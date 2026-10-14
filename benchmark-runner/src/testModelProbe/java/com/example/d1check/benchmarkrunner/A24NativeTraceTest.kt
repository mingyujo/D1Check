package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.util.UUID

/** Native Kotlin scheduler traces for independent host replay. No adapter is instantiated. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[34])
class A24NativeTraceTest {
    @Test fun nativePairAndWaitTracesPreserveAll128Requests() {
        for(arm in listOf("PAIR_G","WAIT200")) trace(arm)
    }
    private fun trace(arm:String) {
        val t0 = 1_000_000_000_000L
        val sid = UUID.nameUUIDFromBytes("NATIVE_MOCK_$arm".toByteArray()).toString()
        val requests = List(128) { i ->
            val task = if(i%8 in setOf(3,7)) "D" else "C"
            val at = 35_000_000_000L+i/8*2_032_200_000L
            A24PreparationContract.Request(UUID.nameUUIDFromBytes("NATIVE-$i".toByteArray()).toString(),i,task,
                at,at+if(task=="C") 2_200_000_000L else 5_000_000_000L,i/8)
        }
        val p = A24PreparationContract.Prescription("M128","FIFO","C_GPU_D_CPU",if(arm=="PAIR_G") "CG_DC" else "SERIAL",if(arm=="WAIT200") 200 else 0)
        val core = A24PreparationScheduler(p,requests)
        val events = mutableListOf<Map<String,Any?>>()
        val rows = requests.associate { q -> q.id to linkedMapOf<String,Any?>("request_id" to q.id,"ordinal" to q.ordinal,
            "task" to q.task,"scheduled_arrival_ns" to t0+q.arrivalNs,"deadline_ns" to t0+q.deadlineNs,"terminal_status" to "UNFINISHED") }
        fun emit(kind:String, at:Long, data:Map<String,Any?> = emptyMap()) {
            events+=data+mapOf("kind" to kind,"mono_ns" to t0+at,"sequence" to events.size,"session_id" to sid)
        }
        emit("runtime_ready",-1,mapOf("key" to "C_GPU","mock" to true))
        emit("common_start",0,mapOf("origin_ns" to t0,"evidence_level" to "SOFTWARE_MOCK_DEVICE_UNVERIFIED"))
        var next = 0
        val finishes = mutableListOf<Triple<Long,String,String>>()
        var elapsed = 0L
        while(next < requests.size || finishes.isNotEmpty() || core.waiting().isNotEmpty()) {
            elapsed = minOf(requests.getOrNull(next)?.arrivalNs ?: Long.MAX_VALUE,
                finishes.minOfOrNull { it.first } ?: Long.MAX_VALUE,core.wait?.endNs ?: Long.MAX_VALUE)
            while(next < requests.size && requests[next].arrivalNs <= elapsed) {
                val q = requests[next++]; val row = rows.getValue(q.id)
                row["actual_arrival_ns"] = t0+elapsed
                emit("arrival",elapsed,mapOf("request_id" to q.id,"scheduled_arrival_ns" to t0+q.arrivalNs,"actual_arrival_ns" to t0+elapsed))
                core.enqueue(q.id,elapsed); row["queue_entry_ns"] = t0+elapsed
                emit("queue_entry",elapsed,mapOf("request_id" to q.id,"queue_entry_ns" to t0+elapsed))
            }
            val done = finishes.filter { it.first <= elapsed }; finishes.removeAll(done.toSet())
            for((finish,id,backend) in done) {
                val row = rows.getValue(id)
                row["output_ready_ns"] = t0+finish; emit("output_ready",finish,mapOf("request_id" to id,"output_ready_ns" to t0+finish))
                for(kind in listOf("persist_write","persist_flush","persist_fsync","persist_rename","persist_readback"))
                    emit(kind,finish,mapOf("request_id" to id,"completed_ns" to t0+finish))
                row["persist_complete_ns"] = t0+finish
                row["worker_release_ns"] = t0+finish
                emit("worker_release",finish,mapOf("request_id" to id,"backend" to backend,"worker_release_ns" to t0+finish))
                // Worker-return marker is represented by this separate core callback.
                core.available(id,backend); row["lane_available_ns"] = t0+finish; row["terminal_status"] = "COMPLETED"
                emit("lane_available",finish,mapOf("request_id" to id,"backend" to backend,"lane_available_ns" to t0+finish))
            }
            core.wait?.takeIf { it.endNs <= elapsed }?.let { wait ->
                core.endWait(elapsed)
                emit("wait_end",elapsed,mapOf("group" to wait.group,"planned_wait_ns" to A24PreparationContract.WAIT_NS,
                    "planned_start_ns" to t0+wait.startNs,"planned_end_ns" to t0+wait.endNs,"actual_end_ns" to t0+elapsed,
                    "waiting" to core.waiting(),"owners" to core.owners(),"cut_by_service_stop" to false))
            }
            while(true) when(val action = core.select(elapsed)) {
                null -> break
                is A24PreparationScheduler.Action.Wait -> {
                    emit("wait_start",elapsed,mapOf("group" to action.group,"planned_wait_ns" to A24PreparationContract.WAIT_NS,
                        "planned_start_ns" to t0+action.startNs,"planned_end_ns" to t0+action.endNs,"actual_start_ns" to t0+elapsed,
                        "waiting" to core.waiting(),"owners" to core.owners()))
                    break
                }
                is A24PreparationScheduler.Action.Dispatch -> {
                    val row = rows.getValue(action.request.id); row["backend"] = action.backend; row["dispatch_ns"] = t0+elapsed
                    row["execution_start_ns"] = t0+elapsed
                    emit("dispatch",elapsed,mapOf("request_id" to action.request.id,"backend" to action.backend,"dispatch_ns" to t0+elapsed))
                    emit("execution_start",elapsed,mapOf("request_id" to action.request.id,"execution_start_ns" to t0+elapsed))
                    finishes+=Triple(elapsed+50_000_000L,action.request.id,action.backend)
                }
            }
            assertTrue(elapsed < A24PreparationContract.SERVICE_NS)
        }
        core.stopDispatch(); emit("dispatch_stop",A24PreparationContract.SERVICE_NS,mapOf("planned_stop_ns" to t0+A24PreparationContract.SERVICE_NS))
        emit("logging_end",A24PreparationContract.LOGGING_NS,mapOf("planned_sensor_end_ns" to t0+A24PreparationContract.LOGGING_NS))
        assertEquals(128,core.dispatchCount()); assertTrue(core.owners().values.all { it==null })
        val manifest = mapOf("protocol" to A24PreparationContract.PROTOCOL,"session_id" to sid,"recipe" to "M128","order" to p.order,
            "route" to p.route,"concurrency" to p.concurrency,"wait_ms" to p.waitMs,"m128_delta_ns" to 2_032_200_000L,
            "nominal_profile_sha256" to "0".repeat(64),"service_cutoff_ns" to A24PreparationContract.SERVICE_NS,
            "sensor_end_ns" to A24PreparationContract.LOGGING_NS,"mock" to true,"device_status" to "DEVICE_UNVERIFIED",
            "evidence_level" to "SOFTWARE_MOCK_DEVICE_UNVERIFIED","requests" to requests.map { q -> mapOf("request_id" to q.id,"ordinal" to q.ordinal,
                "task" to q.task,"scheduled_arrival_ns" to q.arrivalNs,"relative_deadline_ns" to q.deadlineNs-q.arrivalNs,"deadline_ns" to q.deadlineNs,
                "group" to q.group,"input_file" to null,"input_sha256" to null,"tensor_sha256" to null) })
        val root = File("build/a24PreparationMock/$arm").apply { mkdirs() }
        File(root,"session_manifest.json").writeText(ModelProbeArtifacts.json(manifest),Charsets.UTF_8)
        File(root,"requests.json").writeText(ModelProbeArtifacts.json(requests.map { rows.getValue(it.id) }),Charsets.UTF_8)
        File(root,"events.jsonl").writeText(events.joinToString("\n",postfix="\n") { ModelProbeArtifacts.json(it) },Charsets.UTF_8)
    }
}
