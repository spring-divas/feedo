package org.spring.divas.loadtests.review;

public record VenueReviewRequest(long userId, long venueId, int rating, String content) {
}
