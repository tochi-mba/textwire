package com.rextechnologies.textwire.buildlogic

import com.android.build.api.dsl.CommonExtension
import org.gradle.api.Plugin
import org.gradle.api.Project

/** `textwire.compose`: the Compose compiler, for an Android module that draws with Compose. */
class ComposeConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("org.jetbrains.kotlin.plugin.compose")
            pluginManager.withPlugin("com.android.application") {
                (extensions.getByName("android") as CommonExtension).buildFeatures.compose = true
            }
        }
    }
}
