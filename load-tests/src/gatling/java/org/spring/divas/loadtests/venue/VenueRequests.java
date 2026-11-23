package org.spring.divas.loadtests.venue;

import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

import io.gatling.javaapi.http.HttpRequestActionBuilder;
import lombok.experimental.UtilityClass;

@UtilityClass
public class VenueRequests {

  public static final HttpRequestActionBuilder LIST_VENUES =
      http("List venues")
          .get("/api/venue")
          .check(status().is(200))
          .check(jsonPath("$[*].id").findRandom().saveAs("venueId"));

  public static final HttpRequestActionBuilder GET_MENU =
      http("Get menu")
          .get("/api/menu")
          .queryParam("venueId", "#{venueId}")
          .check(status().is(200))
          .check(jsonPath("$[*].id").findRandom(3, false).optional().saveAs("dishIds"));

  public static final HttpRequestActionBuilder GET_DISH =
      http("Get dish")
          .get("/api/dish/#{dishId}")
          .check(status().is(200));
}
