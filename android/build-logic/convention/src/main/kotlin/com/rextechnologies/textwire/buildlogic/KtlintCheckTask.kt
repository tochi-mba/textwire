package com.rextechnologies.textwire.buildlogic

import org.gradle.api.file.RegularFileProperty
import org.gradle.api.tasks.JavaExec
import org.gradle.api.tasks.OutputFile
import org.gradle.api.tasks.TaskAction

/** Runs the ktlint command-line tool and records a pass, so an unchanged module is not linted again. */
abstract class KtlintCheckTask : JavaExec() {
    @get:OutputFile
    abstract val marker: RegularFileProperty

    @TaskAction
    override fun exec() {
        super.exec()
        marker.get().asFile.apply { parentFile.mkdirs() }.writeText("ok\n")
    }
}
