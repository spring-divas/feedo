package org.spring.divas.loadtests.review;

import static io.gatling.javaapi.core.CoreDsl.constantUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.csv;
import static io.gatling.javaapi.core.CoreDsl.global;
import static io.gatling.javaapi.core.CoreDsl.rampUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.scenario;

import io.gatling.javaapi.core.FeederBuilder;
import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;
import java.time.Duration;
import org.spring.divas.loadtests.config.LoadTestConfig;
import org.spring.divas.loadtests.config.Protocols;

public class ReviewCreationSimulation extends Simulation {

  private static final String REVIEWS_FEEDER_PATH = "feeders/reviews.csv";
  private static final Duration MIN_THINK_TIME_BETWEEN_REVIEWS = Duration.ofSeconds(1);
  private static final Duration MAX_THINK_TIME_BETWEEN_REVIEWS = Duration.ofSeconds(3);
  private static final double RAMP_START_USERS_PER_SEC = 10;
  private static final double MIN_SUCCESS_PERCENT = 99.0;
  private static final double RESPONSE_TIME_PERCENTILE = 95.0;
  private static final int MAX_RESPONSE_TIME_MS = 1000;

  private static final FeederBuilder<String> REVIEWS = csv(REVIEWS_FEEDER_PATH).queue();

  private static final ScenarioBuilder CREATE_REVIEWS =
      scenario("Customers review dish and venue")
          .feed(REVIEWS)
          .exec(ReviewRequests.CREATE_DISH_REVIEW)
          .pause(MIN_THINK_TIME_BETWEEN_REVIEWS, MAX_THINK_TIME_BETWEEN_REVIEWS)
          .exec(ReviewRequests.CREATE_VENUE_REVIEW);

  {
    setUp(
        CREATE_REVIEWS.injectOpen(
            rampUsersPerSec(RAMP_START_USERS_PER_SEC)
                .to(LoadTestConfig.USERS_PER_SEC)
                .during(LoadTestConfig.RAMP),
            constantUsersPerSec(LoadTestConfig.USERS_PER_SEC).during(LoadTestConfig.DURATION)))
        .protocols(Protocols.HTTP)
        .assertions(
            global().successfulRequests().percent().gte(MIN_SUCCESS_PERCENT),
            global().responseTime().percentile(RESPONSE_TIME_PERCENTILE).lt(MAX_RESPONSE_TIME_MS));
  }
}
