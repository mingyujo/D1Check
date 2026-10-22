package com.example.d1check.benchmarkrunner

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import java.io.BufferedWriter
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

internal data class AccuracyPreflightResult(
    val executionIntegrityPassed: Boolean,
    val artifact: File,
    val binaryArtifact: File,
    val summary: Map<String, Any?>,
)

internal class AccuracyPreflightEngine(private val context: Context) {
    fun execute(config: AccuracyPreflightConfig): AccuracyPreflightResult {
        val representativeSet = config.representativeTensorSetPath?.let {
            RepresentativeTensorSet.load(
                File(it),
                expectedContainerSha256 = config.expectedTensorSetContainerSha256,
                expectedPreprocessingConfigurationSha256 =
                    config.expectedPreprocessingConfigurationSha256,
            )
        }
        val inputBytes = if (representativeSet != null) {
            representativeSet.tensors.map { it.bytes }
        } else {
            val generator = DeterministicInputSet.generator(
                config.seed,
                DeterministicInputSet.INPUT_SHAPE.fold(1) { total, value -> total * value } * 4,
            )
            List(config.inputCount) { byteArray(generator.next()) }
        }
        check(inputBytes.size == config.inputCount) {
            "configured input count does not match tensor-set count"
        }
        val referenceOutputs = mutableListOf<FloatArray>()
        val candidateOutputs = mutableListOf<FloatArray>()
        val inputHashes = mutableListOf<String>()
        val referenceOutputHashes = mutableListOf<String>()
        val candidateOutputHashes = mutableListOf<String>()
        val referenceInputSetDigest = MessageDigest.getInstance("SHA-256")
        val candidateInputSetDigest = MessageDigest.getInstance("SHA-256")
        lateinit var referenceDescription: TensorDescription
        lateinit var candidateDescription: TensorDescription

        val cpuOptions = Interpreter.Options()
            .setNumThreads(config.cpuThreads)
            .setUseXNNPACK(true)
        val cpu = Interpreter(ModelLoader.map(context), cpuOptions)
        try {
            cpu.allocateTensors()
            validateInput(cpu)
            referenceDescription = outputDescription(cpu)
            inputBytes.forEach { bytes ->
                check(bytes.size == cpu.getInputTensor(0).numBytes()) { "input tensor byte size mismatch" }
                val input = directBuffer(bytes)
                updateDigest(referenceInputSetDigest, input)
                inputHashes += DeterministicInputSet.sha256(input)
                val output = runOnce(cpu, input)
                referenceOutputs += output
                referenceOutputHashes += floatArraySha256(output)
            }
        } finally {
            cpu.close()
        }

        val compatibility = CompatibilityList()
        check(compatibility.isDelegateSupportedOnThisDevice) {
            "GPU delegate is not supported; output equivalence preflight cannot run"
        }
        val delegate = GpuDelegate(config.gpuDelegateProfile.options())
        val gpuOptions = Interpreter.Options().addDelegate(delegate)
        val gpu = try {
            Interpreter(ModelLoader.map(context), gpuOptions)
        } catch (error: Throwable) {
            delegate.close()
            throw error
        }
        try {
            gpu.allocateTensors()
            validateInput(gpu)
            candidateDescription = outputDescription(gpu)
            check(referenceDescription == candidateDescription) {
                "CPU/GPU output tensor mismatch: CPU=$referenceDescription GPU=$candidateDescription"
            }
            inputBytes.forEachIndexed { index, bytes ->
                check(bytes.size == gpu.getInputTensor(0).numBytes()) { "input tensor byte size mismatch" }
                val input = directBuffer(bytes)
                updateDigest(candidateInputSetDigest, input)
                check(DeterministicInputSet.sha256(input) == inputHashes[index]) {
                    "CPU/GPU deterministic input bytes differ at index $index"
                }
                val output = runOnce(gpu, input)
                candidateOutputs += output
                candidateOutputHashes += floatArraySha256(output)
            }
        } finally {
            gpu.close()
            delegate.close()
        }

        val referenceInputSetSha = referenceInputSetDigest.digest().toHex()
        val candidateInputSetSha = candidateInputSetDigest.digest().toHex()
        check(referenceInputSetSha == candidateInputSetSha) {
            "CPU/GPU input set SHA-256 mismatch"
        }
        val decision = OutputEquivalenceComparator.evaluate(
            references = referenceOutputs,
            candidates = candidateOutputs,
            referenceTensor = referenceDescription,
            candidateTensor = candidateDescription,
            tolerance = config.tolerance,
            fullDelegationVerified = true,
        )
        val directory = context.getExternalFilesDir(ARTIFACT_DIRECTORY)
            ?: File(context.filesDir, ARTIFACT_DIRECTORY)
        check(directory.exists() || directory.mkdirs()) { "cannot create accuracy artifact directory" }
        val binary = writeBinaryArtifact(
            directory, config.commandId, referenceOutputs, candidateOutputs
        )
        val binarySha = sha256File(binary)
        val summary = linkedMapOf<String, Any?>(
            "execution_integrity_status" to if (decision.executionIntegrityPassed) "passed" else "failed",
            "execution_integrity_passed" to decision.executionIntegrityPassed,
            "numerical_tolerance_result" to decision.numericalToleranceResult,
            "numeric_equivalence_passed" to (decision.numericalToleranceResult == "within"),
            "failure_reasons" to decision.failureReasons,
            "deterministic_input_count" to config.inputCount,
            "mismatch_count" to decision.aggregate.mismatchCount,
            "non_finite_count" to decision.aggregate.nonFiniteCount,
            "argmax_match_count" to decision.aggregate.argmaxMatchCount,
            "argmax_mismatch_count" to decision.aggregate.argmaxMismatchCount,
            "top5_set_match_count" to decision.aggregate.top5SetMatchCount,
            "ordered_top5_match_count" to decision.aggregate.orderedTop5MatchCount,
            "aggregate" to aggregateMap(decision.aggregate),
        )
        val taskAccuracy = representativeSet?.let {
            OutputEquivalenceComparator.taskAccuracy(
                decision.perInput,
                it.tensors.map(RepresentativeTensor::mappedOutputIndex),
            )
        }
        summary["task_accuracy"] = taskAccuracy?.let(::taskAccuracyMap)
        val artifact = writeJsonlArtifact(
            directory = directory,
            config = config,
            referenceDescription = referenceDescription,
            inputSetSha256 = referenceInputSetSha,
            inputHashes = inputHashes,
            referenceOutputHashes = referenceOutputHashes,
            candidateOutputHashes = candidateOutputHashes,
            comparisons = decision.perInput,
            binary = binary,
            binarySha256 = binarySha,
            summary = summary,
            representativeSet = representativeSet,
        )
        Log.i(TAG, JSONObject().apply {
            put("schema_version", SCHEMA_VERSION)
            put("event", "accuracy_preflight_complete")
            put("command_id", config.commandId)
            put("status", if (decision.executionIntegrityPassed) "integrity_passed" else "integrity_failed")
            put("check_type", config.checkType.wireName)
            put("artifact_path", artifact.absolutePath)
            put("binary_artifact_path", binary.absolutePath)
        }.toString())
        return AccuracyPreflightResult(decision.executionIntegrityPassed, artifact, binary, summary)
    }

    private fun validateInput(interpreter: Interpreter) {
        check(interpreter.inputTensorCount == 1) { "expected exactly one input tensor" }
        val input = interpreter.getInputTensor(0)
        check(
            input.dataType() == DataType.FLOAT32 &&
                input.shape().contentEquals(DeterministicInputSet.INPUT_SHAPE)
        ) { "unexpected input tensor: ${input.dataType()} ${input.shape().contentToString()}" }
    }

    private fun outputDescription(interpreter: Interpreter): TensorDescription {
        check(interpreter.outputTensorCount == 1) { "expected exactly one output tensor" }
        val output = interpreter.getOutputTensor(0)
        return TensorDescription(output.shape().toList(), output.dataType().toString())
    }

    private fun runOnce(interpreter: Interpreter, input: ByteBuffer): FloatArray {
        val outputTensor = interpreter.getOutputTensor(0)
        val output = ByteBuffer.allocateDirect(outputTensor.numBytes()).order(ByteOrder.nativeOrder())
        input.rewind()
        output.clear()
        interpreter.run(input, output)
        output.rewind()
        return FloatArray(outputTensor.numElements()).also { output.asFloatBuffer().get(it) }
    }

    private fun byteArray(buffer: ByteBuffer): ByteArray {
        val duplicate = buffer.asReadOnlyBuffer()
        duplicate.rewind()
        return ByteArray(duplicate.remaining()).also(duplicate::get)
    }

    private fun directBuffer(bytes: ByteArray): ByteBuffer =
        ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.LITTLE_ENDIAN)
            .apply { put(bytes); rewind() }

    private fun writeBinaryArtifact(
        directory: File,
        commandId: String,
        references: List<FloatArray>,
        candidates: List<FloatArray>,
    ): File {
        val finalFile = File(directory, "accuracy-outputs-$commandId-v1.bin")
        val temporary = File(directory, ".${finalFile.name}.tmp")
        check(!finalFile.exists()) { "accuracy binary artifact already exists: ${finalFile.absolutePath}" }
        check(temporary.createNewFile()) { "accuracy binary temp already exists: ${temporary.absolutePath}" }
        try {
            FileOutputStream(temporary).use { stream ->
                stream.write("D1EQV001".toByteArray(StandardCharsets.US_ASCII))
                val header = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN)
                    .putInt(references.size)
                    .putInt(references.firstOrNull()?.size ?: 0)
                    .array()
                stream.write(header)
                references.indices.forEach { index ->
                    stream.write(floatBytes(references[index]))
                    stream.write(floatBytes(candidates[index]))
                }
                stream.fd.sync()
            }
            check(temporary.renameTo(finalFile)) { "cannot atomically finalize ${finalFile.absolutePath}" }
            return finalFile
        } catch (error: Throwable) {
            temporary.delete()
            throw error
        }
    }

    private fun writeJsonlArtifact(
        directory: File,
        config: AccuracyPreflightConfig,
        referenceDescription: TensorDescription,
        inputSetSha256: String,
        inputHashes: List<String>,
        referenceOutputHashes: List<String>,
        candidateOutputHashes: List<String>,
        comparisons: List<InputComparison>,
        binary: File,
        binarySha256: String,
        summary: Map<String, Any?>,
        representativeSet: RepresentativeTensorSet?,
    ): File {
        val finalFile = File(directory, "accuracy-preflight-${config.commandId}.jsonl")
        val temporary = File(directory, ".${finalFile.name}.tmp")
        check(!finalFile.exists()) { "accuracy JSONL artifact already exists: ${finalFile.absolutePath}" }
        check(temporary.createNewFile()) { "accuracy JSONL temp already exists: ${temporary.absolutePath}" }
        try {
            FileOutputStream(temporary).use { stream ->
                BufferedWriter(OutputStreamWriter(stream, StandardCharsets.UTF_8)).use { writer ->
                    writer.write(json(linkedMapOf<String, Any?>(
                        "schema_version" to SCHEMA_VERSION,
                        "event" to "accuracy_preflight_metadata",
                        "sequence" to 0,
                        "command_id" to config.commandId,
                        "validation_scope" to config.checkType.wireName,
                        "equivalence_scope" to "CPU_GPU_numerical_output_equivalence_not_task_accuracy",
                        "comparator_version" to OutputEquivalenceComparator.VERSION,
                        "reference_resource" to "CPU",
                        "candidate_resource" to "GPU",
                        "reference_cpu_threads" to config.cpuThreads,
                        "gpu_delegate_profile" to config.gpuDelegateProfile.metadata(),
                        "delegate_configuration" to config.gpuDelegateProfile.profileId,
                        "cpu_reference" to mapOf(
                            "threads" to config.cpuThreads,
                            "xnnpack_enabled" to true,
                            "xnnpack_evidence" to "explicit_interpreter_option_not_runtime_kernel_trace",
                            "plain_cpu_claimed" to false,
                        ),
                        "model_id" to ModelLoader.MODEL_ID,
                        "model_sha256" to ModelLoader.MODEL_SHA256,
                        "reference_model_sha256" to ModelLoader.MODEL_SHA256,
                        "candidate_model_sha256" to ModelLoader.MODEL_SHA256,
                        "litert_version" to GpuBenchmarkEngine.LITERT_VERSION,
                        "input_set_version" to (representativeSet?.header?.getString("format_version")
                            ?: DeterministicInputSet.VERSION),
                        "seed" to if (representativeSet == null) config.seed else JSONObject.NULL,
                        "input_count" to config.inputCount,
                        "input_shape" to DeterministicInputSet.INPUT_SHAPE.toList(),
                        "input_dtype" to DeterministicInputSet.INPUT_DTYPE,
                        "normalization" to if (representativeSet == null) {
                            DeterministicInputSet.NORMALIZATION
                        } else {
                            "host_preprocessed_rgb_central_crop_0.875_bilinear_float32_minus1_to_1"
                        },
                        "input_set_sha256" to inputSetSha256,
                        "representative_tensor_set" to representativeSet?.let {
                            mapOf(
                                "container_path" to it.file.absolutePath,
                                "tensor_set_container_sha256" to it.containerSha256,
                                "tensor_set_sha256" to it.tensorSetSha256,
                                "label_mapping_file_sha256" to it.labelMappingSha256,
                                "preprocessing_configuration_sha256" to
                                    it.preprocessingConfigurationSha256,
                                "dataset" to it.header.getJSONObject("dataset"),
                                "selection" to it.header.getJSONObject("selection"),
                            )
                        },
                        "output_tensor_count" to 1,
                        "output_shape" to referenceDescription.shape,
                        "output_dtype" to referenceDescription.dtype,
                        "tolerance" to mapOf(
                            "atol" to config.tolerance.atol,
                            "rtol" to config.tolerance.rtol,
                            "relative_error_epsilon" to config.tolerance.relativeErrorEpsilon,
                        ),
                        "binary_artifact" to mapOf(
                            "format_version" to "d1eq-interleaved-float32-le-v1",
                            "path" to binary.absolutePath,
                            "sha256" to binarySha256,
                        ),
                    )))
                    writer.newLine()
                    comparisons.forEachIndexed { index, comparison ->
                        writer.write(json(linkedMapOf(
                            "schema_version" to SCHEMA_VERSION,
                            "event" to "accuracy_preflight_input",
                            "sequence" to index + 1,
                            "command_id" to config.commandId,
                            "input_index" to index,
                            "input_sha256" to inputHashes[index],
                            "reference_output_sha256" to referenceOutputHashes[index],
                            "candidate_output_sha256" to candidateOutputHashes[index],
                            "metrics" to comparisonMap(comparison),
                            "ground_truth" to representativeSet?.tensors?.get(index)?.let {
                                mapOf(
                                    "wnid" to it.groundTruthWnid,
                                    "mapped_output_index" to it.mappedOutputIndex,
                                    "source_image_sha256" to it.sourceImageSha256,
                                )
                            },
                        )))
                        writer.newLine()
                    }
                    writer.write(json(linkedMapOf<String, Any?>(
                        "schema_version" to SCHEMA_VERSION,
                        "event" to "accuracy_preflight_summary",
                        "sequence" to comparisons.size + 1,
                        "command_id" to config.commandId,
                    ).apply { putAll(summary) }))
                    writer.newLine()
                    writer.flush()
                    stream.fd.sync()
                }
            }
            check(temporary.renameTo(finalFile)) { "cannot atomically finalize ${finalFile.absolutePath}" }
            return finalFile
        } catch (error: Throwable) {
            temporary.delete()
            throw error
        }
    }

    private fun comparisonMap(value: InputComparison) = linkedMapOf<String, Any?>(
        "output_element_count" to value.outputElementCount,
        "max_absolute_error" to value.maxAbsoluteError,
        "max_absolute_error_index" to value.maxAbsoluteErrorIndex,
        "max_absolute_error_reference" to value.maxAbsoluteErrorReference,
        "max_absolute_error_candidate" to value.maxAbsoluteErrorCandidate,
        "max_absolute_error_threshold" to value.maxAbsoluteErrorThreshold,
        "mean_absolute_error" to value.meanAbsoluteError,
        "rmse" to value.rmse,
        "max_relative_error" to value.maxRelativeError,
        "elementwise_mismatch_count" to value.mismatchCount,
        "non_finite_count" to value.nonFiniteCount,
        "reference_minimum" to value.referenceMinimum,
        "reference_maximum" to value.referenceMaximum,
        "reference_probability_sum" to value.referenceSum,
        "candidate_minimum" to value.candidateMinimum,
        "candidate_maximum" to value.candidateMaximum,
        "candidate_probability_sum" to value.candidateSum,
        "cosine_similarity" to value.cosineSimilarity,
        "total_variation_distance" to value.totalVariationDistance,
        "reference_argmax" to value.referenceArgmax,
        "candidate_argmax" to value.candidateArgmax,
        "argmax_agreement" to value.argmaxMatches,
        "reference_top5" to value.referenceTop5,
        "candidate_top5" to value.candidateTop5,
        "top5_overlap_count" to value.top5OverlapCount,
        "top5_overlap_applicable" to value.top5OverlapApplicable,
        "top5_overlap_not_applicable_reason" to value.top5OverlapNotApplicableReason,
        "top5_set_agreement" to value.top5SetMatches,
        "ordered_top5_agreement" to value.orderedTop5Matches,
        "tie_break_rule" to OutputEquivalenceComparator.TIE_BREAK_RULE,
        "reference_top1_margin" to value.referenceTop1Margin,
        "candidate_top1_margin" to value.candidateTop1Margin,
        "reference_top5_boundary_margin" to value.referenceTop5BoundaryMargin,
        "candidate_top5_boundary_margin" to value.candidateTop5BoundaryMargin,
    )

    private fun aggregateMap(value: AggregateComparison) = linkedMapOf<String, Any?>(
        "output_element_count" to value.outputElementCount,
        "max_absolute_error" to value.maxAbsoluteError,
        "mean_absolute_error" to value.meanAbsoluteError,
        "rmse" to value.rmse,
        "max_relative_error" to value.maxRelativeError,
        "mismatch_count" to value.mismatchCount,
        "non_finite_count" to value.nonFiniteCount,
        "argmax_match_count" to value.argmaxMatchCount,
        "argmax_mismatch_count" to value.argmaxMismatchCount,
        "top5_set_match_count" to value.top5SetMatchCount,
        "ordered_top5_match_count" to value.orderedTop5MatchCount,
        "minimum_top5_overlap_count" to value.minimumTop5OverlapCount,
        "top5_overlap_applicable_count" to value.top5OverlapApplicableCount,
        "top5_overlap_not_applicable_count" to value.top5OverlapNotApplicableCount,
        "mean_cosine_similarity" to value.meanCosineSimilarity,
        "minimum_cosine_similarity" to value.minimumCosineSimilarity,
        "mean_total_variation_distance" to value.meanTotalVariationDistance,
        "maximum_total_variation_distance" to value.maximumTotalVariationDistance,
        "reference_probability_sum_minimum" to value.referenceProbabilitySumMinimum,
        "reference_probability_sum_maximum" to value.referenceProbabilitySumMaximum,
        "candidate_probability_sum_minimum" to value.candidateProbabilitySumMinimum,
        "candidate_probability_sum_maximum" to value.candidateProbabilitySumMaximum,
    )

    private fun taskAccuracyMap(value: TaskAccuracyMetrics) = linkedMapOf<String, Any?>(
        "labeled_input_count" to value.labeledInputCount,
        "reference_top1_correct_count" to value.referenceTop1CorrectCount,
        "candidate_top1_correct_count" to value.candidateTop1CorrectCount,
        "reference_top5_correct_count" to value.referenceTop5CorrectCount,
        "candidate_top5_correct_count" to value.candidateTop5CorrectCount,
        "reference_top1_accuracy" to value.referenceTop1Accuracy,
        "candidate_top1_accuracy" to value.candidateTop1Accuracy,
        "reference_top5_accuracy" to value.referenceTop5Accuracy,
        "candidate_top5_accuracy" to value.candidateTop5Accuracy,
        "top1_accuracy_delta" to value.top1AccuracyDelta,
        "top5_accuracy_delta" to value.top5AccuracyDelta,
    )

    private fun json(values: Map<String, Any?>): String = JSONObject().apply {
        values.forEach { (key, value) -> put(key, jsonValue(value)) }
    }.toString()

    private fun jsonValue(value: Any?): Any = when (value) {
        null -> JSONObject.NULL
        is Map<*, *> -> JSONObject().apply {
            value.forEach { (key, nested) -> put(key.toString(), jsonValue(nested)) }
        }
        is Iterable<*> -> JSONArray().apply { value.forEach { put(jsonValue(it)) } }
        else -> value
    }

    private fun updateDigest(digest: MessageDigest, buffer: ByteBuffer) {
        val duplicate = buffer.asReadOnlyBuffer()
        duplicate.rewind()
        digest.update(duplicate)
    }

    private fun floatArraySha256(values: FloatArray): String =
        MessageDigest.getInstance("SHA-256").digest(floatBytes(values)).toHex()

    private fun floatBytes(values: FloatArray): ByteArray =
        ByteBuffer.allocate(values.size * Float.SIZE_BYTES)
            .order(ByteOrder.LITTLE_ENDIAN)
            .apply { values.forEach { putFloat(it) } }
            .array()

    private fun sha256File(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().toHex()
    }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }

    companion object {
        const val TAG = "D1ACC"
        const val SCHEMA_VERSION = 2
        const val ARTIFACT_DIRECTORY = "accuracy-preflight"
    }
}
