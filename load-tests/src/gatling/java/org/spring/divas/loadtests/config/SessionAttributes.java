package org.spring.divas.loadtests.config;

import io.gatling.javaapi.core.Session;
import lombok.experimental.UtilityClass;

@UtilityClass
public class SessionAttributes {

  public static String requireString(Session session, String key) {
    String value = session.getString(key);
    if (value == null) {
      throw new IllegalStateException("Missing session attribute '" + key + "'");
    }
    return value;
  }
}
