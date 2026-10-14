package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test
import java.util.UUID

class A24PreparationSchedulerTest {
    private fun requests(recipe:String): List<A24PreparationContract.Request> {
        val n = when(recipe) { "L64" -> 64; "C252" -> 252; else -> 128 }
        return List(n) { i ->
            val task = when(recipe) { "C252" -> "C"; "L64" -> if(i%2==0) "C" else "D"; else -> if(i%8 in setOf(3,7)) "D" else "C" }
            val arrival = 35_000_000_000L+when(recipe) { "L64" -> i*1_000_000_000L; "C252" -> i*333_200_000L; else -> i/8*2_032_200_000L }
            A24PreparationContract.Request(UUID.nameUUIDFromBytes("$recipe-$i".toByteArray()).toString(),i,task,arrival,
                arrival+if(task == "C") 2_200_000_000L else 5_000_000_000L,if(recipe == "M128") i/8 else -1)
        }
    }
    private fun scheduler(recipe:String="M128", order:String="FIFO", route:String="C_GPU_D_CPU", pair:Boolean=false, wait:Int=0) =
        A24PreparationScheduler(A24PreparationContract.Prescription(recipe,order,route,if(pair) "CG_DC" else "SERIAL",wait),requests(recipe))
    private fun expectIllegal(block:()->Unit) {
        try { block(); fail("must reject") } catch(_:IllegalArgumentException) { } catch(_:IllegalStateException) { }
    }
    @Test fun noFutureArrivalAndNoDuplicateArrival() {
        val s = scheduler(); val first = s.requests.first()
        expectIllegal { s.enqueue(first.id,first.arrivalNs-1) }
        assertEquals(emptyList<String>(),s.waiting())
        s.enqueue(first.id,first.arrivalNs)
        expectIllegal { s.enqueue(first.id,first.arrivalNs) }
    }
    @Test fun eddActuallyChangesOrderWithFifoTies() {
        val fifo = scheduler(); val edd = scheduler(order="EDD")
        for(s in listOf(fifo,edd)) s.requests.take(8).forEach { s.enqueue(it.id,35_000_000_000L) }
        fun drain(s:A24PreparationScheduler):List<Int> {
            val out = mutableListOf<Int>()
            repeat(8) {
                val a = s.select(35_000_000_000L) as A24PreparationScheduler.Action.Dispatch
                out+=a.request.ordinal; s.available(a.request.id,a.backend)
            }
            return out
        }
        assertEquals((0..7).toList(),drain(fifo))
        assertEquals(listOf(0,1,2,4,5,6,3,7),drain(edd))
    }
    @Test fun serialWaitsForActualAvailableNotOutputOrWorkerRelease() {
        val s = scheduler(); s.requests.take(8).forEach { s.enqueue(it.id,35_000_000_000L) }
        val a = s.select(35_000_000_000L) as A24PreparationScheduler.Action.Dispatch
        // output and worker-release are intentionally not ownership-changing API calls
        assertNull(s.select(35_500_000_000L)); assertEquals(a.request.id,s.owners()["GPU"])
        expectIllegal { s.available("some_other_request","GPU") }
        s.available(a.request.id,a.backend)
        assertNotNull(s.select(35_500_000_000L))
    }
    @Test fun pairAllowsOnlyCgDcAndRetainsStrictFifoHead() {
        val s = scheduler(pair=true); s.requests.take(8).forEach { s.enqueue(it.id,35_000_000_000L) }
        repeat(2) {
            val a = s.select(35_000_000_000L) as A24PreparationScheduler.Action.Dispatch
            assertEquals(it,a.request.ordinal); assertNull(s.select(35_000_000_000L))
            s.available(a.request.id,a.backend)
        }
        val c = s.select(35_000_000_000L) as A24PreparationScheduler.Action.Dispatch
        val d = s.select(35_000_000_000L) as A24PreparationScheduler.Action.Dispatch
        assertEquals("C",c.request.task); assertEquals("GPU",c.backend)
        assertEquals("D",d.request.task); assertEquals("CPU",d.backend)
        assertEquals(2,s.owners().values.count { it!=null }); assertNull(s.select(35_000_000_000L))
        expectIllegal { scheduler(pair=true,route="C_CPU") }
    }
    @Test fun waitTimerCannotBeReleasedByNewArrivalsAndDoseIsOncePerGroup() {
        val s = scheduler(wait=200); val t = 35_000_000_000L
        s.enqueue(s.requests[0].id,t)
        val wait = s.select(t) as A24PreparationScheduler.Action.Wait
        assertEquals(200_000_000L,wait.endNs-wait.startNs)
        s.enqueue(s.requests[1].id,t)
        assertNull(s.select(t+199_000_000L)); expectIllegal { s.endWait(t+199_000_000L) }
        s.endWait(t+200_000_000L)
        val first = s.select(t+200_000_000L) as A24PreparationScheduler.Action.Dispatch
        s.available(first.request.id,first.backend)
        assertTrue(s.select(t+400_000_000L) is A24PreparationScheduler.Action.Dispatch)
    }
    @Test fun plannedDenominatorAndServiceCutoffPreserved() {
        for(recipe in listOf("L64","C252","M128")) {
            val s = scheduler(recipe); assertEquals(requests(recipe).size,s.requests.size)
            s.enqueue(s.requests[0].id,35_000_000_000L)
            assertNull(s.select(A24PreparationContract.SERVICE_NS))
            assertEquals(1,s.waiting().size); assertEquals(0,s.dispatchCount())
            s.stopDispatch(); assertNull(s.select(35_000_000_000L))
        }
    }
    @Test fun selectionCrossingCutoffReturnsUnsubmittedRequestWithoutLosingWork() {
        val s = scheduler(); s.requests.take(8).forEach { s.enqueue(it.id,35_000_000_000L) }
        val before = s.waiting()
        val selected = s.select(A24PreparationContract.SERVICE_NS-1) as A24PreparationScheduler.Action.Dispatch
        assertEquals(1,s.dispatchCount()); assertEquals(selected.request.id,s.owners()["GPU"])
        // The Activity captures actual commit >=120s before worker submission.
        s.rollbackUnsubmitted(selected); s.stopDispatch()
        assertEquals(before,s.waiting()); assertEquals(0,s.dispatchCount())
        assertTrue(s.owners().values.all { it==null }); assertEquals(128,s.requests.size)
        assertNull(s.select(A24PreparationContract.SERVICE_NS))
        expectIllegal { s.rollbackUnsubmitted(selected) }
    }
    @Test fun cpuRouteAndTruncatedWaitAreExact() {
        val s = scheduler(recipe="C252",route="C_CPU")
        s.enqueue(s.requests[0].id,35_000_000_000L)
        assertEquals("CPU",(s.select(35_000_000_000L) as A24PreparationScheduler.Action.Dispatch).backend)
        val w = scheduler(wait=200); w.enqueue(w.requests[0].id,119_900_000_000L)
        val wait = w.select(119_900_000_000L) as A24PreparationScheduler.Action.Wait
        assertEquals(A24PreparationContract.SERVICE_NS,wait.endNs)
        w.endWait(wait.endNs); w.stopDispatch(); assertNull(w.select(wait.endNs))
    }
    @Test fun allFourResidentKeysMapToTheExactTaskAndBackend() {
        val expected = mapOf("C_CPU" to ("classification" to "CPU"), "C_GPU" to ("classification" to "GPU"),
            "D_CPU" to ("detection" to "CPU"), "D_GPU" to ("detection" to "GPU"))
        assertEquals(expected.keys,A24PreparationContract.RUNTIME_KEYS.toSet())
        expected.forEach { (key,value) ->
            A24PreparationContract.validateRuntimeMapping(key,value.first,value.second)
            expectIllegal { A24PreparationContract.validateRuntimeMapping(key,if(value.first == "classification") "detection" else "classification",value.second) }
            expectIllegal { A24PreparationContract.validateRuntimeMapping(key,value.first,if(value.second == "CPU") "GPU" else "CPU") }
        }
        expectIllegal { A24PreparationContract.runtimeTask("classification_CPU") }
        expectIllegal { A24PreparationContract.runtimeBackend("C_NPU") }
    }
    @Test fun instrumentationC32IsClassificationGpuOnlyAndCannotUseBadArrivals() {
        val p = A24PreparationContract.Prescription("I_C32","FIFO","C_GPU_D_CPU","SERIAL",0)
        val qs = requests("C252").take(32).mapIndexed { i,r -> r.copy(arrivalNs=35_000_000_000L+i*1_000_000_000L,
            deadlineNs=37_200_000_000L+i*1_000_000_000L) }
        A24PreparationContract.validate(p,qs)
        expectIllegal { A24PreparationContract.validate(p,qs.mapIndexed { i,r -> if(i==0) r.copy(task="D") else r }) }
        expectIllegal { A24PreparationContract.validate(p.copy(route="C_CPU"),qs) }
        expectIllegal { A24PreparationContract.validate(p,qs.mapIndexed { i,r -> if(i==0) r.copy(arrivalNs=r.arrivalNs+1) else r }) }
    }
    @Test fun allRecipesPreserveEveryRequestUnderPureMockExecution() {
        for(recipe in listOf("L64","C252","M128")) for(pair in listOf(false,true)) {
            val s = scheduler(recipe,pair=pair)
            var t = 0L; var next = 0
            val completions = mutableListOf<Triple<Long,String,String>>()
            val ids = mutableSetOf<String>()
            while(next < s.requests.size || completions.isNotEmpty() || s.waiting().isNotEmpty()) {
                t = minOf(s.requests.getOrNull(next)?.arrivalNs ?: Long.MAX_VALUE,completions.minOfOrNull { it.first } ?: Long.MAX_VALUE)
                while(next < s.requests.size && s.requests[next].arrivalNs <= t) { s.enqueue(s.requests[next].id,t); next++ }
                val done = completions.filter { it.first <= t }; completions.removeAll(done.toSet())
                done.forEach { s.available(it.second,it.third) }
                while(true) {
                    val action = s.select(t) ?: break
                    assertTrue(action is A24PreparationScheduler.Action.Dispatch)
                    val a = action as A24PreparationScheduler.Action.Dispatch
                    assertTrue(ids.add(a.request.id))
                    completions.add(Triple(t+50_000_000L,a.request.id,a.backend))
                    assertTrue(s.owners().values.count { it!=null } <= if(pair) 2 else 1)
                }
                assertTrue(t < A24PreparationContract.SERVICE_NS)
            }
            assertEquals(s.requests.size,ids.size)
        }
    }
}
