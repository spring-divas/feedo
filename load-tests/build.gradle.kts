plugins {
    id("java")
    id("io.gatling.gradle") version "3.16.1"
}

group = "org.spring.divas"
version = "1.0.0"

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

val lombokVersion = "1.18.48"

dependencies {
    gatlingImplementation("com.fasterxml.jackson.core:jackson-databind:2.23.0")
    gatlingCompileOnly("org.projectlombok:lombok:$lombokVersion")
    gatlingAnnotationProcessor("org.projectlombok:lombok:$lombokVersion")
}

// Forward load-test settings, e.g. ./gradlew gatlingRun -DbaseUrl=http://localhost:8080 -DusersPerSec=20
val loadTestProperties = listOf("baseUrl", "usersPerSec", "rampSeconds", "durationSeconds")

tasks.withType<io.gatling.gradle.GatlingRunTask>().configureEach {
    systemProperties = loadTestProperties
        .mapNotNull { key -> System.getProperty(key)?.let { key to it } }
        .toMap()
}