package com.example.d1check.requestrunner

/*
 * 출처: feature/arrival-scheduling-20260923 @ d588323
 *   benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalPolicyStudy.kt 50~62행 (choose)
 *   benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalPolicy.kt 10~11행 (Ticket · Choice)
 * 바꾼 것: lane 에 NPU 를 추가하고 정책 S26_NPU_PARALLEL_V1 (분류 → NPU · 탐지 → CPU) 을 넣었다 (등록 §2).
 * CPU · PAR 의 선택 규칙은 원문 그대로다: 비선점 · 큐에 든 것만 · urgent 먼저 → ordinal → id ·
 * CPU 정책은 CPU · GPU lane 이 둘 다 비었을 때만 고른다 (사실상 CPU lane 하나 직렬).
 */
object PolicyStudy {
    const val REASON = "online_arrived_priority_then_ordinal"

    data class Ticket(val id: String, val task: String, val priority: String, val ordinal: Int)
    data class Choice(val ticket: Ticket, val backend: String, val reason: String)

    fun choose(
        policy: String,
        waiting: List<Ticket>,
        freeCpu: Boolean,
        freeGpu: Boolean,
        freeNpu: Boolean = true,
    ): Choice? {
        require(policy in MixreqContract.POLICIES) { "unknown policy $policy" }
        // A24: if ((policy == CPU || policy == SERIAL) && (!freeCpu || !freeGpu)) return null
        if (policy == MixreqContract.POLICY_CPU && (!freeCpu || !freeGpu)) return null
        val ordered = waiting.sortedWith(
            compareBy<Ticket> { it.priority != "urgent" }.thenBy { it.ordinal }.thenBy { it.id },
        )
        for (q in ordered) {
            val lane = laneFor(policy, q.task)
            val free = when (lane) {
                "CPU" -> freeCpu
                "GPU" -> freeGpu
                else -> freeNpu
            }
            if (free) return Choice(q, lane, REASON)
        }
        return null
    }

    /** 등록 §2 배정: CPU 정책 → 전부 CPU · PAR → 분류 GPU / 탐지 CPU · PAR-NPU → 분류 NPU / 탐지 CPU. */
    fun laneFor(policy: String, task: String): String = when {
        policy == MixreqContract.POLICY_CPU || task == "detection" -> "CPU"
        policy == MixreqContract.POLICY_PAR -> "GPU"
        policy == MixreqContract.POLICY_PAR_NPU -> "NPU"
        else -> error("unknown policy $policy")
    }
}
