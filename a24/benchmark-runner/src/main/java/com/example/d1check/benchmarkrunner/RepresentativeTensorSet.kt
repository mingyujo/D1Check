package com.example.d1check.benchmarkrunner

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

internal data class RepresentativeTensor(
    val sampleId: String,
    val sourceImageSha256: String,
    val tensorSha256: String,
    val groundTruthWnid: String,
    val mappedOutputIndex: Int,
    val bytes: ByteArray,
)

internal data class RepresentativeTensorSet(
    val file: File,
    val header: JSONObject,
    val tensors: List<RepresentativeTensor>,
    val containerSha256: String,
    val tensorSetSha256: String,
    val labelMappingSha256: String,
    val preprocessingConfigurationSha256: String,
) {
    companion object {
        const val FORMAT_VERSION = "d1-representative-tensor-set-v1"
        private val MAGIC = "D1TSET01".toByteArray(Charsets.US_ASCII)
        private const val MAX_HEADER_BYTES = 8 * 1024 * 1024

        fun load(
            file: File,
            expectedShape: IntArray = DeterministicInputSet.INPUT_SHAPE,
            expectedTensorBytes: Int = expectedShape.fold(1) { result, value -> result * value } * 4,
            expectedContainerSha256: String? = null,
            expectedPreprocessingConfigurationSha256: String? = null,
        ): RepresentativeTensorSet {
            require(file.isFile) { "representative tensor-set does not exist: ${file.absolutePath}" }
            val all = file.readBytes()
            require(all.size >= 12) { "representative tensor-set is truncated" }
            require(all.copyOfRange(0, 8).contentEquals(MAGIC)) {
                "representative tensor-set magic is invalid"
            }
            val headerSize = ByteBuffer.wrap(all, 8, 4).order(ByteOrder.LITTLE_ENDIAN).int
            require(headerSize in 2..MAX_HEADER_BYTES && 12L + headerSize <= all.size.toLong()) {
                "representative tensor-set header length is invalid"
            }
            val header = JSONObject(String(all, 12, headerSize, Charsets.UTF_8))
            require(header.getInt("schema_version") == 1) { "unsupported tensor-set schema" }
            require(header.getString("format_version") == FORMAT_VERSION) {
                "unsupported tensor-set format"
            }
            val tensor = header.getJSONObject("tensor")
            require(jsonInts(tensor.getJSONArray("shape")) == expectedShape.toList()) {
                "representative tensor shape mismatch"
            }
            require(tensor.getString("dtype") == "FLOAT32") {
                "representative tensor dtype must be FLOAT32"
            }
            require(tensor.getString("endian") == "LITTLE") {
                "representative tensor endian must be LITTLE"
            }
            require(tensor.getInt("bytes_per_tensor") == expectedTensorBytes) {
                "representative tensor byte size mismatch"
            }
            val samples = header.getJSONArray("samples")
            val count = tensor.getInt("count")
            require(count > 0 && samples.length() == count) {
                "representative tensor count mismatch"
            }
            val payloadStart = 12 + headerSize
            val expectedPayloadSize = count.toLong() * expectedTensorBytes
            require(all.size.toLong() == payloadStart.toLong() + expectedPayloadSize) {
                "representative tensor-set payload is truncated or has trailing bytes"
            }
            val payload = all.copyOfRange(payloadStart, all.size)
            val payloadHash = sha256(payload)
            require(payloadHash == normalizedSha(header.getString("tensor_set_sha256"))) {
                "representative tensor-set payload SHA-256 mismatch"
            }
            val values = mutableListOf<RepresentativeTensor>()
            repeat(count) { index ->
                val item = samples.getJSONObject(index)
                require(item.getInt("tensor_index") == index) { "tensor indexes are not contiguous" }
                require(item.getInt("byte_offset") == index * expectedTensorBytes) {
                    "tensor byte offset mismatch at index $index"
                }
                require(item.getInt("byte_length") == expectedTensorBytes) {
                    "tensor byte length mismatch at index $index"
                }
                val bytes = payload.copyOfRange(
                    index * expectedTensorBytes,
                    (index + 1) * expectedTensorBytes,
                )
                val tensorHash = normalizedSha(item.getString("tensor_sha256"))
                require(sha256(bytes) == tensorHash) { "tensor SHA-256 mismatch at index $index" }
                val outputIndex = item.getInt("mapped_output_index")
                require(outputIndex in 1..1000) { "mapped output index must include background offset" }
                values += RepresentativeTensor(
                    sampleId = item.getString("sample_id"),
                    sourceImageSha256 = normalizedSha(item.getString("source_image_sha256")),
                    tensorSha256 = tensorHash,
                    groundTruthWnid = item.getString("ground_truth_wnid"),
                    mappedOutputIndex = outputIndex,
                    bytes = bytes,
                )
            }
            val selection = header.getJSONObject("selection")
            val selectedIds = selection.getJSONArray("selected_sample_ids")
            require(selectedIds.length() == count) {
                "selected sample ID count mismatch"
            }
            require((0 until count).map(selectedIds::getString).distinct().size == count) {
                "selected sample IDs contain duplicates"
            }
            require(values.indices.all { values[it].sampleId == selectedIds.getString(it) }) {
                "selected sample ID inventory does not match samples"
            }
            val labelHash = normalizedSha(
                header.getJSONObject("label_mapping").getString("file_sha256")
            )
            require(header.getJSONObject("label_mapping").getInt("background_index") == 0) {
                "label mapping must reserve output index 0 for background"
            }
            val preprocessing = header.getJSONObject("preprocessing")
            val preprocessingHash = normalizedSha(
                preprocessing.getString("configuration_sha256")
            )
            val expectedPreprocessingHash = expectedPreprocessingConfigurationSha256?.let(
                ::normalizedSha
            )
            val recomputedPreprocessingHash = sha256(
                PreprocessingCanonicalJsonV1.bytesExcluding(
                    preprocessing, "configuration_sha256"
                )
            )
            RepresentativeHashContract.verifyPreprocessing(
                preprocessingHash, expectedPreprocessingHash, recomputedPreprocessingHash
            )
            val containerHash = sha256(all)
            val expectedContainerHash = expectedContainerSha256?.let(::normalizedSha)
            RepresentativeHashContract.verifyContainer(expectedContainerHash, containerHash)
            return RepresentativeTensorSet(
                file, header, values, containerHash, payloadHash, labelHash, preprocessingHash,
            )
        }

        private fun jsonInts(values: JSONArray): List<Int> =
            (0 until values.length()).map(values::getInt)

        private fun normalizedSha(value: String): String {
            val normalized = value.lowercase()
            require(normalized.matches(Regex("[0-9a-f]{64}"))) { "invalid SHA-256 value" }
            return normalized
        }

        private fun sha256(value: ByteArray): String = MessageDigest.getInstance("SHA-256")
            .digest(value).joinToString("") { "%02x".format(it) }

    }
}

internal object RepresentativeHashContract {
    fun verifyPreprocessing(declared: String, expected: String?, recomputed: String) {
        require(expected == null || declared == expected) {
            "preprocessing configuration SHA-256 mismatch: " +
                "declared=$declared expected=$expected recomputed=$recomputed"
        }
        require(recomputed == declared) {
            "preprocessing configuration SHA-256 mismatch: " +
                "declared=$declared expected=${expected ?: "not_provided"} " +
                "recomputed=$recomputed"
        }
    }

    fun verifyContainer(expected: String?, recomputed: String) {
        require(expected == null || recomputed == expected) {
            "representative tensor-set container SHA-256 mismatch: " +
                "expected=$expected recomputed=$recomputed"
        }
    }
}

/**
 * d1-representative-tensor-set-v1 preprocessing canonicalization contract.
 *
 * Matches Python json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":"))
 * for the v1 preprocessing schema. In particular, '/' is not escaped and parsed decimal
 * values such as -1.0 remain decimal values. The hash field itself is excluded at the
 * preprocessing object's top level.
 */
internal object PreprocessingCanonicalJsonV1 {
    fun bytesExcluding(value: JSONObject, excludedKey: String): ByteArray =
        canonicalObject(
            value.keys().asSequence().associateWith(value::get), excludedKey
        ).toByteArray(Charsets.UTF_8)

    fun bytes(value: Map<String, Any?>): ByteArray =
        canonicalObject(value, null).toByteArray(Charsets.UTF_8)

    private fun canonicalObject(value: Map<String, Any?>, excludedKey: String?): String =
        value.keys.filter { it != excludedKey }.sorted().joinToString(
            prefix = "{", postfix = "}", separator = ",",
        ) { key -> "${quote(key)}:${canonical(value.getValue(key))}" }

    private fun canonical(value: Any?): String = when (value) {
        null, JSONObject.NULL -> "null"
        is JSONObject -> canonicalObject(
            value.keys().asSequence().associateWith(value::get), null
        )
        is JSONArray -> (0 until value.length()).joinToString(
            prefix = "[", postfix = "]", separator = ",",
        ) { index -> canonical(value.get(index)) }
        is Map<*, *> -> {
            require(value.keys.all { it is String }) { "canonical JSON object keys must be strings" }
            @Suppress("UNCHECKED_CAST")
            canonicalObject(value as Map<String, Any?>, null)
        }
        is Iterable<*> -> value.joinToString(
            prefix = "[", postfix = "]", separator = ",", transform = ::canonical
        )
        is Array<*> -> value.joinToString(
            prefix = "[", postfix = "]", separator = ",", transform = ::canonical
        )
        is Int, is Long, is Short, is Byte -> value.toString()
        is Float -> canonicalFloating(value.toDouble(), value.toString())
        is Double -> canonicalFloating(value, value.toString())
        is Boolean -> value.toString()
        is String -> quote(value)
        else -> throw IllegalArgumentException(
            "unsupported JSON value in preprocessing configuration: ${value.javaClass.name}"
        )
    }

    private fun canonicalFloating(value: Double, encoded: String): String {
        require(value.isFinite()) { "canonical JSON numbers must be finite" }
        require('e' !in encoded.lowercase()) {
            "tensor-set-v1 preprocessing does not permit exponent-form numbers: $encoded"
        }
        return encoded
    }

    private fun quote(value: String): String = buildString {
        append('"')
        value.forEach { character ->
            when (character) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\b' -> append("\\b")
                '\u000c' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (character.code <= 0x1f) {
                    append("\\u").append(character.code.toString(16).padStart(4, '0'))
                } else {
                    append(character)
                }
            }
        }
        append('"')
    }
}
