package org.spring.divas.loadtests.order;

import static io.gatling.javaapi.core.CoreDsl.StringBody;
import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;
import static org.spring.divas.loadtests.config.SessionAttributes.requireString;

import io.gatling.javaapi.core.Session;
import io.gatling.javaapi.http.HttpRequestActionBuilder;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import lombok.experimental.UtilityClass;
import org.spring.divas.loadtests.config.Json;

@UtilityClass
public class OrderRequests {

  private static final String DISH_IDS_SEPARATOR = "\\|";
  private static final int MIN_QUANTITY = 1;
  private static final int MAX_QUANTITY = 3;

  public static final HttpRequestActionBuilder CREATE_ORDER =
      http("Create order")
          .post("/order/api/order")
          .body(StringBody(session -> Json.toJson(createOrderRequest(session))))
          .check(status().is(201))
          .check(jsonPath("$.id").saveAs("orderId"));

  public static final HttpRequestActionBuilder GET_ORDER =
      http("Get order")
          .get("/order/api/order/#{orderId}")
          .check(status().is(200));

  private static CreateOrderRequest createOrderRequest(Session session) {
    List<OrderItem> items = Arrays.stream(requireString(session, "dishIds").split(DISH_IDS_SEPARATOR))
        .map(dishId -> new OrderItem(
            Long.parseLong(dishId),
            ThreadLocalRandom.current().nextInt(MIN_QUANTITY, MAX_QUANTITY + 1)))
        .toList();

    return new CreateOrderRequest(
        session.getLong("userId"),
        session.getLong("venueId"),
        session.getLong("tableId"),
        items);
  }
}
