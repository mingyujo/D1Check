package com.example.d1check.contract

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class DiagnosticRecordIdentityTest {
    @Test
    fun everyV2RecordKindReceivesCompleteTraceIdentity() {
        val identity = DiagnosticRecordIdentity(
            2,
            "33333333-3333-3333-3333-333333333333",
            "on",
        )
        val records = listOf(
            "run_metadata", "warmup", "load_start", "inference",
            "diagnostic_trace_start", "load_end", "file_summary",
        ).map { event -> mutableMapOf<String, Any?>("event" to event) }

        records.forEach(identity::applyTo)

        records.forEach { record ->
            assertEquals(2, record["protocol_version"])
            assertEquals(identity.diagnosticSessionId, record["diagnostic_session_id"])
            assertEquals("on", record["requested_trace_mode"])
        }
    }

    @Test
    fun v1RecordsRemainSchemaUnchanged() {
        val record = mutableMapOf<String, Any?>("event" to "file_summary")

        DiagnosticRecordIdentity(null, null, null).applyTo(record)

        assertFalse(record.containsKey("protocol_version"))
        assertFalse(record.containsKey("diagnostic_session_id"))
        assertFalse(record.containsKey("requested_trace_mode"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun incompleteV2IdentityIsRejected() {
        DiagnosticRecordIdentity(2, "33333333-3333-3333-3333-333333333333", null)
    }
}
