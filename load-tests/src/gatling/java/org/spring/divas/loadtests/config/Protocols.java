package org.spring.divas.loadtests.config;

import static io.gatling.javaapi.http.HttpDsl.http;

import io.gatling.javaapi.http.HttpProtocolBuilder;
import lombok.experimental.UtilityClass;

@UtilityClass
public class Protocols {

  public static final HttpProtocolBuilder HTTP =
      http.baseUrl(LoadTestConfig.BASE_URL)
          .acceptHeader("application/json")
          .contentTypeHeader("application/json")
          .userAgentHeader("feedo-load-tests");
}
