package org.spring.divas.loadtests.venue;

import static io.gatling.javaapi.core.CoreDsl.constantUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.foreach;
import static io.gatling.javaapi.core.CoreDsl.global;
import static io.gatling.javaapi.core.CoreDsl.rampUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.scenario;

import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;
import java.time.Duration;
import org.spring.divas.loadtests.config.LoadTestConfig;
import org.spring.divas.loadtests.config.Protocols;

public class MenuBrowsingSimulation extends Simulation {

  private static final Duration MIN_THINK_TIME_BEFORE_MENU = Duration.ofSeconds(1);
  private static final Duration MAX_THINK_TIME_BEFORE_MENU = Duration.ofSeconds(3);
  private static final Duration MIN_THINK_TIME_BETWEEN_DISHES = Duration.ofSeconds(1);
  private static final Duration MAX_THINK_TIME_BETWEEN_DISHES = Duration.ofSeconds(2);
  private static final double RAMP_START_USERS_PER_SEC = 10;
  private static final double MIN_SUCCESS_PERCENT = 99.0;
  private static final double RESPONSE_TIME_PERCENTILE = 95.0;
  private static final int MAX_RESPONSE_TIME_MS = 500;

  private static final ScenarioBuilder BROWSE_MENUS =
      scenario("Customers browse menus")
          .exec(VenueRequests.LIST_VENUES)
          .exitHereIfFailed()
          .pause(MIN_THINK_TIME_BEFORE_MENU, MAX_THINK_TIME_BEFORE_MENU)
          .exec(VenueRequests.GET_MENU)
          .exitHereIfFailed()
          .doIf("#{dishIds.exists()}").then(
              foreach("#{dishIds}", "dishId").on(
                  exec(VenueRequests.GET_DISH)
                      .pause(MIN_THINK_TIME_BETWEEN_DISHES, MAX_THINK_TIME_BETWEEN_DISHES)));

  {
    setUp(
        BROWSE_MENUS.injectOpen(
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
