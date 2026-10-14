package com.example.d1check.benchmarkrunner

/** New opt-in prescription executor; not an adaptive policy and not a device validation. */
internal object A24PreparationContract {
    const val PROTOCOL = "a24-laptop-measurement-v1"
    const val SERVICE_NS = 120_000_000_000L
    const val LOGGING_NS = 210_000_000_000L
    const val WAIT_NS = 200_000_000L
    val RUNTIME_KEYS = listOf("C_CPU", "C_GPU", "D_CPU", "D_GPU")
    fun runtimeTask(key: String): String {
        require(key in RUNTIME_KEYS)
        return if(key.startsWith("C_")) "classification" else "detection"
    }
    fun runtimeBackend(key: String): String {
        require(key in RUNTIME_KEYS)
        return key.substringAfter('_')
    }
    fun validateRuntimeMapping(key: String, task: String, backend: String) {
        require(task == runtimeTask(key) && backend == runtimeBackend(key)) { "Runtime key does not match model task/backend" }
    }
    data class Request(val id: String, val ordinal: Int, val task: String,
                       val arrivalNs: Long, val deadlineNs: Long, val group: Int)
    data class Prescription(val recipe: String, val order: String, val route: String,
                            val concurrency: String, val waitMs: Int)

    fun validate(p: Prescription, requests: List<Request>) {
        require(p.recipe in setOf("L64", "C252", "M128", "IDLE", "I_C32"))
        require(p.order in setOf("FIFO", "EDD"))
        require(p.route in setOf("C_CPU", "C_GPU_D_CPU"))
        require(p.concurrency in setOf("SERIAL", "CG_DC"))
        require(p.waitMs in setOf(0, 200))
        require(p.concurrency != "CG_DC" || p.route == "C_GPU_D_CPU")
        require(p.waitMs == 0 || (p.recipe == "M128" && p.order == "FIFO" && p.concurrency == "SERIAL"))
        require(requests.map { it.id }.distinct().size == requests.size)
        require(requests.map { it.ordinal } == requests.indices.toList())
        require(requests.all { it.task in setOf("C", "D") && it.arrivalNs >= 0 && it.arrivalNs < SERVICE_NS && it.deadlineNs > it.arrivalNs })
        require(requests.zipWithNext().all { (a,b) -> a.arrivalNs <= b.arrivalNs })
        val n = when(p.recipe) { "L64" -> 64; "C252" -> 252; "M128" -> 128; "I_C32" -> 32; else -> 0 }
        require(requests.size == n)
        if (p.recipe == "L64") requests.forEachIndexed { i,r ->
            require(r.task == if(i % 2 == 0) "C" else "D")
            require(r.arrivalNs == 35_000_000_000L+i*1_000_000_000L && r.group == -1)
        }
        if (p.recipe == "C252") requests.forEachIndexed { i,r ->
            require(r.task == "C" && r.arrivalNs == 35_000_000_000L+i*333_200_000L && r.group == -1)
        }
        if (p.recipe == "I_C32") {
            require(p.route == "C_GPU_D_CPU" && p.order == "FIFO" && p.concurrency == "SERIAL" && p.waitMs == 0)
            requests.forEachIndexed { i,r ->
                require(r.task == "C" && r.arrivalNs == 35_000_000_000L+i*1_000_000_000L && r.group == -1)
                require(r.deadlineNs-r.arrivalNs == 2_200_000_000L)
            }
        }
        if (p.recipe == "M128") {
            val delta = requests[8].arrivalNs-requests[0].arrivalNs
            require(delta > 0 && delta % 1000 == 0L) // registered microsecond-ceiling profile recipe
            requests.forEachIndexed { i,r ->
                require(r.task == if(i%8 in setOf(3,7)) "D" else "C")
                require(r.group == i/8 && r.arrivalNs == 35_000_000_000L+(i/8)*delta)
            }
        }
        if (p.recipe in setOf("L64", "C252", "M128")) requests.forEach {
            require(it.deadlineNs-it.arrivalNs == if(it.task == "C") 2_200_000_000L else 5_000_000_000L)
        }
    }
}

/** Called only on a single dispatch executor; lane ownership ends at actual AVAILABLE. */
internal class A24PreparationScheduler(
    val prescription: A24PreparationContract.Prescription,
    val requests: List<A24PreparationContract.Request>,
) {
    init { A24PreparationContract.validate(prescription, requests) }
    sealed class Action {
        data class Dispatch(val request: A24PreparationContract.Request, val backend: String): Action()
        data class Wait(val group: Int, val startNs: Long, val endNs: Long): Action()
    }
    private val queue = mutableListOf<A24PreparationContract.Request>()
    private val arrived = mutableSetOf<String>()
    private val dispatched = mutableSetOf<String>()
    private val waited = mutableSetOf<Int>()
    private val owners = linkedMapOf<String,String?>("CPU" to null,"GPU" to null)
    var wait: Action.Wait? = null; private set
    var stopped = false; private set
    fun owners(): Map<String,String?> = LinkedHashMap(owners)
    fun waiting(): List<String> = ordered().map { it.id }
    fun dispatchCount() = dispatched.size
    fun enqueue(id: String, elapsedNs: Long) {
        val q = requests.single { it.id == id }
        require(elapsedNs >= q.arrivalNs) { "future request" }
        check(arrived.add(id)) { "duplicate arrival" }
        queue.add(q)
    }
    private fun ordered() = if(prescription.order == "EDD") queue.sortedWith(
        compareBy<A24PreparationContract.Request> { it.deadlineNs }.thenBy { it.arrivalNs }.thenBy { it.ordinal }.thenBy { it.id })
    else queue.sortedWith(compareBy<A24PreparationContract.Request> { it.arrivalNs }.thenBy { it.ordinal }.thenBy { it.id })
    fun select(elapsedNs: Long): Action? {
        if(stopped || elapsedNs >= A24PreparationContract.SERVICE_NS) return null
        if(wait != null) return null // arrivals and callbacks cannot cancel the selected dose
        val q = ordered().firstOrNull() ?: return null
        if(prescription.concurrency == "SERIAL" && owners.values.any { it != null }) return null
        val backend = if(q.task == "D" || prescription.route == "C_CPU") "CPU" else "GPU"
        if(owners[backend] != null) return null // strict head: no overtaking a busy lane
        if(prescription.waitMs == 200 && q.group !in waited) {
            check(owners.values.all { it == null })
            return Action.Wait(q.group,elapsedNs,minOf(A24PreparationContract.SERVICE_NS,elapsedNs+A24PreparationContract.WAIT_NS)).also {
                wait = it; waited.add(q.group)
            }
        }
        queue.remove(q); check(dispatched.add(q.id)); check(owners[backend] == null)
        owners[backend] = q.id
        return Action.Dispatch(q,backend)
    }
    fun endWait(elapsedNs: Long): Action.Wait {
        val current = checkNotNull(wait)
        require(elapsedNs >= current.endNs)
        wait = null
        return current
    }
    fun available(id: String, backend: String) {
        check(owners[backend] == id) { "AVAILABLE does not match current lane owner" }
        owners[backend] = null
    }
    /** Only a selected action that has NOT been submitted to a worker can be rolled back. */
    fun rollbackUnsubmitted(action: Action.Dispatch) {
        check(owners[action.backend] == action.request.id)
        check(action.request !in queue && dispatched.remove(action.request.id))
        owners[action.backend] = null
        queue.add(action.request)
    }
    fun stopDispatch() { stopped = true }
}
