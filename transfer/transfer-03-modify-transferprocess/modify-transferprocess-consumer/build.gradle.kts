/*
 *  Copyright (c) 2020, 2021 Microsoft Corporation
 *
 *  This program and the accompanying materials are made available under the
 *  terms of the Apache License, Version 2.0 which is available at
 *  https://www.apache.org/licenses/LICENSE-2.0
 *
 *  SPDX-License-Identifier: Apache-2.0
 *
 *  Contributors:
 *       Microsoft Corporation - initial API and implementation
 *       Fraunhofer Institute for Software and Systems Engineering - added dependencies
 *       ZF Friedrichshafen AG - add dependency
 *
 */

plugins {
    `java-library`
    id("application")
    alias(libs.plugins.shadow)
}

dependencies {
    implementation(project(":transfer:transfer-03-modify-transferprocess:watchdog"))
    implementation(project(":transfer:transfer-03-modify-transferprocess:simulator"))

    implementation(libs.edc.control.plane.core)
    implementation(libs.edc.http)

    implementation(libs.edc.configuration.filesystem)
    implementation(libs.edc.iam.mock)

    implementation(libs.edc.auth.tokenbased)
    implementation(libs.edc.management.api)

    implementation(libs.edc.dsp)
}

application {
    mainClass.set("org.eclipse.edc.boot.system.runtime.BaseRuntime")
}

tasks.withType<com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar> {
    exclude("**/pom.properties", "**/pom.xm")
    mergeServiceFiles()
    archiveFileName.set("consumer.jar")
}
