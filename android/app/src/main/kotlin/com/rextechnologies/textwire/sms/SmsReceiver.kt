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
    return joinParts(parts.map { it.displayOriginatingAddress to it.messageBody })
}

/** Parts as (sender, body) pairs, joined per sender in order; a part the radio left blank is empty. */
internal fun joinParts(parts: List<Pair<String?, String?>>): List<IncomingSms> = parts
    .groupBy { (sender, _) -> sender.orEmpty() }
    .map { (sender, messages) -> IncomingSms(sender, messages.joinToString("") { (_, body) -> body.orEmpty() }) }

/**
 * Manifest-registered, so frames arrive while the app is not running. It does the minimum:
 * hand each message to the controller, which keeps those from the server's number and
 * stores and assembles them. That is a few milliseconds of work, so it is done before
 * `onReceive` returns.
 */
class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val controller = (context.applicationContext as TextwireApp).controller
        for (message in parseSmsIntent(intent)) controller.onSms(message.sender, message.body)
    }
}
