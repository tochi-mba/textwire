package com.rextechnologies.textwire.sms

import android.content.Context
import android.telephony.SmsManager

/** Sends one text to one number. The only way a request leaves the phone. */
interface SmsGateway {
    fun send(destination: String, text: String)
}

/** [SmsGateway] on the platform's [SmsManager]; long requests go as a multipart SMS. */
class AndroidSmsGateway(context: Context) : SmsGateway {
    private val manager: SmsManager = context.getSystemService(SmsManager::class.java)

    override fun send(destination: String, text: String) {
        val parts = splitRequest(text)
        if (parts.size == 1) {
            manager.sendTextMessage(destination, null, text, null, null)
        } else {
            manager.sendMultipartTextMessage(destination, null, ArrayList(parts), null, null)
        }
    }
}

/** One SMS holds 160 GSM-7 characters; a part of a concatenated SMS holds 153. */
const val SINGLE_SMS_CHARS = 160
const val CONCATENATED_PART_CHARS = 153

/**
 * The parts a request is sent as. Requests are ASCII (a URL or search words), so characters
 * and septets agree; a request longer than one SMS goes as concatenated parts that the network
 * and the server's provider reassemble (PROTOCOL.md section 6.1).
 */
fun splitRequest(text: String): List<String> =
    if (text.length <= SINGLE_SMS_CHARS) listOf(text) else text.chunked(CONCATENATED_PART_CHARS)

/** Whether two numbers name the same phone: same digits, ignoring spacing and a national prefix. */
fun sameNumber(a: String, b: String): Boolean {
    val left = significantDigits(a)
    val right = significantDigits(b)
    return left.isNotEmpty() && left == right
}

private const val SIGNIFICANT = 9

/** The last nine digits, which identify a UK mobile whether written `07...` or `+447...`. */
private fun significantDigits(number: String): String = number.filter { it.isDigit() }.takeLast(SIGNIFICANT)
