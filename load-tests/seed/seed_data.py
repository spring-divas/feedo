#!/usr/bin/env python3
"""
Seed the Feedo services with realistic test data through the public REST API (ingress).

Creates, in dependency order:
  venue-and-menu-service : allergens, ingredients, venues, tables, categories, dishes
  user-service           : customers, managers, venue-manager links, user allergies
  order-service          : orders (some paid, cancelled or marked READY)
  payment-service        : payments (created via order-service /pay over gRPC)
  review-service         : venue reviews and dish reviews (only valid combos)

Every run adds new data (emails get a unique run id), so it can be re-run safely.
Only uses the Python standard library.

Usage:
  # cluster reachable via `minikube tunnel`
  python3 seed_data.py

  # via port-forward: kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 8080:80
  python3 seed_data.py --base-url http://localhost:8080

  # bigger dataset
  python3 seed_data.py --venues 100 --customers 2000 --orders 10000 --workers 32

  # only (re)generate the Gatling feeder CSVs from the data already in the cluster
  python3 seed_data.py --export-only

  # prepare one-time review data for ReviewCreationSimulation (rerun before each run)
  python3 seed_data.py --prepare-reviews

After seeding, Gatling feeders are written to ../src/gatling/resources/feeders/.
"""

import argparse
import csv
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

TTY = sys.stdout.isatty()

# Test-data generation only: values are not security-sensitive and must be reproducible with --seed.
RNG = random.Random()  # NOSONAR

ORDER_API = "/api/order"
USER_PASSWORD = "Password123!"

# ---------------------------------------------------------------------------
# Static vocabularies
# ---------------------------------------------------------------------------

TREE_NUTS = "Tree nuts"

ALLERGENS = [
    "Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk",
    TREE_NUTS, "Celery", "Mustard", "Sesame", "Sulphites", "Lupin", "Molluscs",
]

# ingredient -> allergens it contains
INGREDIENTS = {
    "Wheat flour": ["Gluten"], "Mozzarella": ["Milk"], "Parmesan": ["Milk"],
    "Butter": ["Milk"], "Cream": ["Milk"], "Egg": ["Eggs"], "Shrimp": ["Crustaceans"],
    "Salmon": ["Fish"], "Tuna": ["Fish"], "Cod": ["Fish"], "Peanut sauce": ["Peanuts"],
    "Tofu": ["Soybeans"], "Soy sauce": ["Soybeans", "Gluten"], "Almonds": [TREE_NUTS],
    "Walnuts": [TREE_NUTS], "Celery": ["Celery"], "Dijon mustard": ["Mustard"],
    "Sesame seeds": ["Sesame"], "Tahini": ["Sesame"], "White wine": ["Sulphites"],
    "Mussels": ["Molluscs"], "Squid": ["Molluscs"], "Pasta": ["Gluten", "Eggs"],
    "Brioche bun": ["Gluten", "Eggs", "Milk"], "Mayonnaise": ["Eggs", "Mustard"],
    "Tomato": [], "Basil": [], "Garlic": [], "Onion": [], "Olive oil": [],
    "Chicken breast": [], "Beef patty": [], "Pork belly": [], "Lamb": [], "Rice": [],
    "Potato": [], "Avocado": [], "Lettuce": [], "Cucumber": [], "Bell pepper": [],
    "Mushrooms": [], "Spinach": [], "Chili": [], "Lime": [], "Lemon": [],
    "Coriander": [], "Ginger": [], "Black beans": [], "Corn": [], "Chickpeas": [],
    "Dark chocolate": ["Milk"], "Strawberries": [], "Mango": [], "Coconut milk": [],
    "Honey": [], "Bacon": [], "Cheddar": ["Milk"], "Feta": ["Milk"], "Olives": [],
    "Pesto": [TREE_NUTS, "Milk"],
}

CUISINES = {
    "Italian": {
        "categories": ["Pizza", "Pasta", "Antipasti", "Desserts", "Drinks"],
        "dishes": ["Margherita", "Diavola", "Quattro Formaggi", "Carbonara", "Bolognese",
                   "Pesto Genovese", "Lasagna", "Bruschetta", "Caprese", "Tiramisu",
                   "Panna Cotta", "Arancini", "Risotto ai Funghi", "Calzone", "Minestrone"],
    },
    "Japanese": {
        "categories": ["Sushi", "Ramen", "Starters", "Desserts", "Drinks"],
        "dishes": ["Salmon Nigiri", "Tuna Maki", "California Roll", "Tonkotsu Ramen",
                   "Miso Ramen", "Gyoza", "Edamame", "Tempura Shrimp", "Chicken Katsu",
                   "Mochi", "Matcha Cheesecake", "Teriyaki Salmon", "Onigiri", "Takoyaki"],
    },
    "Mexican": {
        "categories": ["Tacos", "Burritos", "Sides", "Desserts", "Drinks"],
        "dishes": ["Carnitas Taco", "Fish Taco", "Al Pastor Taco", "Beef Burrito",
                   "Veggie Burrito", "Quesadilla", "Nachos", "Guacamole", "Elote",
                   "Churros", "Tres Leches", "Enchiladas", "Tamales", "Pozole"],
    },
    "American": {
        "categories": ["Burgers", "Grill", "Sides", "Desserts", "Drinks"],
        "dishes": ["Classic Burger", "Bacon Cheeseburger", "BBQ Ribs", "Buffalo Wings",
                   "Mac and Cheese", "Fries", "Onion Rings", "Caesar Salad", "Club Sandwich",
                   "Brownie", "Cheesecake", "Pulled Pork Sandwich", "Hot Dog", "Milkshake"],
    },
    "Indian": {
        "categories": ["Curries", "Tandoor", "Breads", "Desserts", "Drinks"],
        "dishes": ["Butter Chicken", "Chicken Tikka Masala", "Palak Paneer", "Lamb Rogan Josh",
                   "Chana Masala", "Tandoori Chicken", "Garlic Naan", "Samosa", "Biryani",
                   "Dal Makhani", "Gulab Jamun", "Mango Lassi", "Pakora", "Korma"],
    },
    "Mediterranean": {
        "categories": ["Mezze", "Grill", "Salads", "Desserts", "Drinks"],
        "dishes": ["Hummus", "Falafel", "Shawarma", "Greek Salad", "Moussaka", "Souvlaki",
                   "Tabbouleh", "Baba Ganoush", "Spanakopita", "Baklava", "Halloumi",
                   "Grilled Octopus", "Dolma", "Lamb Kofta"],
    },
}

FIRST_NAMES = ["Olena", "Andrii", "Maria", "Taras", "Iryna", "Dmytro", "Sofia", "Oleh",
               "Anna", "Maksym", "Kateryna", "Ivan", "Yulia", "Bohdan", "Daria", "Serhii",
               "Emma", "Liam", "Noah", "Olivia", "Mia", "Lucas", "Ava", "Ethan", "Zoe",
               "Leo", "Nina", "Adam", "Eva", "Mark"]
LAST_NAMES = ["Shevchenko", "Kovalenko", "Bondarenko", "Tkachenko", "Kravchenko", "Melnyk",
              "Boyko", "Koval", "Oliinyk", "Lysenko", "Smith", "Johnson", "Brown", "Garcia",
              "Miller", "Davis", "Martinez", "Wilson", "Anderson", "Taylor"]
STREETS = ["Khreshchatyk", "Shevchenka", "Franka", "Lesi Ukrainky", "Sahaidachnoho",
           "Velyka Vasylkivska", "Main St", "Oak Ave", "Park Rd", "River Ln", "Market Sq"]
CITIES = ["Kyiv", "Lviv", "Odesa", "Kharkiv", "Dnipro", "Vinnytsia"]
VENUE_WORDS = ["Golden", "Little", "Blue", "Rustic", "Urban", "Happy", "Old Town", "Green",
               "Royal", "Cozy", "Sunny", "Hidden", "Wild", "Corner", "Lucky"]
VENUE_NOUNS = ["Kitchen", "Bistro", "House", "Table", "Spoon", "Garden", "Grill", "Cantina",
               "Trattoria", "Diner", "Eatery", "Corner", "Fork", "Oven", "Bar"]

REVIEW_TEXTS = {
    5: ["Absolutely loved it!", "Best I've had in town.", "Perfect, will come back.",
        "Outstanding quality and service."],
    4: ["Really good, minor nitpicks.", "Tasty and fresh.", "Great value for money.",
        "Very nice, would recommend."],
    3: ["It was okay.", "Decent but nothing special.", "Average experience.",
        "Fine, but a bit overpriced."],
    2: ["Not great, quite bland.", "Took too long to arrive.", "Below expectations.",
        "Portion was too small."],
    1: ["Terrible, would not recommend.", "Cold and tasteless.", "Very disappointing.",
        "Worst experience so far."],
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


class Api:
    def __init__(self, base_url, timeout=30):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.errors = 0
        self.lock = threading.Lock()
        self.error_samples = []
        self.last_status = None
        self.last_error = None

    def _send(self, req):
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return raw.decode()

    def _record_failure(self, error, quiet):
        with self.lock:
            self.errors += 1
            if not quiet and len(self.error_samples) < 10:
                self.error_samples.append(error)

    def call(self, method, path, body=None, headers=None, retries=3, quiet=False):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
        hdrs.update(headers or {})
        last = None
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            try:
                return self._send(req)
            except urllib.error.HTTPError as e:
                last = f"{method} {path} -> {e.code} {e.read()[:200].decode(errors='replace')}"
                self.last_status, self.last_error = e.code, last
                if e.code < 500 and e.code != 429:
                    break  # client error: retrying won't help
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = f"{method} {path} -> {e}"
                self.last_status, self.last_error = None, last
            time.sleep(0.5 * (2 ** attempt))
        self._record_failure(last, quiet)
        return None

    def post(self, path, body=None, **kw):
        return self.call("POST", path, body, **kw)

    def put(self, path, body, **kw):
        return self.call("PUT", path, body, **kw)

    def get(self, path, **kw):
        return self.call("GET", path, **kw)


def run_parallel(workers, fn, items, label):
    """Run fn over items in parallel, print progress, return non-None results in order."""
    items = list(items)
    total = len(items)
    done = [0]
    lock = threading.Lock()
    started = time.time()

    def wrapped(item):
        result = fn(item)
        with lock:
            done[0] += 1
            if TTY and (done[0] % max(1, total // 20) == 0 or done[0] == total):
                print(f"\r  {label}: {done[0]}/{total}", end="", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(wrapped, items))
    ok = [r for r in results if r is not None]
    print(f"\r  {label}: {len(ok)}/{total} ok ({time.time() - started:.1f}s)")
    return results


def price():
    return round(RNG.uniform(3.5, 32.0) * 2) / 2  # .0 / .5 prices


def check_reachable(api, base_url):
    if not api.get("/api/auth/public-key", retries=1):
        sys.exit(f"Cannot reach {base_url}/api/auth/public-key. "
                 f"Is `minikube tunnel` or the ingress port-forward running?")


# ---------------------------------------------------------------------------
# Gatling feeder export
# ---------------------------------------------------------------------------

DEFAULT_FEEDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "src", "gatling", "resources", "feeders")
LOAD_TEST_PROPERTIES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "src", "gatling", "resources", "load-test.properties")


def load_test_setting(prop, env_var):
    """Same lookup as LoadTestConfig (minus -D): environment variable, then load-test.properties."""
    value = os.environ.get(env_var, "").strip()
    if not value and os.path.exists(LOAD_TEST_PROPERTIES):
        with open(LOAD_TEST_PROPERTIES) as f:
            for line in f:
                key, sep, val = line.partition("=")
                if sep and key.strip() == prop:
                    value = val.strip()
    if not value:
        sys.exit(f"Missing load test setting '{prop}' ({env_var} or {LOAD_TEST_PROPERTIES})")
    return float(value)


def required_review_rows():
    """Upper bound of users ReviewCreationSimulation injects: the ramp never exceeds usersPerSec."""
    users_per_sec = load_test_setting("usersPerSec", "USERS_PER_SEC")
    seconds = (load_test_setting("rampSeconds", "RAMP_SECONDS")
               + load_test_setting("durationSeconds", "DURATION_SECONDS"))
    return int(users_per_sec * seconds + 0.999999)


REVIEW_ROWS_PER_CUSTOMER = 20


def require(api, result, what):
    if result is None:
        sys.exit(f"Could not load {what}. Is the service up? Last error: {api.last_error}")
    return result


def load_venue_catalog(api):
    """Venues that have both tables and dishes, with their table and dish IDs."""
    tables, dishes = {}, {}
    for t in require(api, api.get("/api/table"), "tables from venue-service"):
        if t.get("id") is not None:
            tables.setdefault(t["venueId"], []).append(t["id"])
    for d in require(api, api.get("/api/dish"), "dishes from venue-service"):
        dishes.setdefault(d["venueId"], []).append(d["id"])
    venues = [v for v in tables if v in dishes]
    if not venues:
        sys.exit("No venues with both tables and dishes; run the seeder first.")
    return venues, tables, dishes


def create_user(api, run_id, index, role="customer", label=None):
    first, last = RNG.choice(FIRST_NAMES), RNG.choice(LAST_NAMES)
    r = api.post(f"/api/user/{role}", {
        "firstName": first, "lastName": last,
        "email": f"{first.lower()}.{last.lower()}.{label or role}{index}.{run_id}@feedo.test",
        "password": USER_PASSWORD,
    })
    return r["id"] if r else None


def export_feeders(api, out_dir, rows):
    """Write feeders/orders.csv from the data currently in the cluster.

    Each row is a valid order: a real customer, a venue, one of that venue's tables and
    1-4 of that venue's dishes ("|"-separated).
    """
    print(f"[export] building Gatling feeders from {api.base}")
    users = require(api, api.get("/api/user"), "users from user-service")
    customers = [u["id"] for u in users if u.get("role") == "CUSTOMER"]
    if not customers:
        sys.exit("[export] no customers; run the seeder first.")
    venues, tables, dishes = load_venue_catalog(api)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.normpath(os.path.join(out_dir, "orders.csv"))
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["userId", "venueId", "tableId", "dishIds"])
        for _ in range(rows):
            v = RNG.choice(venues)
            picked = RNG.sample(dishes[v], k=min(len(dishes[v]), RNG.randint(1, 4)))
            writer.writerow([RNG.choice(customers), v, RNG.choice(tables[v]),
                             "|".join(map(str, picked))])
    print(f"  orders.csv: {rows} rows ({len(customers)} customers, {len(venues)} venues) -> {path}")


def prepare_reviews(api, out_dir, rows, workers, order_workers):
    """Write feeders/reviews.csv with (user, venue, dish) rows that can each be reviewed once.

    review-service accepts one review per (user, venue) and (user, dish), and a dish review only
    for a READY order containing the dish. Fresh customers have no orders or reviews, so each row
    gets a new customer/venue pair and a READY order created for it.
    """
    print(f"[reviews] preparing {rows} review rows from {api.base}")
    venues, tables, dishes = load_venue_catalog(api)
    per_customer = min(len(venues), REVIEW_ROWS_PER_CUSTOMER)
    run_id = uuid.uuid4().hex[:6]

    customer_count = -(-rows // per_customer)
    res = run_parallel(workers, lambda i: create_user(api, run_id, i, label="reviewer"),
                       range(customer_count), "review customers")
    customers = [c for c in res if c]
    if not customers:
        sys.exit(f"Could not create customers in user-service: {api.last_error}")

    jobs = []
    for customer in customers:
        for venue in RNG.sample(venues, per_customer):
            if len(jobs) < rows:
                jobs.append((customer, venue, RNG.choice(tables[venue]),
                             RNG.choice(dishes[venue])))

    def create_ready_order(job):
        customer, venue, table, dish = job
        body = {"userId": customer, "venueId": venue, "tableId": table,
                "items": [{"dishId": dish, "quantity": 1}]}
        created = api.post(ORDER_API, body)
        if not created:
            return None
        return api.put(f"{ORDER_API}/{created['id']}", {**body, "status": "READY"})

    res = run_parallel(order_workers, create_ready_order, jobs, "READY orders")
    ready = [job for job, r in zip(jobs, res) if r]

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.normpath(os.path.join(out_dir, "reviews.csv"))
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["userId", "venueId", "dishId"])
        for customer, venue, _, dish in ready:
            writer.writerow([customer, venue, dish])
    print(f"  reviews.csv: {len(ready)} rows (each usable once) -> {path}")

    if len(ready) < rows:
        for sample in api.error_samples:
            print(f"    {sample}")
        sys.exit(f"Only {len(ready)}/{rows} rows prepared; order-service rejected or dropped the rest.")


# ---------------------------------------------------------------------------
# Seeding steps
# ---------------------------------------------------------------------------


def seed_allergens_and_ingredients(api, run_id, workers):
    print("[venue] allergens & ingredients")
    res = run_parallel(workers, lambda n: api.post("/api/allergen", {"name": f"{n} {run_id}"}),
                       ALLERGENS, "allergens")
    allergen_ids = {name: r["id"] for name, r in zip(ALLERGENS, res) if r}

    res = run_parallel(workers, lambda n: api.post("/api/ingredient", {
        "name": f"{n} {run_id}",
        "quantity": RNG.randint(0, 500),
        "allergens": [allergen_ids[a] for a in INGREDIENTS[n] if a in allergen_ids],
    }), list(INGREDIENTS), "ingredients")
    ingredient_ids = [r["id"] for r in res if r and r.get("id") is not None]
    return allergen_ids, ingredient_ids


def create_venue(api, i):
    cuisine = RNG.choice(list(CUISINES))
    name = f"{RNG.choice(VENUE_WORDS)} {RNG.choice(VENUE_NOUNS)} #{i} ({cuisine})"
    addr = f"{RNG.randint(1, 200)} {RNG.choice(STREETS)}, {RNG.choice(CITIES)}"
    r = api.post("/api/venue", {"name": name[:150], "address": addr})
    return {"id": r["id"], "cuisine": cuisine} if r else None


def attach_ids(jobs, results, key):
    """Append the id of each successful result to its venue (first element of the job)."""
    for (venue, _), r in zip(jobs, results):
        if r and r.get("id") is not None:
            venue.setdefault(key, []).append(r["id"])


def dish_names(cuisine, count):
    names = CUISINES[cuisine]["dishes"]
    for i in range(count):
        base = names[i % len(names)]
        yield base if i < len(names) else f"{base} Special {i // len(names)}"


def dish_body(venue, name, ingredient_ids):
    return {
        "venueId": venue["id"],
        "category": RNG.choice(venue["categories"]),
        "name": name,
        "description": f"House {name.lower()} made fresh daily.",
        "price": price(),
        "ingredients": RNG.sample(ingredient_ids, k=min(len(ingredient_ids),
                                                           RNG.randint(2, 6))),  # [] if none
    }


def seed_venues(api, args, ingredient_ids):
    print("[venue] venues, tables, categories, dishes")
    w = args.workers
    venues = [v for v in run_parallel(w, lambda i: create_venue(api, i), range(args.venues), "venues")
              if v]

    table_jobs = [(v, i) for v in venues for i in range(args.tables_per_venue)]
    res = run_parallel(w, lambda j: api.post("/api/table", {
        "venueId": j[0]["id"], "isAvailable": RNG.random() < 0.8,
    }), table_jobs, "tables")
    attach_ids(table_jobs, res, "tables")

    cat_jobs = [(v, c) for v in venues for c in CUISINES[v["cuisine"]]["categories"]]
    res = run_parallel(w, lambda j: api.post("/api/category", {
        "venueId": j[0]["id"], "name": j[1],
    }), cat_jobs, "categories")
    attach_ids(cat_jobs, res, "categories")

    dish_jobs = [(v, name) for v in venues if v.get("categories")
                 for name in dish_names(v["cuisine"], args.dishes_per_venue)]
    res = run_parallel(w, lambda j: api.post("/api/dish", dish_body(j[0], j[1], ingredient_ids)),
                       dish_jobs, "dishes")
    attach_ids(dish_jobs, res, "dishes")

    venues = [v for v in venues if v.get("tables") and v.get("dishes")]
    if not venues:
        sys.exit("No usable venues (each needs tables and dishes with IDs). "
                 "Check venue-service responses.")
    return venues


def venue_manager_jobs(venues, managers):
    return [{"userId": m, "venueId": v["id"], "managerLevel": RNG.choice(["JUNIOR", "SENIOR"])}
            for v in venues
            for m in RNG.sample(managers, k=min(len(managers), RNG.randint(1, 2)))]


def allergy_jobs_for(customers, allergen_ids):
    jobs = []
    for c in customers:
        if RNG.random() < 0.3:
            jobs.extend((c, a) for a in RNG.sample(list(allergen_ids.values()), k=RNG.randint(1, 2)))
    return jobs


def seed_users(api, run_id, args, venues, allergen_ids):
    print("[user] customers, managers, venue managers, allergies")
    w = args.workers
    customers = [u for u in run_parallel(
        w, lambda i: create_user(api, run_id, i, "customer"), range(args.customers), "customers") if u]
    managers = [u for u in run_parallel(
        w, lambda i: create_user(api, run_id, i, "manager"), range(args.managers), "managers") if u]

    vm_jobs = venue_manager_jobs(venues, managers)
    run_parallel(w, lambda b: api.post("/api/venue-manager", b), vm_jobs, "venue managers")

    allergy_jobs = allergy_jobs_for(customers, allergen_ids)
    run_parallel(w, lambda j: api.post(f"/api/allergy?userId={j[0]}&allergenId={j[1]}"),
                 allergy_jobs, "user allergies")
    return customers, managers, len(vm_jobs), len(allergy_jobs)


def wait_for_dish_sync(api, venues, customers):
    """order-service keeps a replica of dishes synced over gRPC from venue-service;
    wait until the last created dish is orderable before bulk ordering."""
    print("[order] waiting for dish sync to order-service", end="", flush=True)
    probe_v = venues[-1]
    for _ in range(60):
        probe = api.post(ORDER_API, {
            "userId": customers[0], "venueId": probe_v["id"], "tableId": probe_v["tables"][0],
            "items": [{"dishId": probe_v["dishes"][-1], "quantity": 1}],
        }, retries=1, quiet=True)
        if probe and probe.get("items"):
            break
        if probe is None and api.last_status == 400:
            sys.exit(f"\nOrder request rejected: {api.last_error}")
        print(".", end="", flush=True)
        time.sleep(2)
    else:
        sys.exit("\nDishes never became orderable in order-service; check its gRPC dish stream.")
    api.errors = 0
    api.error_samples.clear()
    print(" ok")


def create_order(api, customers, venues):
    user = RNG.choice(customers)
    v = RNG.choice(venues)
    dishes = RNG.sample(v["dishes"], k=min(len(v["dishes"]), RNG.randint(1, 4)))
    body = {
        "userId": user, "venueId": v["id"], "tableId": RNG.choice(v["tables"]),
        "items": [{"dishId": d, "quantity": RNG.randint(1, 3)} for d in dishes],
    }
    r = api.post(ORDER_API, body)
    return {"id": r["id"], "user": user, "venue": v["id"], "dishes": dishes,
            "body": body} if r else None


def pay_order(api, order):
    fail = "true" if RNG.random() < 0.05 else "false"
    return api.post(f"{ORDER_API}/{order['id']}/pay?simulateFailure={fail}")


def seed_orders(api, args, customers, venues):
    ow = args.order_workers  # order-service exhausts its DB pool under high /pay concurrency
    orders = [o for o in run_parallel(ow, lambda _: create_order(api, customers, venues),
                                      range(args.orders), "orders") if o]

    # Lifecycle: ~65% paid, ~10% cancelled, rest stay NEW. Half of paid -> READY.
    RNG.shuffle(orders)
    n_pay = int(len(orders) * 0.65)
    n_cancel = int(len(orders) * 0.10)
    to_pay, to_cancel = orders[:n_pay], orders[n_pay:n_pay + n_cancel]

    print("[payment] paying orders via order-service -> payment-service (gRPC)")
    res = run_parallel(ow, lambda o: pay_order(api, o), to_pay, "payments")
    paid = [o for o, r in zip(to_pay, res) if r and r.get("status") == "PAID"]
    print(f"  orders PAID: {len(paid)}  (others PAYMENT_FAILED / pending)")

    run_parallel(ow, lambda o: api.call(
        "PATCH", f"{ORDER_API}/{o['id']}/cancel?reason=Changed%20my%20mind"),
        to_cancel, "cancellations")

    to_ready = paid[: len(paid) // 2 + 1] if paid else []
    res = run_parallel(ow, lambda o: api.put(f"{ORDER_API}/{o['id']}",
                                            {**o["body"], "status": "READY"}),
                       to_ready, "mark READY")
    ready = [o for o, r in zip(to_ready, res) if r]
    return orders, paid, ready, to_cancel


def review_body(target_key, target_id, user):
    rating = RNG.choices([5, 4, 3, 2, 1], weights=[35, 30, 18, 10, 7])[0]
    return {"rating": rating, "content": RNG.choice(REVIEW_TEXTS[rating]),
            target_key: target_id, "userId": user}


def seed_reviews(api, args, orders, ready):
    print("[review] venue & dish reviews")
    w = args.workers
    venue_pairs = list({(o["user"], o["venue"]) for o in orders})
    venue_pairs = RNG.sample(venue_pairs, k=int(len(venue_pairs) * args.review_ratio))
    run_parallel(w, lambda p: api.post("/api/review/venue",
                                       review_body("venueId", p[1], p[0])),
                 venue_pairs, "venue reviews")

    dish_pairs = list({(o["user"], d) for o in ready for d in o["dishes"]})
    dish_pairs = RNG.sample(dish_pairs, k=int(len(dish_pairs) * args.review_ratio))
    run_parallel(w, lambda p: api.post("/api/review/dish",
                                       review_body("dishId", p[1], p[0])),
                 dish_pairs, "dish reviews")
    return len(venue_pairs), len(dish_pairs)


def print_summary(api, counts):
    print("\nDone.")
    print("  venues={venues} tables={tables} dishes={dishes} ingredients={ingredients} "
          "allergens={allergens}".format(**counts))
    print("  customers={customers} managers={managers} "
          "venue-managers={venue_managers} allergies={allergies}".format(**counts))
    print("  orders={orders} paid={paid} ready={ready} cancelled~={cancelled}".format(**counts))
    print("  venue-reviews~={venue_reviews} dish-reviews~={dish_reviews}".format(**counts))
    if api.errors:
        print(f"\n  {api.errors} failed requests. Samples:")
        for s in api.error_samples:
            print(f"    {s}")


def seed(args):
    RNG.seed(args.seed)
    api = Api(args.base_url)
    run_id = uuid.uuid4().hex[:6]

    check_reachable(api, args.base_url)
    print(f"Seeding {args.base_url} (run id {run_id})")

    allergen_ids, ingredient_ids = seed_allergens_and_ingredients(api, run_id, args.workers)
    venues = seed_venues(api, args, ingredient_ids)
    customers, managers, n_vm, n_allergies = seed_users(api, run_id, args, venues, allergen_ids)
    wait_for_dish_sync(api, venues, customers)
    orders, paid, ready, cancelled = seed_orders(api, args, customers, venues)
    n_venue_reviews, n_dish_reviews = seed_reviews(api, args, orders, ready)

    print_summary(api, {
        "venues": len(venues), "tables": sum(len(v["tables"]) for v in venues),
        "dishes": sum(len(v["dishes"]) for v in venues), "ingredients": len(ingredient_ids),
        "allergens": len(allergen_ids), "customers": len(customers), "managers": len(managers),
        "venue_managers": n_vm, "allergies": n_allergies, "orders": len(orders),
        "paid": len(paid), "ready": len(ready), "cancelled": len(cancelled),
        "venue_reviews": n_venue_reviews, "dish_reviews": n_dish_reviews,
    })

    print()
    export_feeders(api, args.export_dir, args.export_rows)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://127.0.0.1",
                   help="ingress base URL (default: http://127.0.0.1 via `minikube tunnel`)")
    p.add_argument("--venues", type=int, default=40)
    p.add_argument("--tables-per-venue", type=int, default=12)
    p.add_argument("--dishes-per-venue", type=int, default=20)
    p.add_argument("--customers", type=int, default=600)
    p.add_argument("--managers", type=int, default=40)
    p.add_argument("--orders", type=int, default=3000)
    p.add_argument("--review-ratio", type=float, default=0.6,
                   help="share of eligible (user, venue/dish) pairs that get a review")
    p.add_argument("--workers", type=int, default=16, help="parallel HTTP requests")
    p.add_argument("--order-workers", type=int, default=4,
                   help="parallel requests for order-service steps (create/pay/cancel); "
                        "order-service holds a DB connection while waiting on gRPC in /pay")
    p.add_argument("--seed", type=int, default=None, help="random seed for reproducible data")
    p.add_argument("--export-only", action="store_true",
                   help="skip seeding; only write Gatling feeder CSVs from existing data")
    p.add_argument("--export-rows", type=int, default=5000, help="rows in orders.csv")
    p.add_argument("--export-dir", default=DEFAULT_FEEDER_DIR, help="feeder output directory")
    p.add_argument("--prepare-reviews", action="store_true",
                   help="skip seeding; create fresh customers with READY orders and write "
                        "reviews.csv (run before every ReviewCreationSimulation run, rows are "
                        "consumed)")
    p.add_argument("--review-rows", type=int, default=None,
                   help="rows in reviews.csv (default: enough for the users configured in "
                        "load-test.properties / env)")
    args = p.parse_args()

    if args.export_only or args.prepare_reviews:
        RNG.seed(args.seed)
        api = Api(args.base_url)
        check_reachable(api, args.base_url)
        if args.export_only:
            export_feeders(api, args.export_dir, args.export_rows)
        if args.prepare_reviews:
            rows = args.review_rows if args.review_rows is not None else required_review_rows()
            prepare_reviews(api, args.export_dir, rows, args.workers, args.order_workers)
    else:
        seed(args)


if __name__ == "__main__":
    main()
