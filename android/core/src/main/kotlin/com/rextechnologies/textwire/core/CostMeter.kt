package com.rextechnologies.textwire.core

/** What today's replies have cost so far, estimated from a price per SMS (ADR-0012). */
data class CostMeter(val segments: Int = 0, val pricePerSegment: Double = DEFAULT_PRICE, val currency: String = "USD") {
    /** The meter after [count] more SMS arrived. */
    fun plus(count: Int): CostMeter {
        require(count >= 0) { "a count cannot be negative" }
        return copy(segments = segments + count)
    }

    /** The estimated spend. */
    val estimate: Double get() = segments * pricePerSegment

    /** `12 texts \u00b7 ~0.67 USD`. */
    fun describe(): String {
        val count = if (segments == 1) "1 text" else "$segments texts"
        return "$count \u00b7 ~${"%.2f".format(estimate)} $currency"
    }

    companion object {
        /** Twilio's UK outbound rate in 2026-09; the app's settings can change it. */
        const val DEFAULT_PRICE = 0.056
    }
}
