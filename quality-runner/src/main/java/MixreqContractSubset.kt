package com.example.d1check.qualityrunner

/*
 * ★ 사본 (부분) — request-runner/src/main/java/MixreqContract.kt (s26-mixreq e2bedf1 · blob 8797d7aeac079c299efe1dc2bca1f40969cae159) 에서
 *   Runtimes.kt 사본이 참조하는 다섯 가지 (LANES · ENGINE · LITERT_VERSION · laneOf · taskOf) 만 같은 이름 · 같은 코드로 가져왔다.
 *   혼합 요청의 요청표 · 정책 · 블록 상수는 Q20 에 없다. Runtimes.kt 를 한 글자도 바꾸지 않기 위한 파일이다.
 */
object MixreqContract {
    val LANES = listOf("CPU", "GPU", "NPU")
    const val ENGINE = "litert-compiled-model"
    const val LITERT_VERSION = "2.2.0"

    /** "classification_GPU" -> "GPU". lane 이름 = runtime 키의 마지막 토큰. */
    fun laneOf(key: String): String = key.substringAfterLast('_').also { require(it in LANES) { "unknown lane in $key" } }

    fun taskOf(key: String): String = key.substringBeforeLast('_')
}
