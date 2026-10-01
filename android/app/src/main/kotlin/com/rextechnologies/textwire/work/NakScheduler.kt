package com.rextechnologies.textwire.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.rextechnologies.textwire.TextwireApp
import java.util.concurrent.TimeUnit

/** Wakes the controller at a chosen moment so resend requests go out even if the UI is dead. */
interface NakScheduler {
    fun wakeAt(atMillis: Long, nowMillis: Long)

    fun cancel()
}

/** [NakScheduler] on WorkManager: one unique delayed job, replaced whenever the moment moves. */
class WorkManagerNakScheduler(private val context: Context) : NakScheduler {
    override fun wakeAt(atMillis: Long, nowMillis: Long) {
        val request = OneTimeWorkRequestBuilder<NakWorker>()
            .setInitialDelay((atMillis - nowMillis).coerceAtLeast(0), TimeUnit.MILLISECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.REPLACE, request)
    }

    override fun cancel() {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
    }

    companion object {
        const val WORK_NAME = "textwire-nak"
    }
}

/** The job: one tick of every open conversation. */
class NakWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        (applicationContext as? TextwireApp)?.controller?.tick()
        return Result.success()
    }
}
