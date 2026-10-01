package com.rextechnologies.textwire.work

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.Configuration
import androidx.work.ListenableWorker
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.testing.TestListenableWorkerBuilder
import androidx.work.testing.WorkManagerTestInitHelper
import com.rextechnologies.textwire.TextwireApp
import kotlinx.coroutines.runBlocking
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@RunWith(AndroidJUnit4::class)
@Config(application = TextwireApp::class)
class NakSchedulerTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Before
    fun init() {
        WorkManagerTestInitHelper.initializeTestWorkManager(context, Configuration.Builder().build())
    }

    @Test
    fun `waking replaces the one pending job and cancelling removes it`() {
        val scheduler = WorkManagerNakScheduler(context)
        scheduler.wakeAt(atMillis = 70_000, nowMillis = 10_000)
        scheduler.wakeAt(atMillis = 20_000, nowMillis = 10_000)
        val pending = WorkManager.getInstance(
            context,
        ).getWorkInfosForUniqueWork(WorkManagerNakScheduler.WORK_NAME).get()
        assertEquals(1, pending.count { it.state == WorkInfo.State.ENQUEUED })
        scheduler.cancel()
        val after = WorkManager.getInstance(context).getWorkInfosForUniqueWork(WorkManagerNakScheduler.WORK_NAME).get()
        assertTrue(after.all { it.state == WorkInfo.State.CANCELLED })
    }

    @Test
    fun `a moment in the past is scheduled without delay`() {
        WorkManagerNakScheduler(context).wakeAt(atMillis = 5, nowMillis = 10)
        val pending = WorkManager.getInstance(
            context,
        ).getWorkInfosForUniqueWork(WorkManagerNakScheduler.WORK_NAME).get()
        // The test executor runs zero-delay work at once, so it may already be running or done.
        assertTrue(
            pending.single().state in setOf(WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.SUCCEEDED),
        )
    }

    @Test
    fun `the worker ticks the controller and succeeds`() {
        val worker = TestListenableWorkerBuilder<NakWorker>(context).build()
        val result = runBlocking { worker.doWork() }
        assertEquals(ListenableWorker.Result.success(), result)
    }
}
