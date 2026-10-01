package com.rextechnologies.textwire.sms

import android.content.Intent
import android.provider.Telephony
import android.telephony.SmsMessage
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.TextwireApp
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@RunWith(AndroidJUnit4::class)
@Config(application = TextwireApp::class)
class SmsTest {
    @Test
    fun `numbers match on their last nine digits`() {
        assertTrue(sameNumber("+447700900000", "07700 900000"))
        assertTrue(sameNumber("07700900000", "+44 7700 900000"))
        assertFalse(sameNumber("+447700900000", "+447700900001"))
        assertFalse(sameNumber("", ""))
        assertFalse(sameNumber("+447700900000", ""))
    }

    @Test
    fun `an intent's parts are joined per sender`() {
        val decoded = arrayOf(
            fakeMessage("+447700900000", "AAA"),
            fakeMessage("+447700900000", "BBB"),
            fakeMessage("+447700900999", "x"),
        )
        val messages = parseSmsIntent(Intent(Telephony.Sms.Intents.SMS_RECEIVED_ACTION)) { decoded }
        assertEquals(listOf(IncomingSms("+447700900000", "AAABBB"), IncomingSms("+447700900999", "x")), messages)
    }

    @Test
    fun `an intent without messages parses to nothing`() {
        assertEquals(emptyList(), parseSmsIntent(Intent(Telephony.Sms.Intents.SMS_RECEIVED_ACTION)) { null })
        assertEquals(emptyList(), parseSmsIntent(Intent(Telephony.Sms.Intents.SMS_RECEIVED_ACTION)))
    }

    @Test
    fun `the gateway sends short texts whole and long ones in parts`() {
        val gateway = AndroidSmsGateway(ApplicationProvider.getApplicationContext())
        gateway.send("+447700900000", "a7 g https://example.com")
        val manager =
            shadowOf(
                ApplicationProvider.getApplicationContext<TextwireApp>().getSystemService(
                    android.telephony.SmsManager::class.java,
                ),
            )
        assertEquals("a7 g https://example.com", manager.lastSentTextMessageParams.text)
        gateway.send("+447700900000", "a7 g https://example.com/" + "x".repeat(300))
        assertEquals(3, manager.lastSentMultipartTextMessageParams.parts.size)
        assertEquals(listOf("x".repeat(160)), splitRequest("x".repeat(160)))
        assertEquals(listOf("x".repeat(153), "x".repeat(8)), splitRequest("x".repeat(161)))
    }

    @Test
    fun `the receiver ignores other actions and hands frames to the controller`() {
        val app = ApplicationProvider.getApplicationContext<TextwireApp>()
        val receiver = SmsReceiver()
        receiver.onReceive(app, Intent("other"))
        receiver.onReceive(app, Intent(Telephony.Sms.Intents.SMS_RECEIVED_ACTION))
        assertTrue(app.controller.state.value.log.isEmpty())
    }

    private fun fakeMessage(sender: String, body: String): SmsMessage = SmsMessage.createFromPdu(
        deliverPdu(sender, body),
        "3gpp",
    )

    @Test
    fun `a real delivery pdu decodes under robolectric`() {
        val message = fakeMessage("+447700900000", "a7 g https://example.com")
        assertEquals("+447700900000", message.displayOriginatingAddress)
        assertEquals("a7 g https://example.com", message.messageBody)
    }

    private companion object {
        /** A GSM SMS-DELIVER PDU with a 7-bit ASCII body: what the radio hands the framework. */
        fun deliverPdu(sender: String, body: String): ByteArray {
            val digits = sender.removePrefix("+")
            val out = mutableListOf<Int>(0x00, 0x04, digits.length, 0x91)
            out += semiOctets(digits)
            out += listOf(0x00, 0x00)
            out += semiOctets("62019011000000").drop(0) // 2026-09-10 11:00:00 +00
            out += body.length
            out += pack7(body)
            return out.map { it.toByte() }.toByteArray()
        }

        fun semiOctets(digits: String): List<Int> {
            val padded = if (digits.length % 2 == 1) digits + "F" else digits
            return padded.chunked(2).map { pair -> (pair[1].digitToInt(16) shl 4) or pair[0].digitToInt(16) }
        }

        fun pack7(text: String): List<Int> {
            val septets = text.map { it.code and 0x7F }
            val out = mutableListOf<Int>()
            var bits = 0
            var buffer = 0
            for (septet in septets) {
                buffer = buffer or (septet shl bits)
                bits += 7
                while (bits >= 8) {
                    out += buffer and 0xFF
                    buffer = buffer shr 8
                    bits -= 8
                }
            }
            if (bits > 0) out += buffer and 0xFF
            return out
        }
    }
}
