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

Go to the service directories and set up `.env` files using `.env.example` as bases. You can copy the contents of the
`.env.example` files by running this command in the parent directory:

```
for file in */.env.example; do
    cp "$file" "${file%.example}";
done
```

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

---

# Kubernetes Setup

`k8s/kustomization.yaml` combines the `k8s` manifests of all services, so the complete application can be deployed to a
local cluster with a single command.

Requirements: Docker, `kubectl` and a local cluster (`minikube` or Docker Desktop Kubernetes).

## 1. Clone the repositories

Clone all repositories to the same directory as described in [Build and Launch](#build-and-launch). The kustomization
references the services by relative paths, so the directory structure must be the same.

---

## 2. Configure secrets

Each service has a `k8s/*-secret.yaml.example` file. Copy them to `*-secret.yaml` by running this command in the parent
directory:

```bash
for file in */k8s/*-secret.yaml.example; do
    cp "$file" "${file%.example}";
done
```

The `*-secret.yaml` files are ignored by Git. Change the example values if needed.

`user-service/k8s/user-secret.yaml` additionally requires an RSA key pair for JWT. Generate it:

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
```

Paste the contents of the files in place of the `private.pem` and `public.pem` placeholders in `user-secret.yaml`,
keeping the indentation of the block.

---

## 3. Start the cluster

With `minikube`:

```bash
minikube start
```

With Docker Desktop, enable Kubernetes in the settings and select its context:

```bash
kubectl config use-context docker-desktop
```

---

## 4. Build the Docker images

The manifests use locally built images with fixed names, which are different from the names produced by
`docker compose build`. Build them from the parent directory:

```bash
docker build -t venue-service:latest venue-and-menu-service
docker build -t user-service:latest user-service
docker build -t review-service:latest review-service
docker build -t order-service:latest order-service
docker build -t payment-service:latest payment-service
```

With `minikube`, load the images into the cluster:

```bash
minikube image load venue-service:latest
minikube image load user-service:latest
minikube image load review-service:latest
minikube image load order-service:latest
minikube image load payment-service:latest
```

Docker Desktop Kubernetes can use the locally built images, so no image loading step is required.

---

## 5. Validate the manifests

From the `feedo` directory, render the combined manifests:

```bash
kubectl kustomize k8s
```

Validate them against the Kubernetes API server:

```bash
kubectl apply -k k8s --dry-run=server
```

---

## 6. Deploy the complete application

From the `feedo` directory:

```bash
kubectl apply -k k8s
```

This creates a database and two replicas for each service, along with their ConfigMaps, Secrets, Services and
PersistentVolumeClaims.

---

## 7. Check the application

Check the pods and wait until all of them are ready:

```bash
kubectl get pods
```

Check the deployments and services:

```bash
kubectl get deployments
kubectl get services
```

View the logs of a service:

```bash
kubectl logs deployment/order-service
```

---

## 8. Access the services

The services are only exposed inside the cluster (`ClusterIP`) on port `8080`. Use port forwarding to access them from
the host, each in a separate terminal:

```bash
kubectl port-forward svc/venue-service 8081:8080
kubectl port-forward svc/user-service 8082:8080
kubectl port-forward svc/review-service 8083:8080
kubectl port-forward svc/payment-service 8084:8080
kubectl port-forward svc/order-service 8085:8080
```

For example, check the health of the `venue-service`:

```bash
curl http://localhost:8081/api/actuator/health
```

---

## 9. Update services

After pulling the changes, rebuild the image of the updated service, load it into `minikube` if needed, and restart its
deployment:

```bash
docker build -t order-service:latest ../order-service
minikube image load order-service:latest
kubectl rollout restart deployment/order-service
```

If the manifests have changed, apply them again:

```bash
kubectl apply -k k8s
```

---

## 10. Remove the application

Remove all resources, including the database volumes:

```bash
kubectl delete -k k8s
```

Stop the `minikube` cluster:

```bash
minikube stop
```
