package com.example.d1check.benchmarkrunner

import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.atomic.AtomicLong

/** New bounded workload contract. Never changes arrival policies or their timeouts. */
internal object EnergyCollectionCore {
    const val PROTOCOL = "energy-thermal-collection-v2"
    // COLLECT-05 may wait in resident state before the one official baseline.
    const val WATCHDOG_MS = 1_560_000L
    const val LOAD_NS = 480_000_000_000L
    const val CALL_NS = 30_000_000_000L
    val KEYS = setOf("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU")
    fun keys(pair: String): List<String> = when (pair) {
        "CG_DG" -> error("same GPU is not a two-lane pair")
        "CC_DG" -> listOf("classification_CPU", "detection_GPU")
        "CG_DC" -> listOf("classification_GPU", "detection_CPU")
        "DC_DG" -> listOf("detection_CPU", "detection_GPU")
        else -> error("unsupported pair")
    }
    fun counts() = mapOf("classification" to 678, "detection" to 192)
    fun probes(operational: Boolean, parallel: Boolean): List<Pair<String,Boolean>> =
        if (operational) listOf("eligibility_serial_probe" to false, "eligibility_parallel_probe" to true)
        else listOf("eligibility_probe" to parallel)
    fun selectable(remaining: List<Int>, busy: Set<Int>, parallel: Boolean): List<Int> {
        require(remaining.size == 2 && remaining.all { it >= 0 } && busy.all { it in 0..1 })
        if (!parallel && busy.isNotEmpty()) return emptyList()
        val eligible = (0..1).filter { remaining[it] > 0 && it !in busy }
        return if (parallel) eligible else eligible.take(1)
    }
    fun requireTime(now: Long, start: Long, budget: Long) {
        check(now - start < budget) { "bounded phase/call timeout" }
    }
    fun remainingCall(now: Long, phaseStart: Long, phaseBudget: Long): Long {
        requireTime(now,phaseStart,phaseBudget)
        return minOf(CALL_NS,phaseBudget-(now-phaseStart))
    }
}

/** Independent bounded writer: no fsync on the measured worker path.
 * A crash can lose the queued prefix/last second. Missing completion stays unknown.
 */
internal class EnergyProgress(private val file: File, private val capacity: Int = 32768) : AutoCloseable {
    private val queue = ArrayBlockingQueue<String>(capacity)
    private val submitted = AtomicLong(0)
    private val synced = AtomicLong(0)
    val failure = AtomicReference<String?>(null)
    @Volatile private var closing = false
    private val writer = Thread({
        try {
            FileOutputStream(file).use { out ->
                var syncTime = System.nanoTime(); var written = 0L
                while (!closing || queue.isNotEmpty()) {
                    queue.poll(100, TimeUnit.MILLISECONDS)?.let { out.write((it + "\n").toByteArray(Charsets.UTF_8)); written++ }
                    if (System.nanoTime() - syncTime >= 1_000_000_000) { out.fd.sync(); synced.set(written); syncTime = System.nanoTime() }
                }
                out.fd.sync()
            }
        } catch (e: Throwable) { failure.compareAndSet(null, "writer: $e") }
    }, "energy-progress-writer").apply { isDaemon = true; start() }
    fun add(line: String) {
        check(!closing && failure.get() == null) { "journal closed/failed" }
        submitted.incrementAndGet()
        if (!queue.offer(line)) { failure.compareAndSet(null, "overflow"); error("journal overflow") }
    }
    fun flushBeforeGate() {
        val target=submitted.get(); val start=System.nanoTime()
        while (synced.get()<target) {
            check(failure.get()==null && System.nanoTime()-start<2_000_000_000) { "bounded gate journal flush failed" }
            Thread.sleep(10)
        }
    }
    override fun close() {
        closing = true; writer.join(2000)
        check(!writer.isAlive && failure.get() == null) { "journal flush incomplete: ${failure.get()}" }
    }
}
