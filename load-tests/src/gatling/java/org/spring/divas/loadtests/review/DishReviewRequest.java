package org.spring.divas.loadtests.review;

public record DishReviewRequest(long userId, long dishId, int rating, String content) {
}
