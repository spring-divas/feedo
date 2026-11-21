package org.spring.divas.loadtests.config;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.UncheckedIOException;
import lombok.experimental.UtilityClass;

@UtilityClass
public class Json {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  public static String toJson(Object value) {
    try {
      return MAPPER.writeValueAsString(value);
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }
}
