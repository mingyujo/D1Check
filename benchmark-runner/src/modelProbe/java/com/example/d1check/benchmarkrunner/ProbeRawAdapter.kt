package com.example.d1check.benchmarkrunner

import android.os.SystemClock
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.Tensor
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

internal class ProbeUnsupportedBackendException(message: String) : IllegalStateException(message)

internal data class ProbeRawInvocation(
    val seed: Int,
    val inputSha256: String,
    val outputSha256: List<String>,
    val outputs: List<FloatArray>,
    val invokeNs: Long,
    val backend: ProbeBackend,
    val delegationStatus: String,
)

internal class ProbeRawSession private constructor(
    private val manifest: ModelProbeManifest,
    private val interpreter: Interpreter,
    private val gpuDelegate: GpuDelegate?,
    private val progress: ProbeProgress?,
) : AutoCloseable {
    private var closed = false

    fun invoke(seed: Int): ProbeRawInvocation {
        check(!closed) { "Probe raw session is closed" }
        require(seed in 0..2) { "Probe raw seed must be 0, 1, or 2" }
        val input = deterministicInput(manifest.model.task, seed)
        return invokePrepared(input, seed).also { progress?.captureRaw(it) }
    }

    /** Diagnostic same-tensor replay; never written as a synthetic-seed capture. */
    fun invokePrepared(input: ByteBuffer, seed: Int = 0, invocationObserver: ((Long, Long) -> Unit)? = null,
                       diagnosticMark: ((String, String) -> Unit)? = null): ProbeRawInvocation {
        check(!closed) { "Probe raw session is closed" }
        require(input.capacity() == interpreter.getInputTensor(0).numBytes()) { "Prepared input size mismatch" }
        val outputBuffers = manifest.tensor.outputs.associate { spec ->
            spec.index to ByteBuffer.allocateDirect(interpreter.getOutputTensor(spec.index).numBytes())
                .order(ByteOrder.nativeOrder())
        }.toMutableMap<Int, Any>()
        input.rewind()
        outputBuffers.values.forEach { (it as ByteBuffer).clear() }
        diagnosticMark?.invoke("host_inference", "start")
        progress?.mark("measured_invocation", "start")
        val startedNs: Long
        val finishedNs: Long
        if (invocationObserver == null) {
            // Preserve the original formal host-invocation timing boundary.
            val start = SystemClock.elapsedRealtimeNanos()
            interpreter.runForMultipleInputsOutputs(arrayOf(input), outputBuffers)
            val finish = SystemClock.elapsedRealtimeNanos()
            startedNs = start; finishedNs = finish
        } else {
            val bounds = ArrivalTimingDev.observeInvocation(SystemClock::elapsedRealtimeNanos, invocationObserver) {
                interpreter.runForMultipleInputsOutputs(arrayOf(input), outputBuffers)
            }
            startedNs = bounds.first; finishedNs = bounds.second
        }
        diagnosticMark?.invoke("host_inference", "succeeded")
        diagnosticMark?.invoke("output_readback", "start")
        progress?.mark("measured_invocation", "finish")
        progress?.mark("output_readback", "start")
        val outputs = manifest.tensor.outputs.map { spec ->
            val buffer = outputBuffers.getValue(spec.index) as ByteBuffer
            buffer.rewind()
            FloatArray(interpreter.getOutputTensor(spec.index).numElements()).also {
                buffer.asFloatBuffer().get(it)
            }
        }
        progress?.mark("output_readback", "finish")
        check(outputs.all { output -> output.all { it.isFinite() } }) {
            "Probe raw output contains non-finite values"
        }
        diagnosticMark?.invoke("output_readback", "succeeded")
        return ProbeRawInvocation(
            seed = seed,
            inputSha256 = sha256(input),
            outputSha256 = outputs.map(::sha256),
            outputs = outputs,
            invokeNs = finishedNs - startedNs,
            backend = manifest.execution.backend,
            delegationStatus = if (manifest.execution.backend == ProbeBackend.GPU) {
                "unverified_requires_host_delegate_log"
            } else {
                "not_applicable_cpu"
            },
        )
    }

    override fun close() {
        if (closed) return
        closed = true
        var first: Throwable? = null
        try {
            closeProbeResource(progress, "runtime_close") { interpreter.close() }
        } catch (error: Throwable) {
            first = error
        }
        try {
            closeProbeResource(progress, "delegate_close") { gpuDelegate?.close() }
        } catch (error: Throwable) {
            if (first == null) first = error else first.addSuppressed(error)
        }
        first?.let { throw it }
    }

    companion object {
        fun create(manifest: ModelProbeManifest, model: VerifiedProbeFile, progress: ProbeProgress? = null,
                   initializationMark: ((String, String) -> Unit)? = null): ProbeRawSession {
            fun mark(stage: String, edge: String) {
                progress?.mark(stage, edge)
                initializationMark?.invoke(stage, if (edge == "finish") "succeeded" else edge)
            }
            require(model.sha256 == manifest.model.sha256) { "Verified model identity mismatch" }
            val options = Interpreter.Options()
            var delegate: GpuDelegate? = null
            try {
                when (manifest.execution.backend) {
                    ProbeBackend.CPU -> options
                        .setNumThreads(manifest.runtime.cpuThreads)
                        .setUseXNNPACK(manifest.runtime.xnnpack)
                    ProbeBackend.GPU -> {
                        val profile = GpuDelegateProfile.fromId(manifest.runtime.gpuProfileId)
                        require(profile.configurationSha256 == manifest.runtime.gpuConfigurationSha256) {
                            "GPU configuration SHA-256 mismatch"
                        }
                        initializationMark?.invoke("gpu_compatibility", "start")
                        val compatibility = CompatibilityList()
                        if (!compatibility.isDelegateSupportedOnThisDevice) {
                            throw ProbeUnsupportedBackendException(
                                "GPU delegate is unsupported by the strict compatibility list"
                            )
                        }
                        initializationMark?.invoke("gpu_compatibility", "succeeded")
                        mark("gpu_delegate_construction", "start")
                        delegate = GpuDelegate(profile.options())
                        mark("gpu_delegate_construction", "finish")
                        mark("gpu_delegate_attachment", "start")
                        options.addDelegate(delegate)
                        mark("gpu_delegate_attachment", "finish")
                    }
                }
                val buffer = model.readOnlyBuffer.duplicate().apply { rewind() }
                mark("interpreter_construction", "start")
                val interpreter = Interpreter(buffer, options)
                try {
                    mark("interpreter_construction", "finish")
                    mark("tensor_allocation", "start")
                    interpreter.allocateTensors()
                    mark("tensor_allocation", "finish")
                    initializationMark?.invoke("tensor_validation", "start")
                    validateTensors(interpreter, manifest.tensor)
                    initializationMark?.invoke("tensor_validation", "succeeded")
                    return ProbeRawSession(manifest, interpreter, delegate, progress)
                } catch (error: Throwable) {
                    try {
                        closeProbeResource(progress, "runtime_close") { interpreter.close() }
                    } catch (cleanup: Throwable) {
                        error.addSuppressed(cleanup)
                    }
                    throw error
                }
            } catch (error: Throwable) {
                try {
                    closeProbeResource(progress, "delegate_close") { delegate?.close() }
                } catch (cleanup: Throwable) {
                    error.addSuppressed(cleanup)
                }
                throw error
            }
        }

        internal fun deterministicInput(task: ProbeTask, seed: Int): ByteBuffer {
            require(seed in 0..2)
            val size = if (task == ProbeTask.CLASSIFICATION) 224 else 320
            val center = if (task == ProbeTask.CLASSIFICATION) 127.0f else 127.5f
            val scale = if (task == ProbeTask.CLASSIFICATION) 128.0f else 127.5f
            return ByteBuffer.allocateDirect(size * size * 3 * Float.SIZE_BYTES)
                .order(ByteOrder.LITTLE_ENDIAN)
                .apply {
                    for (y in 0 until size) {
                        for (x in 0 until size) {
                            val red = (3 * x + 5 * y + 17 + 29 * seed) and 0xff
                            val green = (11 * x + 7 * y + 29 + 31 * seed) and 0xff
                            val blue = (13 * x + 19 * y + 43 + 37 * seed) and 0xff
                            putFloat((red - center) / scale)
                            putFloat((green - center) / scale)
                            putFloat((blue - center) / scale)
                        }
                    }
                    rewind()
                }
        }

        private fun validateTensors(interpreter: Interpreter, contract: ProbeTensorContract) {
            require(interpreter.inputTensorCount == contract.inputs.size) { "Input tensor count mismatch" }
            require(interpreter.outputTensorCount == contract.outputs.size) { "Output tensor count mismatch" }
            contract.inputs.forEach { validateTensor(interpreter.getInputTensor(it.index), it, "input") }
            contract.outputs.forEach { validateTensor(interpreter.getOutputTensor(it.index), it, "output") }
        }

        private fun validateTensor(actual: Tensor, expected: ProbeTensor, area: String) {
            require(actual.name() == expected.name) { "$area tensor name mismatch at ${expected.index}" }
            require(actual.shape().contentEquals(expected.shape)) { "$area tensor shape mismatch at ${expected.index}" }
            require(actual.dataType() == DataType.FLOAT32 && expected.dtype == "FLOAT32") {
                "$area tensor dtype mismatch at ${expected.index}"
            }
            require(actual.quantizationParams().scale == 0f && actual.quantizationParams().zeroPoint == 0) {
                "$area tensor quantization mismatch at ${expected.index}"
            }
        }

        private fun sha256(buffer: ByteBuffer): String {
            val duplicate = buffer.asReadOnlyBuffer().apply { rewind() }
            val digest = MessageDigest.getInstance("SHA-256")
            digest.update(duplicate)
            return digest.digest().toHex()
        }

        private fun sha256(values: FloatArray): String {
            val bytes = ByteBuffer.allocate(values.size * Float.SIZE_BYTES)
                .order(ByteOrder.LITTLE_ENDIAN)
                .apply { values.forEach { value -> putFloat(value) } }
                .array()
            return MessageDigest.getInstance("SHA-256").digest(bytes).toHex()
        }

        private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }
    }
}
