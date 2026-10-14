package com.example.d1check.benchmarkrunner

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.StandardCopyOption

internal object ModelProbeArtifacts {
    val artifactNames = listOf(
        "metadata.json", "events.jsonl", "raw_equivalence.json", "decoded_results.json",
        "memory.json", "delegate_evidence.json", "summary.json",
    )

    fun writeFinalized(
        root: File,
        identity: Map<String, Any?>,
        metadata: Map<String, Any?>,
        events: List<Map<String, Any?>>,
        rawEquivalence: Map<String, Any?>,
        decodedResults: Map<String, Any?>,
        memory: Map<String, Any?>,
        delegateEvidence: Map<String, Any?>,
        summary: Map<String, Any?>,
    ) {
        require(!root.exists()) { "Probe output root already exists" }
        require(root.mkdirs()) { "Cannot create probe output root" }
        val values = linkedMapOf(
            "metadata.json" to json(metadata),
            "events.jsonl" to events.joinToString(separator = "\n", postfix = "\n") { json(it) },
            "raw_equivalence.json" to json(rawEquivalence),
            "decoded_results.json" to json(decodedResults),
            "memory.json" to json(memory),
            "delegate_evidence.json" to json(delegateEvidence),
            "summary.json" to json(summary),
        )
        values.forEach { (name, payload) -> writeAtomic(File(root, name), payload) }
        val artifactSet = artifactNames.map { name ->
            val file = File(root, name)
            linkedMapOf<String, Any?>(
                "path" to name, "byte_count" to file.length(), "sha256" to ProbeModelFile.sha256(file),
            )
        }
        val provenance = identity + linkedMapOf<String, Any?>(
            "artifact_set" to artifactSet,
        )
        writeAtomic(File(root, "provenance.json"), json(provenance))
        validate(root, identity)
    }

    /** Re-read the stored bytes, including every event, before acknowledging finalization. */
    fun validate(root: File, identity: Map<String, Any?>) {
        require(root.absoluteFile == root.canonicalFile && root.isDirectory) { "Invalid probe artifact root" }
        val files = requireNotNull(root.listFiles())
        require(files.map { it.name }.toSet() == (artifactNames + "provenance.json").toSet()) {
            "Probe artifact fixed set mismatch"
        }
        require(files.all { it.isFile && it.absoluteFile == it.canonicalFile }) {
            "Probe artifacts must be regular non-symlink files"
        }
        fun binding(value: JSONObject) {
            identity.forEach { (key, expected) ->
                require(value.has(key) && value.get(key).toString() == expected.toString()) {
                    "Probe artifact binding mismatch: $key"
                }
            }
        }
        val provenance = JSONObject(File(root, "provenance.json").readText(StandardCharsets.UTF_8))
        binding(provenance)
        require(provenance.keys().asSequence().toSet() == identity.keys + "artifact_set") {
            "Probe provenance keys mismatch"
        }
        val entries = provenance.getJSONArray("artifact_set")
        val seen = mutableSetOf<String>()
        repeat(entries.length()) { index ->
            val entry = entries.getJSONObject(index)
            require(entry.keys().asSequence().toSet() == setOf("path", "byte_count", "sha256"))
            val name = entry.getString("path")
            require(name in artifactNames && seen.add(name)) { "Invalid probe provenance path" }
            val file = File(root, name)
            require(file.length() == entry.getLong("byte_count") &&
                ProbeModelFile.sha256(file) == entry.getString("sha256")) { "Probe artifact hash/size mismatch: $name" }
        }
        require(seen == artifactNames.toSet()) { "Incomplete probe provenance" }
        artifactNames.filter { it != "events.jsonl" }.forEach { name ->
            binding(JSONObject(File(root, name).readText(StandardCharsets.UTF_8)))
        }
        val events = File(root, "events.jsonl").readLines(StandardCharsets.UTF_8)
        require(events.isNotEmpty() && events.none { it.isBlank() }) { "Empty probe event record" }
        events.forEach { binding(JSONObject(it)) }
    }

    private fun writeAtomic(file: File, payload: String) {
        val temporary = File(file.parentFile, "${file.name}.part")
        require(!file.exists() && !temporary.exists()) { "Refusing to replace probe artifact" }
        try {
            FileOutputStream(temporary).use { stream ->
                stream.write(payload.toByteArray(StandardCharsets.UTF_8))
                stream.fd.sync()
            }
            if (android.os.Build.VERSION.SDK_INT >= 26) {
                Files.move(temporary.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE)
            } else {
                require(temporary.renameTo(file)) { "Cannot finalize probe artifact" }
            }
        } catch (error: Throwable) {
            temporary.delete()
            throw error
        }
        require(file.readBytes().contentEquals(payload.toByteArray(StandardCharsets.UTF_8))) {
            "Probe artifact readback mismatch"
        }
    }

    internal fun json(value: Any?): String = jsonValue(value).toString()

    private fun jsonValue(value: Any?): Any = when (value) {
        null -> JSONObject.NULL
        is Map<*, *> -> JSONObject().apply {
            value.forEach { (key, nested) -> put(key.toString(), jsonValue(nested)) }
        }
        is Iterable<*> -> JSONArray().apply { value.forEach { put(jsonValue(it)) } }
        is IntArray -> JSONArray().apply { value.forEach { put(it) } }
        is LongArray -> JSONArray().apply { value.forEach { put(it) } }
        is FloatArray -> JSONArray().apply { value.forEach { put(it) } }
        else -> value
    }
}
