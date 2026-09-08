package com.example.d1check

enum class AutomationCommand {
    START_RUN,
    STOP_RUN,
}

enum class TelemetryCommandAction {
    START,
    STOP,
}

object AutomationCommandParser {
    const val EXTRA_COMMAND = "d1_automation_command"

    fun parse(value: String?): AutomationCommand? = when (value?.uppercase()) {
        null -> null
        AutomationCommand.START_RUN.name -> AutomationCommand.START_RUN
        AutomationCommand.STOP_RUN.name -> AutomationCommand.STOP_RUN
        else -> throw IllegalArgumentException("Unsupported $EXTRA_COMMAND: $value")
    }
}

object AutomationCommandRouter {
    fun route(command: AutomationCommand?): TelemetryCommandAction = when (command) {
        null, AutomationCommand.START_RUN -> TelemetryCommandAction.START
        AutomationCommand.STOP_RUN -> TelemetryCommandAction.STOP
    }
}
