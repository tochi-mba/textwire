package com.rextechnologies.textwire

import android.app.Application
import com.rextechnologies.textwire.data.Database
import com.rextechnologies.textwire.data.PreferencesSettings
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.sms.AndroidSmsGateway
import com.rextechnologies.textwire.work.WorkManagerNakScheduler

/**
 * Owns the one [Controller] the activity, the SMS receiver and the resend worker share.
 *
 * Wiring is by hand: the real database, settings, SMS manager, WorkManager scheduler and the
 * packaged dictionary. Tests build a [Controller] from fakes and never see this class.
 */
class TextwireApp : Application() {
    val controller: Controller by lazy {
        Controller(
            storage = Database(this),
            settings = PreferencesSettings(this),
            gateway = AndroidSmsGateway(this),
            scheduler = WorkManagerNakScheduler(this),
            dictionary = ZstdDictionary.packaged(),
        )
    }
}
