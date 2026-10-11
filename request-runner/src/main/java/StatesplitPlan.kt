package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request

/**
 * M5 상태 분리 요청열 — d1sim/docs/상태분리_사전등록_v2.md §1 (SHA-256 717bc4e5…). 구간 시각은 첫 offset 35 s 기준
 * (공통창 시각 35 ~ 155 s → 요청은 35.0 ~ 119.9 s 로 공통창 120 s 안, S4 쉼 = drain + 냉각 앞부분):
 *   S1 분류 urgent 35,000 + 100·i (250) · S2 탐지 normal 65,000 + 300·j (84) ·
 *   S3 분류 urgent 95,000 + 200·k (125) + 탐지 normal 95,100 + 400·m (63) · S4 없음.
 * ordinal = offset 오름차순 (같은 offset 없음) · request_id = uuid5(sid/ordinal) (RequestPlan.requestId 그대로) · 기한 = 기존 1,500 / 6,000.
 * 호스트 s26/tools/mixreq/statesplit_common.py 가 같은 식으로 만들고, 앱은 manifest 의 표가 이 식과 같은지 다시 확인한다 (fail closed).
 */
object StatesplitPlan {
    data class Segment(val name: String, val task: String, val firstOffsetMs: Long, val stepMs: Long, val count: Int)

    val SEGMENTS = listOf(
        Segment("S1", "classification", 35_000L, 100L, 250),
        Segment("S2", "detection", 65_000L, 300L, 84),
        Segment("S3", "classification", 95_000L, 200L, 125),
        Segment("S3", "detection", 95_100L, 400L, 63),
    )
    const val REQUEST_COUNT = 522

    fun requests(sid: String): List<Request> {
        val slots = SEGMENTS.flatMap { s -> List(s.count) { i -> s.task to (s.firstOffsetMs + i * s.stepMs) } }.sortedBy { it.second }
        return slots.mapIndexed { ordinal, (task, offset) ->
            val urgent = task == "classification"
            Request(
                id = RequestPlan.requestId(sid, ordinal),
                ordinal = ordinal,
                task = task,
                priority = if (urgent) "urgent" else "normal",
                offsetMs = offset,
                deadlineMs = if (urgent) MixreqContract.URGENT_DEADLINE_MS else MixreqContract.NORMAL_DEADLINE_MS,
            )
        }.also { validateRequests(it) }
    }

    /** 요청 수 522 · ID 유일 · ordinal 순서 · (task, offset) 이 구간 표와 정확히 같음 · 우선순위 · 기한. */
    fun validateRequests(requests: List<Request>) {
        require(requests.size == REQUEST_COUNT && requests.map { it.id }.toSet().size == REQUEST_COUNT) { "statesplit request count/id" }
        val expected = SEGMENTS.flatMap { s -> List(s.count) { i -> s.task to (s.firstOffsetMs + i * s.stepMs) } }.sortedBy { it.second }
        require(expected.map { it.second }.toSet().size == REQUEST_COUNT) { "statesplit offsets must be unique" }
        requests.forEachIndexed { i, q ->
            val urgent = q.task == "classification"
            require(q.ordinal == i && q.task == expected[i].first && q.offsetMs == expected[i].second) { "statesplit request $i task/offset" }
            require(q.priority == (if (urgent) "urgent" else "normal")) { "statesplit request $i priority" }
            require(q.deadlineMs == (if (urgent) MixreqContract.URGENT_DEADLINE_MS else MixreqContract.NORMAL_DEADLINE_MS)) { "statesplit request $i deadline" }
        }
    }
}
