# Build and Launch

## 1. Clone the repositories

Clone all repositories to the same directory:

```bash
git clone https://github.com/spring-divas/feedo.git
```

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

Go to the service directories and set up `.env` files using `.env.example` as bases.

For the application to work correctly, host ports must be set up in `.env` files. Different services must have different host ports.
For example:
```
venue-and-menu-service: 8081
user-service: 8082
review-service: 8083
payment-service: 8084
order-service: 8085
```

---

## 3. Build all Docker images

From the `feedo` directory:

```bash
docker compose build
```

To force a clean rebuild:

```bash
docker compose build --no-cache
```

---

## 4. Launch the complete application

Start all services:

```bash
docker compose up
```

Launch in the background:

```bash
docker compose up -d
```

---

## 5. Check the application

Check running containers:

```bash
docker compose ps
```

---

## 6. Stop the application

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

## 7. Complete clean rebuild

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

## 8. Update services

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

cd ../feedo
git pull
```

Rebuild and launch:

```bash
docker compose up --build -d
```
