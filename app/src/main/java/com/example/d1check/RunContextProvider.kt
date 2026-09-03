package com.example.d1check

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri

/** Read-only cross-app contract. Benchmark clients query content://com.example.d1check.run/current. */
class RunContextProvider : ContentProvider() {
    override fun onCreate(): Boolean = true

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor {
        val columns = arrayOf(
            "schema_version",
            "run_id",
            "active",
            "started_elapsed_ns",
            "started_wall_ms",
        )
        val cursor = MatrixCursor(columns)
        val run = context?.let { RunSessionStore(it).current() }
        if (uri.lastPathSegment == "current" && run != null) {
            cursor.addRow(
                arrayOf<Any?>(
                    RunSessionStore.SCHEMA_VERSION,
                    run.runId,
                    if (run.active) 1 else 0,
                    run.startedElapsedNs,
                    run.startedWallMs,
                )
            )
        }
        return cursor
    }

    override fun getType(uri: Uri): String = "vnd.android.cursor.item/vnd.d1check.run"
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(
        uri: Uri,
        values: ContentValues?,
        selection: String?,
        selectionArgs: Array<out String>?,
    ): Int = 0
}
