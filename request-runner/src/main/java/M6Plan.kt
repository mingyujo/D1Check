package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request

/**
 * M6 요청표 — d1sim/docs/M6_동일APK_사전등록_v3.md (SHA-256 b57b8957…) §3-2 · §3-5 · §4-1.
 *   P (S26-M6-P · -SMOKE): 100건 = 분류 urgent 50 · 탐지 normal 50 · 기한 1,500 / 6,000 ms · 시각 = 공통창 원점 기준
 *     L 낮은 혼합: i = 0..99 · offset 35,000 + 400·i · 짝 = 분류 · 홀 = 탐지
 *     B 밀집 · 버스트: k = 0..9 · j = 0..9 · i = 10k + j · offset 35,000 + 4,000·k + 50·j · j 짝 = 분류 · 홀 = 탐지
 *     index → (부하, 규칙) = ORDER (개발 D 0..5: L-C · B-G · L-N · B-C · L-G · B-N / 확인 K 6..11: B-N · L-G · B-C · L-N · B-G · L-C).
 *     스모크 ID 도 같은 ORDER 를 쓴다 (index 3 = B-C).
 *   K (S26-M6-K · -SMOKE): 요청 0 (빈 표).
 * ordinal = i (offset 오름차순) · request_id = uuid5(sid/ordinal) (RequestPlan.requestId 그대로).
 * 호스트 s26/tools/mixreq/m6_common.py 가 같은 식으로 만들고, 앱은 manifest 의 표 · 정책이 이 식과 같은지 다시 확인한다 (fail closed).
 */
object M6Plan {
    const val REQUEST_COUNT = 100
    const val LOAD_L = "L"
    const val LOAD_B = "B"
    val LETTER_POLICY = mapOf(
        "C" to MixreqContract.POLICY_CPU,
        "G" to MixreqContract.POLICY_PAR,
        "N" to MixreqContract.POLICY_PAR_NPU,
    )

    /** 등록 §3-5 (거울 · 결과 전 고정). index → "부하-규칙". */
    val ORDER = listOf("L-C", "B-G", "L-N", "B-C", "L-G", "B-N", "B-N", "L-G", "B-C", "L-N", "B-G", "L-C")

    fun isP(experimentId: String) = experimentId == MixreqContract.M6_P_EXPERIMENT_ID || experimentId == MixreqContract.M6_P_SMOKE_EXPERIMENT_ID
    fun isK(experimentId: String) = experimentId == MixreqContract.M6_K_EXPERIMENT_ID || experimentId == MixreqContract.M6_K_SMOKE_EXPERIMENT_ID

    fun loadOf(index: Int): String = ORDER[index].substringBefore('-')
    fun policyOf(index: Int): String = LETTER_POLICY.getValue(ORDER[index].substringAfter('-'))

    /** (task, offset) 슬롯 — ordinal 순서. */
    fun slots(load: String): List<Pair<String, Long>> = when (load) {
        LOAD_L -> List(REQUEST_COUNT) { i -> (if (i % 2 == 0) "classification" else "detection") to (35_000L + 400L * i) }
        LOAD_B -> List(REQUEST_COUNT) { i ->
            val k = i / 10
            val j = i % 10
            (if (j % 2 == 0) "classification" else "detection") to (35_000L + 4_000L * k + 50L * j)
        }
        else -> error("unknown load $load")
    }

    fun loadRequests(sid: String, load: String): List<Request> = slots(load).mapIndexed { ordinal, (task, offset) ->
        val urgent = task == "classification"
        Request(
            id = RequestPlan.requestId(sid, ordinal),
            ordinal = ordinal,
            task = task,
            priority = if (urgent) "urgent" else "normal",
            offsetMs = offset,
            deadlineMs = if (urgent) MixreqContract.URGENT_DEADLINE_MS else MixreqContract.NORMAL_DEADLINE_MS,
        )
    }.also { validateLoad(it, load) }

    /** (experimentId, index) 에서 유도한 표. K = 빈 표. */
    fun requests(experimentId: String, index: Int, sid: String): List<Request> = when {
        isP(experimentId) -> loadRequests(sid, loadOf(index))
        isK(experimentId) -> emptyList()
        else -> error("not an M6 experiment $experimentId")
    }

    /** 요청 수 100 · ID 유일 · ordinal 순서 · (task, offset) 이 부하 식과 정확히 같음 · 우선순위 · 기한 · 분류 50 / 탐지 50. */
    fun validateLoad(requests: List<Request>, load: String) {
        val expected = slots(load)
        require(requests.size == REQUEST_COUNT && requests.map { it.id }.toSet().size == REQUEST_COUNT) { "m6 request count/id" }
        require(expected.map { it.second }.zipWithNext().all { (a, b) -> a < b }) { "m6 offsets must increase" }
        require(expected.count { it.first == "classification" } == 50) { "m6 classification count" }
        requests.forEachIndexed { i, q ->
            val urgent = q.task == "classification"
            require(q.ordinal == i && q.task == expected[i].first && q.offsetMs == expected[i].second) { "m6 request $i task/offset" }
            require(q.priority == (if (urgent) "urgent" else "normal")) { "m6 request $i priority" }
            require(q.deadlineMs == (if (urgent) MixreqContract.URGENT_DEADLINE_MS else MixreqContract.NORMAL_DEADLINE_MS)) { "m6 request $i deadline" }
        }
    }

    /** SessionManifest.validate 의 M6 분기: 블록 M · 정책 = ORDER (P) · 요청표 꼴 (P = 부하 식 · K = 0). */
    fun validateSession(experimentId: String, index: Int, block: String, policy: String, requests: List<Request>) {
        require(block == MixreqContract.BLOCK_M) { "M6 sessions run in block M only (block $block)" }
        when {
            isP(experimentId) -> {
                require(index in ORDER.indices) { "m6 index $index" }
                require(policy == policyOf(index)) { "m6 index $index is ${ORDER[index]} (policy ${policyOf(index)}), manifest policy $policy" }
                validateLoad(requests, loadOf(index))
            }
            isK(experimentId) -> {
                require(policy == MixreqContract.POLICY_CPU) { "m6 K policy label must be ${MixreqContract.POLICY_CPU}" }
                require(requests.isEmpty()) { "m6 K has no requests" }
            }
            else -> error("not an M6 experiment $experimentId")
        }
    }
}
