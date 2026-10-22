package com.example.d1check.benchmarkrunner

import java.nio.ByteBuffer
import java.util.ArrayDeque

internal fun interface CalibrationClock {
    fun monotonicNanos(): Long
}

internal data class CalibrationImageBytes(
    val bytes: ByteArray,
    val sha256: String,
    val mimeType: String,
    val byteCount: Long,
    val exifOrientation: Int,
)

internal interface CalibrationDecodedImage : AutoCloseable {
    val rawWidth: Int
    val rawHeight: Int
    val exifOrientation: Int
    val width: Int
    val height: Int
}

internal data class CalibrationInputTensor(
    val buffer: ByteBuffer,
    val sha256: String,
)

internal interface CalibrationImageReader {
    fun read(uri: String): CalibrationImageBytes
}

internal interface CalibrationImageDecoder {
    fun decode(image: CalibrationImageBytes): CalibrationDecodedImage
}

internal fun interface CalibrationPreprocessor {
    fun preprocess(image: CalibrationDecodedImage): CalibrationInputTensor
}

internal interface CalibrationBackendRuntime : AutoCloseable {
    val actualBackend: CalibrationBackend
    val fallbackStatus: CalibrationFallbackStatus
    fun run(input: ByteBuffer, clock: CalibrationClock): CalibrationRawOutput
}

internal data class CalibrationRawOutput(
    val values: FloatArray,
    val interpreterRunStartNs: Long,
    val interpreterRunEndNs: Long,
)

internal data class PreparedCalibrationBackend(
    val runtime: CalibrationBackendRuntime,
    val cold: Boolean,
    val transition: String?,
)

internal interface CalibrationRuntimePool : AutoCloseable {
    fun prepare(backend: CalibrationBackend): PreparedCalibrationBackend
}

internal fun interface CalibrationPostprocessor {
    fun process(output: FloatArray): ClassificationOutput
}

internal data class CalibrationPersistenceReceipt(
    val relativePath: String,
    val rollback: () -> Unit = {},
)

internal fun interface CalibrationResultStore {
    fun persist(request: CalibrationRequest, output: ClassificationOutput):
        CalibrationPersistenceReceipt
}

internal fun interface CalibrationOutputConsumer {
    fun outputReady(request: CalibrationRequest, output: ClassificationOutput)
}

internal fun interface CalibrationResultRecorder {
    fun record(result: CalibrationRequestResult)
}

internal data class CalibrationSubmission(
    val accepted: Boolean,
    val requestId: String,
    val terminalStatus: CalibrationTerminalStatus?,
)

internal class CalibrationPipeline(
    private val manifest: CalibrationInputManifest,
    private val clock: CalibrationClock,
    private val imageReader: CalibrationImageReader,
    private val imageDecoder: CalibrationImageDecoder,
    private val preprocessor: CalibrationPreprocessor,
    private val runtimePool: CalibrationRuntimePool,
    private val postprocessor: CalibrationPostprocessor,
    private val resultStore: CalibrationResultStore,
    private val recorder: CalibrationResultRecorder,
) : AutoCloseable {
    private data class Pending(
        val request: CalibrationRequest,
        val consumer: CalibrationOutputConsumer,
        val completed: (CalibrationRequestResult) -> Unit,
    )

    private val queue = ArrayDeque<Pending>()
    private var closed = false
    private var processing = false

    @Synchronized
    fun submit(
        request: CalibrationRequest,
        consumer: CalibrationOutputConsumer = CalibrationOutputConsumer { _, _ -> },
        completed: (CalibrationRequestResult) -> Unit = {},
    ): CalibrationSubmission {
        check(!closed) { "calibration pipeline is closed" }
        require(request.image in manifest.images) { "request image is not in input manifest" }
        if (manifest.mode == CalibrationMode.FIXED &&
            request.requestedBackend != manifest.fixedBackend
        ) {
            return reject(request, "requested backend violates fixed calibration manifest", completed)
        }
        if (queue.size >= manifest.queueCapacity) {
            return reject(request, "calibration request queue is full", completed)
        }
        queue.addLast(Pending(request, consumer, completed))
        return CalibrationSubmission(true, request.requestId, null)
    }

    @Synchronized
    fun pendingCount(): Int = queue.size

    fun drainOne(): Boolean {
        val pending = synchronized(this) {
            check(!processing) { "only one calibration worker may drain the pipeline" }
            val next = if (queue.isEmpty()) null else queue.removeFirst()
            next ?: return false
            processing = true
            next
        }
        try {
            val result = process(pending.request, pending.consumer)
            recorder.record(result)
            pending.completed(result)
        } finally {
            synchronized(this) { processing = false }
        }
        return true
    }

    fun drainAll() {
        while (drainOne()) Unit
    }

    private fun process(
        request: CalibrationRequest,
        consumer: CalibrationOutputConsumer,
    ): CalibrationRequestResult {
        val timestamps = CalibrationTimestamps(
            pickerResultReceivedNs = request.pickerResultReceivedNs,
            acceptedNs = request.acceptedNs,
        )
        var decoded: CalibrationDecodedImage? = null
        var actualBackend: CalibrationBackend? = null
        var fallbackStatus = CalibrationFallbackStatus.NOT_APPLICABLE
        var executionClass: CalibrationThermalClass? = null
        var transition: String? = null
        var inputTensorSha256: String? = null
        var classification: ClassificationOutput? = null
        var persistedRelativePath: String? = null
        var persistenceReceipt: CalibrationPersistenceReceipt? = null
        return try {
            val serviceStart = clock.monotonicNanos()
            timestamps.executionStartNs = serviceStart
            if (request.deadlineNs != null && serviceStart >= request.deadlineNs) {
                timestamps.terminalNs = clock.monotonicNanos()
                return terminal(
                    request, CalibrationTerminalStatus.EXPIRED, timestamps, null,
                    CalibrationFallbackStatus.NOT_APPLICABLE, null, null, null, null, null,
                    "request expired before execution",
                )
            }

            timestamps.imageReadStartNs = clock.monotonicNanos()
            val imageBytes = imageReader.read(request.imageUri)
            timestamps.imageReadEndNs = clock.monotonicNanos()
            check(imageBytes.sha256 == request.image.sha256) { "image SHA-256 mismatch" }
            check(imageBytes.byteCount == request.image.byteCount) { "image byte count mismatch" }
            check(imageBytes.mimeType == request.image.mimeType) { "image MIME type mismatch" }
            check(imageBytes.exifOrientation == request.image.exifOrientation) {
                "image EXIF orientation mismatch"
            }

            timestamps.decodeStartNs = clock.monotonicNanos()
            decoded = imageDecoder.decode(imageBytes)
            timestamps.decodeEndNs = clock.monotonicNanos()
            check(decoded.rawWidth == request.image.rawWidth &&
                decoded.rawHeight == request.image.rawHeight) {
                "raw image dimensions mismatch"
            }
            check(decoded.exifOrientation == request.image.exifOrientation) {
                "decoded EXIF orientation mismatch"
            }
            check(decoded.width == request.image.transformedWidth &&
                decoded.height == request.image.transformedHeight) {
                "transformed image dimensions mismatch"
            }

            timestamps.preprocessingStartNs = clock.monotonicNanos()
            val input = preprocessor.preprocess(decoded)
            timestamps.preprocessingEndNs = clock.monotonicNanos()
            inputTensorSha256 = input.sha256

            timestamps.schedulerDecisionStartNs = clock.monotonicNanos()
            val selectedBackend = request.requestedBackend
            check(manifest.mode != CalibrationMode.FIXED || selectedBackend == manifest.fixedBackend)
            timestamps.schedulerDecisionEndNs = clock.monotonicNanos()
            timestamps.backendPrepareStartNs = clock.monotonicNanos()
            val prepared = runtimePool.prepare(selectedBackend)
            timestamps.backendPrepareEndNs = clock.monotonicNanos()
            actualBackend = prepared.runtime.actualBackend
            fallbackStatus = prepared.runtime.fallbackStatus
            transition = prepared.transition
            executionClass = when {
                prepared.cold -> CalibrationThermalClass.COLD
                request.isWarmup -> CalibrationThermalClass.WARMUP
                else -> CalibrationThermalClass.WARM
            }
            check(actualBackend == request.requestedBackend) {
                "silent backend fallback rejected: requested=${request.requestedBackend} " +
                    "actual=$actualBackend"
            }
            check(fallbackStatus != CalibrationFallbackStatus.DETECTED) {
                "backend fallback detected"
            }

            val rawOutput = prepared.runtime.run(input.buffer, clock)
            timestamps.interpreterRunStartNs = rawOutput.interpreterRunStartNs
            timestamps.interpreterRunEndNs = rawOutput.interpreterRunEndNs

            timestamps.postprocessingStartNs = clock.monotonicNanos()
            classification = postprocessor.process(rawOutput.values)
            timestamps.postprocessingEndNs = clock.monotonicNanos()
            check(classification.nonFiniteCount == 0) { "non-finite model output" }

            when (request.requestType) {
                CalibrationRequestType.URGENT -> {
                    timestamps.outputReadyNs = clock.monotonicNanos()
                    consumer.outputReady(request, classification)
                }
                CalibrationRequestType.NORMAL -> {
                    timestamps.persistenceStartNs = clock.monotonicNanos()
                    val receipt = resultStore.persist(request, classification)
                    persistenceReceipt = receipt
                    persistedRelativePath = receipt.relativePath
                    timestamps.persistenceCompletedNs = clock.monotonicNanos()
                }
            }
            timestamps.terminalNs = clock.monotonicNanos()
            terminal(
                request, CalibrationTerminalStatus.SUCCEEDED, timestamps, actualBackend,
                fallbackStatus, executionClass, transition, inputTensorSha256,
                classification, persistedRelativePath, null,
            )
        } catch (error: Throwable) {
            persistenceReceipt?.let { receipt ->
                try {
                    receipt.rollback()
                } catch (cleanup: Throwable) {
                    error.addSuppressed(cleanup)
                }
            }
            timestamps.terminalNs = maxOf(
                timestamps.terminalNs ?: Long.MIN_VALUE,
                clock.monotonicNanos(),
            )
            terminal(
                request, CalibrationTerminalStatus.FAILED, timestamps, actualBackend,
                fallbackStatus, executionClass, transition, inputTensorSha256,
                null, null,
                "${error.javaClass.simpleName}: ${error.message ?: ""}",
            )
        } finally {
            decoded?.close()
        }
    }

    private fun terminal(
        request: CalibrationRequest,
        status: CalibrationTerminalStatus,
        timestamps: CalibrationTimestamps,
        actualBackend: CalibrationBackend?,
        fallbackStatus: CalibrationFallbackStatus,
        executionClass: CalibrationThermalClass?,
        transition: String?,
        inputTensorSha256: String?,
        output: ClassificationOutput?,
        persistedRelativePath: String?,
        error: String?,
    ): CalibrationRequestResult {
        timestamps.validateMonotonic(status)
        return CalibrationRequestResult(
            request = request,
            terminalStatus = status,
            timestamps = timestamps,
            actualBackend = actualBackend,
            fallbackStatus = fallbackStatus,
            executionClass = executionClass,
            transition = transition,
            inputTensorSha256 = inputTensorSha256,
            output = output,
            persistedRelativePath = persistedRelativePath,
            error = error,
        )
    }

    private fun reject(
        request: CalibrationRequest,
        reason: String,
        completed: (CalibrationRequestResult) -> Unit,
    ): CalibrationSubmission {
        val timestamps = CalibrationTimestamps(
            pickerResultReceivedNs = request.pickerResultReceivedNs,
            acceptedNs = request.acceptedNs,
            terminalNs = clock.monotonicNanos(),
        )
        val result = terminal(
            request, CalibrationTerminalStatus.REJECTED, timestamps, null,
            CalibrationFallbackStatus.NOT_APPLICABLE, null, null, null, null, null, reason,
        )
        recorder.record(result)
        completed(result)
        return CalibrationSubmission(false, request.requestId, result.terminalStatus)
    }

    override fun close() {
        synchronized(this) {
            check(!processing) { "cannot close calibration pipeline while processing" }
            closed = true
        }
        runtimePool.close()
    }
}
