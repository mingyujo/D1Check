package com.example.d1check.benchmarkrunner

import org.json.JSONObject
import java.io.File
import java.util.UUID

internal data class A24PreparationInput(val filename: String, val sha256: String, val tensorSha256: String)
internal data class A24PreparationManifest(
    val json: JSONObject, val sessionId: String, val prescription: A24PreparationContract.Prescription,
    val requests: List<A24PreparationContract.Request>, val inputs: Map<String,A24PreparationInput>,
) {
    companion object {
        fun parse(root: JSONObject): A24PreparationManifest {
            require(root.getString("protocol") == A24PreparationContract.PROTOCOL)
            val id = root.getString("session_id")
            require(UUID.fromString(id).toString() == id)
            require(root.getLong("service_cutoff_ns") == A24PreparationContract.SERVICE_NS)
            require(root.getLong("sensor_end_ns") == A24PreparationContract.LOGGING_NS)
            val p = A24PreparationContract.Prescription(root.getString("recipe"),root.getString("order"),
                root.getString("route"),root.getString("concurrency"),root.getInt("wait_ms"))
            val arr = root.getJSONArray("requests")
            val inputs = linkedMapOf<String,A24PreparationInput>()
            val requests = (0 until arr.length()).map { i ->
                val q = arr.getJSONObject(i)
                val arrival = q.getLong("scheduled_arrival_ns")
                val relative = q.getLong("relative_deadline_ns")
                val deadline = q.getLong("deadline_ns")
                require(deadline == arrival+relative)
                val requestId = q.getString("request_id")
                require(UUID.fromString(requestId).toString() == requestId)
                val filename = q.getString("input_file")
                require(filename.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,126}")))
                fun hash(key:String) = q.getString(key).also { require(it.matches(Regex("[0-9a-f]{64}"))) }
                inputs[requestId] = A24PreparationInput(filename,hash("input_sha256"),hash("tensor_sha256"))
                A24PreparationContract.Request(requestId,q.getInt("ordinal"),q.getString("task"),arrival,deadline,q.getInt("group"))
            }
            A24PreparationContract.validate(p,requests)
            return A24PreparationManifest(root,id,p,requests,inputs)
        }
        fun safeFile(parent: File, name: String): File {
            require(name.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,126}")))
            val root = parent.canonicalFile
            val file = File(root,name)
            require(file.absoluteFile == file.canonicalFile && file.parentFile == root && file.isFile)
            return file
        }
    }
}
