package com.rextechnologies.textwire.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.telephony.SmsMessage
import com.rextechnologies.textwire.TextwireApp

/** One text message as it arrived, all parts joined. */
data class IncomingSms(val sender: String, val body: String)

/** The messages in an `SMS_RECEIVED` intent, one per sender, parts joined in order. */
fun parseSmsIntent(
    intent: Intent,
    decode: (Intent) -> Array<SmsMessage>? = Telephony.Sms.Intents::getMessagesFromIntent,
): List<IncomingSms> {
    val parts = decode(intent)?.filterNotNull() ?: return emptyList()
    return parts
        .groupBy { it.displayOriginatingAddress ?: "" }
        .map { (sender, messages) -> IncomingSms(sender, messages.joinToString("") { it.messageBody ?: "" }) }
}

/**
 * Manifest-registered, so frames arrive while the app is not running. It does the minimum:
 * hand each message from the server's number to the controller, which stores and assembles.
 */
class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val app = context.applicationContext as? TextwireApp ?: return
        val messages = parseSmsIntent(intent)
        if (messages.isEmpty()) return
        val pending = goAsync()
        try {
            for (message in messages) app.controller.onSms(message.sender, message.body)
        } finally {
            pending.finish()
        }
    }
}
