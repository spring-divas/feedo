rootProject.name = "feedo"

include("venue-and-menu-service")
include("user-service")
include("review-service")
include("order-service")
include("payment-service")

project(":venue-and-menu-service").projectDir =
    file("../venue-and-menu-service")

project(":user-service").projectDir =
    file("../user-service")

project(":review-service").projectDir =
    file("../review-service")

project(":order-service").projectDir =
    file("../order-service")

project(":payment-service").projectDir =
    file("../payment-service")