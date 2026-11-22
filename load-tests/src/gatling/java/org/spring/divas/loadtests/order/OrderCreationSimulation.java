package org.spring.divas.loadtests.order;

import static io.gatling.javaapi.core.CoreDsl.constantUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.csv;
import static io.gatling.javaapi.core.CoreDsl.global;
import static io.gatling.javaapi.core.CoreDsl.rampUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.scenario;

import io.gatling.javaapi.core.FeederBuilder;
import io.gatling.javaapi.core.ScenarioBuilder;
import io.gatling.javaapi.core.Simulation;
import java.time.Duration;
import org.spring.divas.loadtests.config.Protocols;

public class OrderCreationSimulation extends Simulation {

  private static final String ORDERS_FEEDER_PATH = "feeders/orders.csv";
  private static final Duration THINK_TIME_BEFORE_GET = Duration.ofSeconds(1);
  private static final double RAMP_START_USERS_PER_SEC = 10;
  private static final double MIN_SUCCESS_PERCENT = 99.0;
  private static final double RESPONSE_TIME_PERCENTILE = 95.0;
  private static final int MAX_RESPONSE_TIME_MS = 1000;
  private static final double USERS_PER_SEC = 20;
  private static final Duration RAMP_SECONDS = Duration.ofSeconds(30);
  private static final Duration DURATION_SECONDS = Duration.ofSeconds(60);

  private static final FeederBuilder<String> ORDERS = csv(ORDERS_FEEDER_PATH).random();

  private static final ScenarioBuilder CREATE_ORDERS =
      scenario("Customers create orders")
          .feed(ORDERS)
          .exec(OrderRequests.CREATE_ORDER)
          .exitHereIfFailed()
          .pause(THINK_TIME_BEFORE_GET)
          .exec(OrderRequests.GET_ORDER);

  public OrderCreationSimulation() {
    setUp(
        CREATE_ORDERS.injectOpen(
            rampUsersPerSec(RAMP_START_USERS_PER_SEC)
                .to(USERS_PER_SEC)
                .during(RAMP_SECONDS),
            constantUsersPerSec(USERS_PER_SEC).during(DURATION_SECONDS)))
        .protocols(Protocols.HTTP)
        .assertions(
            global().successfulRequests().percent().gte(MIN_SUCCESS_PERCENT),
            global().responseTime().percentile(RESPONSE_TIME_PERCENTILE).lt(MAX_RESPONSE_TIME_MS));
  }
}
