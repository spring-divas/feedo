package org.spring.divas.loadtests.review;

import static io.gatling.javaapi.core.CoreDsl.StringBody;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

import io.gatling.javaapi.http.HttpRequestActionBuilder;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import lombok.experimental.UtilityClass;
import org.spring.divas.loadtests.config.Json;

@UtilityClass
public class ReviewRequests {

  private static final int MIN_RATING = 1;
  private static final int MAX_RATING = 5;
  private static final List<String> CONTENTS = List.of(
      "Absolutely loved it!",
      "Tasty and fresh.",
      "Decent but nothing special.",
      "Took too long to arrive.",
      "Very disappointing.");

  public static final HttpRequestActionBuilder CREATE_DISH_REVIEW =
      http("Create dish review")
          .post("/api/review/dish")
          .body(StringBody(session -> Json.toJson(new DishReviewRequest(
              session.getLong("userId"), session.getLong("dishId"),
              randomRating(), randomContent()))))
          .check(status().is(201));

  public static final HttpRequestActionBuilder CREATE_VENUE_REVIEW =
      http("Create venue review")
          .post("/api/review/venue")
          .body(StringBody(session -> Json.toJson(new VenueReviewRequest(
              session.getLong("userId"), session.getLong("venueId"),
              randomRating(), randomContent()))))
          .check(status().is(201));

  private static int randomRating() {
    return ThreadLocalRandom.current().nextInt(MIN_RATING, MAX_RATING + 1);
  }

  private static String randomContent() {
    return CONTENTS.get(ThreadLocalRandom.current().nextInt(CONTENTS.size()));
  }
}
