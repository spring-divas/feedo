package org.spring.divas.loadtests.config;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.Properties;
import lombok.experimental.UtilityClass;

@UtilityClass
public class LoadTestConfig {

  private static final String PROPERTIES_FILE = "load-test.properties";
  private static final Properties FILE_PROPERTIES = loadFileProperties();

  public static final String BASE_URL = read("baseUrl", "BASE_URL");

  private static String read(String property, String envVar) {
    String value = System.getProperty(property);
    if (isBlank(value)) {
      value = System.getenv(envVar);
    }
    if (isBlank(value)) {
      value = FILE_PROPERTIES.getProperty(property);
    }
    if (isBlank(value)) {
      throw new IllegalStateException(
          "Missing load test setting '" + property + "' in " + PROPERTIES_FILE);
    }
    return value.trim();
  }

  private static boolean isBlank(String value) {
    return value == null || value.isBlank();
  }

  private static Properties loadFileProperties() {
    Properties properties = new Properties();
    try (InputStream in =
        LoadTestConfig.class.getClassLoader().getResourceAsStream(PROPERTIES_FILE)) {
      if (in != null) {
        properties.load(in);
      }
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
    return properties;
  }
}
