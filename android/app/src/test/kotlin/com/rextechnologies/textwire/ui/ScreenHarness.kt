package com.rextechnologies.textwire.ui

import android.view.View
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.click
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.text.TextLayoutResult
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.FakeClock
import com.rextechnologies.textwire.FakeGateway
import com.rextechnologies.textwire.FakeNotifier
import com.rextechnologies.textwire.FakeScheduler
import com.rextechnologies.textwire.FakeSettings
import com.rextechnologies.textwire.FakeStorage
import com.rextechnologies.textwire.SERVER
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Alphabet
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.encodeFrame
import org.junit.Rule

/**
 * The app's screens over a real controller and fakes, as every screen test uses them: what was
 * texted is in [gateway], what was shared in [shared], how often permissions were asked for in
 * [permissionRequests], and the window the screens drew in is [view].
 */
abstract class ScreenHarness {
    @get:Rule
    val compose = createComposeRule()

    protected val storage = FakeStorage()
    protected val settings = FakeSettings()
    protected val gateway = FakeGateway()
    protected val clock = FakeClock()
    protected val notifier = FakeNotifier()
    protected val controller =
        Controller(storage, settings, gateway, FakeScheduler(), ZstdDictionary.packaged(), notifier) { clock.now }

    protected val shared = mutableListOf<StoredPage>()
    protected var permissionRequests = 0
    protected lateinit var view: View

    /** What Android allows; a test can change either while the screens show. */
    protected var smsAllowed by mutableStateOf(true)
    protected var notificationsAllowed by mutableStateOf(true)

    /** Whether the guide to the update is open, and how many times it was dismissed. */
    protected var guideVisible by mutableStateOf(false)
    protected var guideDismissals = 0

    protected fun show(granted: Boolean = true, notifications: Boolean = true) {
        smsAllowed = granted
        notificationsAllowed = notifications
        compose.setContent {
            view = LocalView.current
            TextwireUi(
                controller = controller,
                permissionsGranted = smsAllowed,
                notificationsAllowed = notificationsAllowed,
                requestPermissions = { permissionRequests++ },
                share = { shared.add(it) },
                updateGuideVisible = guideVisible,
                dismissUpdateGuide = {
                    guideVisible = false
                    guideDismissals++
                },
                showUpdateGuide = { guideVisible = true },
            )
        }
    }

    /** A whole reply from the server, the way it arrives: one frame after another. */
    protected fun deliver(tag: Int, text: String, kind: Kind = Kind.PAGE, page: Int = 1, pages: Int = 1) {
        val payload = byteArrayOf(kind.code.toByte(), 0, page.toByte(), pages.toByte()) + text.toByteArray()
        val bodies = payload.toList().chunked(114)
        bodies.forEachIndexed { seq, body ->
            controller.onSms(SERVER, encodeFrame(Frame(tag, seq, bodies.size, body), Alphabet.B64))
        }
    }

    /** Only the first frame of a long reply to request [tag], then silence until it gives up. */
    protected fun stall(tag: Int) {
        val payload = byteArrayOf(1, 0, 1, 1) + "word ".repeat(100).toByteArray()
        val bodies = payload.toList().chunked(114)
        controller.onSms(SERVER, encodeFrame(Frame(tag, 0, bodies.size, bodies[0]), Alphabet.B64))
        repeat(4) {
            clock.advance(60_000)
            controller.tick()
        }
    }

    /** Scrolls the list tagged [list] until something in it matching [what] shows, and returns it. */
    protected fun reach(list: String, what: SemanticsMatcher): SemanticsNodeInteraction {
        val inside = what and hasAnyAncestor(hasTestTag(list))
        compose.onNodeWithTag(list).performScrollToNode(inside)
        return compose.onNode(inside)
    }

    /** Taps the link chip [chip] inside the line of text [line], where a finger would. */
    protected fun tapChip(line: SemanticsNodeInteraction, text: String, chip: String) {
        val layouts = mutableListOf<TextLayoutResult>()
        line.fetchSemanticsNode().config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action?.invoke(layouts)
        val box = layouts.single().getBoundingBox(text.indexOf(chip) + 1)
        line.performTouchInput { click(box.center) }
    }
}
