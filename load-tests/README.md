# Load Tests

Gatling load tests for the Feedo services, run against the Kubernetes cluster through the ingress.

| Simulation | Scenario | Test data |
|---|---|---|
| `OrderCreationSimulation` | create an order, then fetch it | `orders.csv` |
| `MenuBrowsingSimulation` | list venues, open a menu, open 3 dishes | none |
| `ReviewCreationSimulation` | review a dish, then its venue | `reviews.csv` |

Requirements: the application deployed to a local cluster (see [Kubernetes Setup](../README.md#kubernetes-setup)),
Java 25 and Python 3.

---

## 1. Expose the ingress

Enable the ingress controller once:

```bash
minikube addons enable ingress
```

Then, in a separate terminal, either run a tunnel (base URL `http://127.0.0.1`):

```bash
minikube tunnel
```

or port-forward the ingress controller (base URL `http://localhost:8080`):

```bash
kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 8080:80
```

Port-forwarding is fine for trying things out, but under high load it becomes a bottleneck. Use the tunnel for real
measurements.

---

## 2. Configure

Settings are in `src/gatling/resources/load-test.properties`:

```properties
baseUrl=http://localhost:8080
usersPerSec=20
rampSeconds=30
durationSeconds=60
```

Each value can be overridden with a system property (`-DusersPerSec=50`) or an environment variable
(`USERS_PER_SEC=50`).

The load ramps up to `usersPerSec` new users per second over `rampSeconds`, then holds it for `durationSeconds`.

---

## 3. Generate test data

The CSV feeders contain IDs from your cluster's databases, so they are not committed. Each machine generates its own
with `seed/seed_data.py`: it creates data through the REST API, then reads the IDs back and writes the CSVs to
`src/gatling/resources/feeders/`.

Seed the cluster with test data (also writes `orders.csv`):

```bash
python3 seed/seed_data.py --base-url http://localhost:8080
```

If the cluster already has data, only write `orders.csv`:

```bash
python3 seed/seed_data.py --base-url http://localhost:8080 --export-only
```

Before **every** `ReviewCreationSimulation` run, prepare `reviews.csv` (each row can be used only once):

```bash
python3 seed/seed_data.py --base-url http://localhost:8080 --prepare-reviews
```

Run `python3 seed/seed_data.py --help` for all options.

---

## 4. Run

Run one simulation:

```bash
./gradlew gatlingRun --simulation org.spring.divas.loadtests.order.OrderCreationSimulation
```

Run all simulations one after another:

```bash
./gradlew gatlingRun --all
```

Running `./gradlew gatlingRun` without arguments waits for a simulation number to be typed in.

---

## 5. Check the results

Reports are written to `build/reports/gatling/<simulation>-<timestamp>/index.html`.

The build fails if a simulation misses its assertions: at least 99% successful requests and a p95 response time
under 1 s (500 ms for menu browsing).
