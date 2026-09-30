package com.rextechnologies.textwire.buildlogic

import org.gradle.api.Project
import javax.inject.Inject

/** The `textwire { }` block: the decisions a module makes that the conventions cannot make for it. */
abstract class TextwireExtension @Inject constructor(private val project: Project) {
    /**
     * Holds this module's tests to a coverage floor, which `check` verifies.
     *
     * For pure JVM modules only. Over Robolectric, JaCoCo measures the framework as much as the code.
     *
     * @param excludes class-file patterns left out of the measurement, each for a reason stated where
     *   it is passed.
     */
    fun coverageFloor(line: Double, branch: Double, excludes: List<String> = emptyList()) {
        project.configureCoverageFloor(line, branch, excludes)
    }
}
