package com.example.d1check.qualityrunner

/*
 * Q20 계약 — d1sim/docs/품질20장_사전등록_v1.md (blob 48b59382…) §1 · §2 의 값만 상수로 둔다.
 *   §1: 입력 = little-endian float32 · NHWC · [1,224,224,3] = 602,112 B · 받은 그대로 (resize · 정규화 다시 안 함).
 *   §2: backend 마다 이미지마다 2회 (같은 입력 반복 — 두 출력 비트 같은지 기록) · 출력 = Softmax [1,1000] 그대로 (변환 없음).
 *   §3: 지표 · 판정은 앱이 아니라 호스트 판정기 (s26/tools/quality20/q20_judge.py, 결과 전 커밋) 가 한다 — 앱은 raw 출력 · SHA · finite 만 적는다.
 */
object QualityContract {
    const val PROTOCOL = "s26-q20-manifest-v1"
    const val SUMMARY_SCHEMA = "s26-q20-summary-v1"
    const val RESULT_SCHEMA = "s26-q20-image-result-v1"
    const val LOG_TAG = "D1Q20"
    const val TASK = "classification"
    const val INPUT_ELEMENTS = 224 * 224 * 3
    const val INPUT_BYTES = INPUT_ELEMENTS * 4          // 602,112
    const val OUTPUT_ELEMENTS = 1000
    const val RUNS_PER_IMAGE = 2
    const val SAMPLE_COUNT = 20
    /** 호스트 상한 15 분 (프롬프트 1-4) 보다 짧게 — 앱이 먼저 끝나야 호스트가 pull 한다. */
    const val WATCHDOG_MS = 840_000L
    val BACKENDS = listOf("CPU", "GPU", "NPU")

    fun keyOf(backend: String): String = "${TASK}_$backend"
}
