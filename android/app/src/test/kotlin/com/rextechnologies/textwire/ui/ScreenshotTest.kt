package com.rextechnologies.textwire.ui

import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.protocol.Kind
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowDialog
import java.io.File
import kotlin.test.assertTrue

/**
 * Every screen drawn to `app/build/screenshots/`, at the Galaxy S21 Ultra's size, so a change to
 * the UI can be looked at without a phone. Each test also checks the image is not blank.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ScreenshotTest : ScreenHarness() {
    /** Draws [target] (the app's window unless given) into `build/screenshots/[name].png`. */
    private fun save(name: String, target: View? = null) {
        compose.waitForIdle()
        val window = target ?: view.rootView
        val bitmap = Bitmap.createBitmap(window.width, window.height, Bitmap.Config.ARGB_8888)
        window.draw(Canvas(bitmap))
        val folder = File("build/screenshots").apply { mkdirs() }
        File(folder, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        val colours = (0 until bitmap.width step 16).flatMap { x ->
            (0 until bitmap.height step 16).map { y -> bitmap.getPixel(x, y) }
        }.toSet()
        assertTrue(colours.size > 3, "$name is blank")
    }

    private fun busyHome() {
        controller.search("weather london")
        deliver(0, "# Search: weather london\n\n1. London - BBC Weather[1] (bbc.co.uk)\nSunny intervals.", Kind.SEARCH)
        controller.get("https://en.wikipedia.org/wiki/SMS")
        deliver(1, "# SMS - Wikipedia\n\nShort Message Service is a text messaging service.", pages = 3)
        controller.get("https://www.bbc.co.uk/news")
        stall(2)
        controller.get("https://example.com/long")
        controller.show(com.rextechnologies.textwire.Screen.HOME)
    }

    @Test
    fun `home, empty and first run`() {
        controller.saveSettings(settings.snapshot.copy(serverNumber = ""))
        show(granted = false)
        save("home-empty")
    }

    @Test
    fun `home with replies and pages`() {
        show()
        busyHome()
        save("home-busy")
    }

    @Test
    fun `the reader`() {
        show()
        controller.get("https://dunmore-gazette.example/news/text-only-library")
        deliver(
            0,
            "# Village gets its first text-only library\n\nResidents of Dunmore, a hill village with no mobile " +
                "data signal, can now borrow the news by text message[1].\n\n## How it works\n\n- Search the web by " +
                "texting a few words\n- Open any page by texting its address\n- Follow a link by texting its " +
                "number[2]\n\n1. A search usually takes four messages.\n2. A news story usually takes twelve.",
            pages = 3,
        )
        save("reader")
    }

    @Test
    fun `diagnostics`() {
        show()
        busyHome()
        controller.onSms(com.rextechnologies.textwire.SERVER, "hello from a person")
        compose.onNodeWithTag("nav-diagnostics").performClick()
        save("diagnostics")
    }

    @Test
    @Config(qualifiers = "w412dp-h2400dp-xxhdpi")
    fun `settings, all of it`() {
        show(notifications = false)
        compose.onNodeWithTag("nav-settings").performClick()
        save("settings")
    }

    @Test
    fun `what's new`() {
        guideVisible = true
        show()
        compose.waitForIdle()
        save("whats-new", ShadowDialog.getLatestDialog().window!!.decorView)
    }
}
