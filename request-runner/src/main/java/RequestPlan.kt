package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request

/**
 * 요청표 생성 — 등록 §1-1: sid = uuid5(NAMESPACE_URL, 'S26-MIXREQ-01/' + 세션 index) ·
 * request_id = uuid5(NAMESPACE_URL, sid + '/' + ordinal). A24 와 네임스페이스 문자열만 다르다
 * (A24: 'SUSTAINED-CPU-PAR-CONFIRM-01/' — tools/d1_sustained_plan.py 85~87행 · d1_sustained_protocol.requests 12~16행).
 * 호스트 mixreq_plan.py 가 같은 식으로 만들고, 앱은 manifest 의 표가 이 식과 같은지 다시 확인한다 (fail closed).
 */
object RequestPlan {
    fun sessionId(experimentId: String, index: Int): String =
        Uuid5.uuid5(Uuid5.NAMESPACE_URL, "$experimentId/$index").toString()

    fun requestId(sid: String, ordinal: Int): String =
        Uuid5.uuid5(Uuid5.NAMESPACE_URL, "$sid/$ordinal").toString()

    fun requests(sid: String, count: Int = MixreqContract.REQUEST_COUNT): List<Request> = List(count) { i ->
        val urgent = i % 2 == 0
        Request(
            id = requestId(sid, i),
            ordinal = i,
            task = if (urgent) "classification" else "detection",
            priority = if (urgent) "urgent" else "normal",
            offsetMs = MixreqContract.FIRST_OFFSET_MS + i * MixreqContract.STEP_MS,
            deadlineMs = if (urgent) MixreqContract.URGENT_DEADLINE_MS else MixreqContract.NORMAL_DEADLINE_MS,
        )
    }.also { MixreqContract.validateRequests(it, count) }

    /** manifest 의 표가 (experimentId, index) 에서 유도한 표와 완전히 같은지. */
    fun requireDerived(experimentId: String, index: Int, sid: String, requests: List<Request>) {
        require(sessionId(experimentId, index) == sid) { "session_id is not uuid5($experimentId/$index)" }
        val expected = requests(sid, requests.size)
        require(expected == requests) { "request table differs from the uuid5 derivation" }
    }
}
