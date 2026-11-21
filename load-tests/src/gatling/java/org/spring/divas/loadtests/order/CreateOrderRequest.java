package org.spring.divas.loadtests.order;

import java.util.List;

public record CreateOrderRequest(long userId, long venueId, long tableId, List<OrderItem> items) {
}
