package com.example.d1check.requestrunner

import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/*
 * 출처: feature/arrival-scheduling-20260923 @ d588323
 *   benchmark-runner/src/modelProbe/.../EnergyCollectionCore.kt 44~80행 (EnergyProgress — writer 하나 · 1 s 마다 fsync ·
 *     측정 경로에는 fsync 없음 · 넘치면 실패 · gate 전 flush)
 *   benchmark-runner/src/modelProbe/.../ArrivalEnergyActivity.kt 88~93행 (save — <name>.part 에 쓰고 fsync → rename · 덮어쓰기 거부)
 * 바꾼 것: 이름 · 용량 (65,536) · 스레드 이름. progress.jsonl 은 이 writer 하나로 직렬화한다 (lane 여럿이 쓴다 — 등록 프롬프트 2부).
 */
class ProgressWriter(private val file: File, capacity: Int = 65_536) : AutoCloseable {
    private val queue = ArrayBlockingQueue<String>(capacity)
    private val submitted = AtomicLong(0)
    private val synced = AtomicLong(0)
    val failure = AtomicReference<String?>(null)
    @Volatile private var closing = false
    private val writer = Thread({
        try {
            FileOutputStream(file).use { out ->
                var syncTime = System.nanoTime()
                var written = 0L
                while (!closing || queue.isNotEmpty()) {
                    queue.poll(100, TimeUnit.MILLISECONDS)?.let {
                        out.write((it + "\n").toByteArray(Charsets.UTF_8))
                        written++
                    }
                    if (System.nanoTime() - syncTime >= 1_000_000_000L) {
                        out.fd.sync()
                        synced.set(written)
                        syncTime = System.nanoTime()
                    }
                }
                out.fd.sync()
                synced.set(written)
            }
        } catch (e: Throwable) {
            failure.compareAndSet(null, "writer: $e")
        }
    }, "d1mix-progress-writer").apply { isDaemon = true; start() }

    fun add(line: String) {
        check(!closing && failure.get() == null) { "journal closed/failed: ${failure.get()}" }
        submitted.incrementAndGet()
        if (!queue.offer(line)) {
            failure.compareAndSet(null, "overflow")
            error("journal overflow")
        }
    }

    /** gate 앞에서 모든 제출 줄이 디스크에 닿게 한다 (A24 flushBeforeGate, 2 s 상한). */
    fun flush(timeoutNs: Long = 2_000_000_000L) {
        val target = submitted.get()
        val start = System.nanoTime()
        while (synced.get() < target) {
            check(failure.get() == null && System.nanoTime() - start < timeoutNs) { "journal flush failed: ${failure.get()}" }
            Thread.sleep(10)
        }
    }

    override fun close() {
        closing = true
        writer.join(5_000)
        check(!writer.isAlive && failure.get() == null) { "journal flush incomplete: ${failure.get()}" }
    }
}

/** 원자 저장: <name>.part 에 쓰고 fsync → rename. 같은 이름이 있으면 거부 (A24 save). */
class ArtifactStore(val root: File) {
    fun save(name: String, value: Any?) = saveBytes(name, Json.encode(value).toByteArray(Charsets.UTF_8))

    fun saveBytes(name: String, bytes: ByteArray) {
        val output = File(root, name)
        val temp = File(root, "$name.part")
        check(!output.exists() && temp.createNewFile()) { "artifact exists or .part not creatable: $name" }
        FileOutputStream(temp).use {
            it.write(bytes)
            it.fd.sync()
        }
        check(temp.renameTo(output)) { "rename failed: $name" }
    }
}
