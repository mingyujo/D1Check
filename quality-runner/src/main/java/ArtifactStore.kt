package com.example.d1check.qualityrunner

import java.io.File
import java.io.FileOutputStream

// ★ 사본 — request-runner/src/main/java/EventLog.kt (s26-mixreq e2bedf1 · blob b9c88e3b1ba432167510cdb1b9dcd4d694e5e95b) 의 ArtifactStore 만
//   (A24 ArrivalEnergyActivity.save: <name>.part 에 쓰고 fsync → rename · 덮어쓰기 거부). ProgressWriter 는 Q20 에 없다 (직렬 실행 · lane 0).
/** 원자 저장: <name>.part 에 쓰고 fsync → rename. 같은 이름이 있으면 거부 (A24 save). */
class ArtifactStore(val root: File) {
    fun save(name: String, value: Any?) = saveBytes(name, Json.encode(value).toByteArray(Charsets.UTF_8))

    fun saveBytes(name: String, bytes: ByteArray) {
        val output = File(root, name)
        val temp = File(root, "$name.part")
        check(!output.exists() && temp.createNewFile()) { "artifact exists or .part not creatable: $name" }
        FileOutputStream(temp).use {
            it.write(bytes)
            it.fd.sync()
        }
        check(temp.renameTo(output)) { "rename failed: $name" }
    }
}
