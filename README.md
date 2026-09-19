# Build and Launch

## 1. Clone the repositories

Clone all services to the same parent directory as this project:

```bash
git clone https://github.com/spring-divas/venue-and-menu-service.git
git clone https://github.com/spring-divas/user-service.git
git clone https://github.com/spring-divas/review-service.git
git clone https://github.com/spring-divas/order-service.git
git clone https://github.com/spring-divas/payment-service.git
```

The directory structure must be:

```text
parent-directory/
├── feedo/
├── venue-and-menu-service/
├── user-service/
├── review-service/
├── order-service/
└── payment-service/
```

---

## 2. Configure environment variables

Go to the service directories and set up `.env` files.


---

## 3. Build all Docker images

From the `spring-divas` directory:

```bash
docker compose build
```

To force a clean rebuild:

```bash
docker compose build --no-cache
```

---

## 4. Launch the complete application

Build and start all services:

```bash
docker compose up --build
```

Launch in the background:

```bash
docker compose up --build -d
```

---

## 5. Check the application

Check running containers:

```bash
docker compose ps
```

Check all logs:

```bash
docker compose logs -f
```

Check logs for a specific service:

```bash
docker compose logs -f user-service
```

Available service names:

```text
venue-and-menu-service
user-service
review-service
order-service
payment-service
```

---

## 6. Rebuild a single service

When only one service has changed:

```bash
docker compose up -d --build user-service
```

Replace `user-service` with the required service.

For example:

```bash
docker compose up -d --build order-service
```

---

## 7. Restart a service

```bash
docker compose restart user-service
```

---

## 8. Stop the application

Stop the containers:

```bash
docker compose stop
```

Remove the containers and network:

```bash
docker compose down
```

Remove containers, networks, and persistent volumes:

```bash
docker compose down -v
```

---

## 9. Complete clean rebuild

To completely rebuild the application:

```bash
docker compose down -v --remove-orphans
docker compose build --no-cache
docker compose up
```

Or in detached mode:

```bash
docker compose down -v --remove-orphans
docker compose build --no-cache
docker compose up -d
```

---

## 10. Update services

Each service is an independent Git repository.

Update them individually:

```bash
cd ../venue-and-menu-service
git pull

cd ../user-service
git pull

cd ../review-service
git pull

cd ../order-service
git pull

cd ../payment-service
git pull
```

Return to the orchestration project:

```bash
cd ../feedo
```

Rebuild and launch:

```bash
docker compose up --build -d
```

---

## 11. Run an individual service without Docker Compose

Each service can also be built independently.

For example:

```bash
cd ../user-service
./gradlew build
```

Run its tests:

```bash
./gradlew test
```

Run the application:

```bash
./gradlew bootRun
```

On Windows:

```powershell
.\gradlew.bat build
.\gradlew.bat test
.\gradlew.bat bootRun
```

The same commands can be used for any of the other services.

---

## Quick Start

After cloning all repositories and configuring `.env` files:

```bash
cd feedo
docker compose up --build -d
```

Check the status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Stop the application:

```bash
docker compose down
```
