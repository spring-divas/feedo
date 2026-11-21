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

# ---------------------------------------------------------------------------
# Static vocabularies
# ---------------------------------------------------------------------------

ALLERGENS = [
    "Gluten", "Crustaceans", "Eggs", "Fish", "Peanuts", "Soybeans", "Milk",
    "Tree nuts", "Celery", "Mustard", "Sesame", "Sulphites", "Lupin", "Molluscs",
]

# ingredient -> allergens it contains
INGREDIENTS = {
    "Wheat flour": ["Gluten"], "Mozzarella": ["Milk"], "Parmesan": ["Milk"],
    "Butter": ["Milk"], "Cream": ["Milk"], "Egg": ["Eggs"], "Shrimp": ["Crustaceans"],
    "Salmon": ["Fish"], "Tuna": ["Fish"], "Cod": ["Fish"], "Peanut sauce": ["Peanuts"],
    "Tofu": ["Soybeans"], "Soy sauce": ["Soybeans", "Gluten"], "Almonds": ["Tree nuts"],
    "Walnuts": ["Tree nuts"], "Celery": ["Celery"], "Dijon mustard": ["Mustard"],
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
    "Pesto": ["Tree nuts", "Milk"],
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

    def call(self, method, path, body=None, headers=None, retries=3, quiet=False):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
        hdrs.update(headers or {})
        last = None
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    if not raw:
                        return {}
                    try:
                        return json.loads(raw)
                    except ValueError:
                        return raw.decode()
            except urllib.error.HTTPError as e:
                last = f"{method} {path} -> {e.code} {e.read()[:200].decode(errors='replace')}"
                self.last_status, self.last_error = e.code, last
                if e.code < 500 and e.code != 429:
                    break  # client error: retrying won't help
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = f"{method} {path} -> {e}"
            time.sleep(0.5 * (2 ** attempt))
        with self.lock:
            self.errors += 1
            if not quiet and len(self.error_samples) < 10:
                self.error_samples.append(last)
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
    return round(random.uniform(3.5, 32.0) * 2) / 2  # .0 / .5 prices


def check_reachable(api, base_url):
    if not api.get("/venue/api/actuator/health", retries=1):
        sys.exit(f"Cannot reach {base_url}/venue/api/actuator/health. "
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


def export_feeders(api, out_dir, rows):
    """Write feeders/orders.csv from the data currently in the cluster.

    Each row is a valid order: a real customer, a venue, one of that venue's tables and
    1-4 of that venue's dishes ("|"-separated).
    """
    print(f"[export] building Gatling feeders from {api.base}")
    customers = [u["id"] for u in api.get("/user/api/user") or [] if u.get("role") == "CUSTOMER"]
    tables, dishes = {}, {}
    for t in api.get("/venue/api/table") or []:
        if t.get("id") is not None:
            tables.setdefault(t["venueId"], []).append(t["id"])
    for d in api.get("/venue/api/dish") or []:
        dishes.setdefault(d["venueId"], []).append(d["id"])
    venues = [v for v in tables if v in dishes]
    if not customers or not venues:
        sys.exit("[export] no customers or no venues with both tables and dishes; seed first.")

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.normpath(os.path.join(out_dir, "orders.csv"))
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["userId", "venueId", "tableId", "dishIds"])
        for _ in range(rows):
            v = random.choice(venues)
            picked = random.sample(dishes[v], k=min(len(dishes[v]), random.randint(1, 4)))
            writer.writerow([random.choice(customers), v, random.choice(tables[v]),
                             "|".join(map(str, picked))])
    print(f"  orders.csv: {rows} rows ({len(customers)} customers, {len(venues)} venues) -> {path}")


def prepare_reviews(api, out_dir, rows, workers):
    """Write feeders/reviews.csv with (user, venue, dish) rows that can each be reviewed once.

    review-service only accepts a dish review for a READY order containing the dish, and one
    review per (user, venue) and (user, dish). This marks fresh NEW orders as READY and skips
    pairs from any order past NEW, since those may already have been reviewed.
    """
    print(f"[reviews] preparing {rows} review rows from {api.base}")
    orders = api.get("/order/api/order") or []
    blocked_venues = {(o["userId"], o["venueId"]) for o in orders if o["status"] != "NEW"}
    blocked_venues |= {(r["user"]["id"], r["venueId"])
                       for r in api.get("/review/api/review/venue") or []
                       if (r.get("user") or {}).get("id") is not None}
    blocked_dishes = {(o["userId"], i["dishId"])
                      for o in orders if o["status"] != "NEW" for i in o["items"]}

    candidates = [o for o in orders if o["status"] == "NEW" and o.get("items")]
    random.shuffle(candidates)
    picked = []
    for o in candidates:
        if len(picked) == rows:
            break
        venue_pair = (o["userId"], o["venueId"])
        dish = next((i["dishId"] for i in o["items"]
                     if (o["userId"], i["dishId"]) not in blocked_dishes), None)
        if venue_pair in blocked_venues or dish is None:
            continue
        blocked_venues.add(venue_pair)
        blocked_dishes.add((o["userId"], dish))
        picked.append((o, dish))

    if len(picked) < rows:
        print(f"  ! only {len(picked)} eligible NEW orders; run the seeder to create more orders")

    def mark_ready(job):
        o, _ = job
        return api.put(f"/order/api/order/{o['id']}", {
            "userId": o["userId"], "venueId": o["venueId"], "tableId": o["tableId"],
            "status": "READY",
            "items": [{"dishId": i["dishId"], "quantity": i["quantity"]} for i in o["items"]],
        })

    res = run_parallel(workers, mark_ready, picked, "mark orders READY")
    ready = [(o, dish) for (o, dish), r in zip(picked, res) if r]

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.normpath(os.path.join(out_dir, "reviews.csv"))
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["userId", "venueId", "dishId"])
        for o, dish in ready:
            writer.writerow([o["userId"], o["venueId"], dish])
    print(f"  reviews.csv: {len(ready)} rows (each usable once) -> {path}")


# ---------------------------------------------------------------------------
# Seeding steps
# ---------------------------------------------------------------------------


def seed(args):
    random.seed(args.seed)
    api = Api(args.base_url)
    run_id = uuid.uuid4().hex[:6]
    w = args.workers
    ow = args.order_workers  # order-service exhausts its DB pool under high /pay concurrency

    check_reachable(api, args.base_url)

    print(f"Seeding {args.base_url} (run id {run_id})")

    # --- venue-and-menu-service: allergens & ingredients ----------------------
    print("[venue] allergens & ingredients")
    allergen_ids = {}
    res = run_parallel(w, lambda n: api.post("/venue/api/allergen", {"name": f"{n} {run_id}"}),
                       ALLERGENS, "allergens")
    for name, r in zip(ALLERGENS, res):
        if r:
            allergen_ids[name] = r["id"]

    ing_names = list(INGREDIENTS)
    res = run_parallel(w, lambda n: api.post("/venue/api/ingredient", {
        "name": f"{n} {run_id}",
        "quantity": random.randint(0, 500),
        "allergens": [allergen_ids[a] for a in INGREDIENTS[n] if a in allergen_ids],
    }), ing_names, "ingredients")
    ingredient_ids = [r["id"] for r in res if r and r.get("id") is not None]

    # --- venues ---------------------------------------------------------------
    print("[venue] venues, tables, categories, dishes")

    def make_venue(i):
        cuisine = random.choice(list(CUISINES))
        name = f"{random.choice(VENUE_WORDS)} {random.choice(VENUE_NOUNS)} #{i} ({cuisine})"
        addr = f"{random.randint(1, 200)} {random.choice(STREETS)}, {random.choice(CITIES)}"
        r = api.post("/venue/api/venue", {"name": name[:150], "address": addr})
        return {"id": r["id"], "cuisine": cuisine} if r else None

    venues = [v for v in run_parallel(w, make_venue, range(args.venues), "venues") if v]

    table_jobs = [(v, i) for v in venues for i in range(args.tables_per_venue)]
    res = run_parallel(w, lambda j: api.post("/venue/api/table", {
        "venueId": j[0]["id"], "isAvailable": random.random() < 0.8,
    }), table_jobs, "tables")
    for (v, _), r in zip(table_jobs, res):
        if r and r.get("id") is not None:
            v.setdefault("tables", []).append(r["id"])

    cat_jobs = [(v, c) for v in venues for c in CUISINES[v["cuisine"]]["categories"]]
    res = run_parallel(w, lambda j: api.post("/venue/api/category", {
        "venueId": j[0]["id"], "name": j[1],
    }), cat_jobs, "categories")
    for (v, _), r in zip(cat_jobs, res):
        if r:
            v.setdefault("categories", []).append(r["id"])

    dish_jobs = []
    for v in venues:
        if not v.get("categories"):
            continue
        names = CUISINES[v["cuisine"]]["dishes"]
        for i in range(args.dishes_per_venue):
            base = names[i % len(names)]
            name = base if i < len(names) else f"{base} Special {i // len(names)}"
            dish_jobs.append((v, name))
    res = run_parallel(w, lambda j: api.post("/venue/api/dish", {
        "venueId": j[0]["id"],
        "category": random.choice(j[0]["categories"]),
        "name": j[1],
        "description": f"House {j[1].lower()} made fresh daily.",
        "price": price(),
        "ingredients": random.sample(ingredient_ids, k=min(len(ingredient_ids),
                                                           random.randint(2, 6))),  # [] if none
    }), dish_jobs, "dishes")
    for (v, _), r in zip(dish_jobs, res):
        if r:
            v.setdefault("dishes", []).append(r["id"])

    venues = [v for v in venues if v.get("tables") and v.get("dishes")]
    if not venues:
        sys.exit("No usable venues (each needs tables and dishes with IDs). "
                 "Check venue-service responses.")

    # --- user-service ---------------------------------------------------------
    print("[user] customers, managers, venue managers, allergies")

    def make_user(job):
        role, i = job
        fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        r = api.post(f"/user/api/user/{role}", {
            "firstName": fn, "lastName": ln,
            "email": f"{fn.lower()}.{ln.lower()}.{role}{i}.{run_id}@feedo.test",
            "password": "Password123!",
        })
        return r["id"] if r else None

    customers = [u for u in run_parallel(
        w, make_user, [("customer", i) for i in range(args.customers)], "customers") if u]
    managers = [u for u in run_parallel(
        w, make_user, [("manager", i) for i in range(args.managers)], "managers") if u]

    vm_jobs = []
    for v in venues:
        for m in random.sample(managers, k=min(len(managers), random.randint(1, 2))):
            vm_jobs.append({"userId": m, "venueId": v["id"],
                            "managerLevel": random.choice(["JUNIOR", "SENIOR"])})
    run_parallel(w, lambda b: api.post("/user/api/venue-manager", b), vm_jobs, "venue managers")

    allergy_jobs = []
    for c in customers:
        if random.random() < 0.3:
            for a in random.sample(list(allergen_ids.values()), k=random.randint(1, 2)):
                allergy_jobs.append((c, a))
    run_parallel(w, lambda j: api.post(f"/user/api/allergy?userId={j[0]}&allergenId={j[1]}"),
                 allergy_jobs, "user allergies")

    # --- order-service --------------------------------------------------------
    # order-service keeps a replica of dishes synced over gRPC from venue-service;
    # wait until the last created dish is orderable before bulk ordering.
    print("[order] waiting for dish sync to order-service", end="", flush=True)
    probe_v = venues[-1]
    probe = None
    for _ in range(60):
        probe = api.post("/order/api/order", {
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

    def make_order(_):
        user = random.choice(customers)
        v = random.choice(venues)
        dishes = random.sample(v["dishes"], k=min(len(v["dishes"]), random.randint(1, 4)))
        body = {
            "userId": user, "venueId": v["id"], "tableId": random.choice(v["tables"]),
            "items": [{"dishId": d, "quantity": random.randint(1, 3)} for d in dishes],
        }
        r = api.post("/order/api/order", body)
        return {"id": r["id"], "user": user, "venue": v["id"], "dishes": dishes,
                "body": body} if r else None

    orders = [o for o in run_parallel(ow, make_order, range(args.orders), "orders") if o]

    # Lifecycle: ~65% paid, ~10% cancelled, rest stay NEW. Half of paid -> READY.
    random.shuffle(orders)
    n_pay = int(len(orders) * 0.65)
    n_cancel = int(len(orders) * 0.10)
    to_pay, to_cancel = orders[:n_pay], orders[n_pay:n_pay + n_cancel]

    print("[payment] paying orders via order-service -> payment-service (gRPC)")
    res = run_parallel(ow, lambda o: api.post(
        f"/order/api/order/{o['id']}/pay?simulateFailure={'true' if random.random() < 0.05 else 'false'}"),
        to_pay, "payments")
    paid = [o for o, r in zip(to_pay, res) if r and r.get("status") == "PAID"]
    print(f"  orders PAID: {len(paid)}  (others PAYMENT_FAILED / pending)")

    run_parallel(ow, lambda o: api.call(
        "PATCH", f"/order/api/order/{o['id']}/cancel?reason=Changed%20my%20mind"),
        to_cancel, "cancellations")

    to_ready = paid[: len(paid) // 2 + 1] if paid else []
    res = run_parallel(ow, lambda o: api.put(f"/order/api/order/{o['id']}",
                                            {**o["body"], "status": "READY"}),
                       to_ready, "mark READY")
    ready = [o for o, r in zip(to_ready, res) if r]

    # --- review-service -------------------------------------------------------
    print("[review] venue & dish reviews")

    def review_body(target_key, target_id, user):
        rating = random.choices([5, 4, 3, 2, 1], weights=[35, 30, 18, 10, 7])[0]
        return {"rating": rating, "content": random.choice(REVIEW_TEXTS[rating]),
                target_key: target_id, "userId": user}

    venue_pairs = list({(o["user"], o["venue"]) for o in orders})
    venue_pairs = random.sample(venue_pairs, k=int(len(venue_pairs) * args.review_ratio))
    run_parallel(w, lambda p: api.post("/review/api/review/venue",
                                       review_body("venueId", p[1], p[0])),
                 venue_pairs, "venue reviews")

    dish_pairs = list({(o["user"], d) for o in ready for d in o["dishes"]})
    dish_pairs = random.sample(dish_pairs, k=int(len(dish_pairs) * args.review_ratio))
    run_parallel(w, lambda p: api.post("/review/api/review/dish",
                                       review_body("dishId", p[1], p[0])),
                 dish_pairs, "dish reviews")

    # --- summary --------------------------------------------------------------
    print("\nDone.")
    print(f"  venues={len(venues)} tables={sum(len(v['tables']) for v in venues)} "
          f"dishes={sum(len(v['dishes']) for v in venues)} ingredients={len(ingredient_ids)} "
          f"allergens={len(allergen_ids)}")
    print(f"  customers={len(customers)} managers={len(managers)} "
          f"venue-managers={len(vm_jobs)} allergies={len(allergy_jobs)}")
    print(f"  orders={len(orders)} paid={len(paid)} ready={len(ready)} cancelled~={len(to_cancel)}")
    print(f"  venue-reviews~={len(venue_pairs)} dish-reviews~={len(dish_pairs)}")
    if api.errors:
        print(f"\n  {api.errors} failed requests. Samples:")
        for s in api.error_samples:
            print(f"    {s}")

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
                   help="skip seeding; mark orders READY and write reviews.csv (run before "
                        "every ReviewCreationSimulation run, rows are consumed)")
    p.add_argument("--review-rows", type=int, default=None,
                   help="rows in reviews.csv (default: enough for the users configured in "
                        "load-test.properties / env)")
    args = p.parse_args()

    if args.export_only or args.prepare_reviews:
        random.seed(args.seed)
        api = Api(args.base_url)
        check_reachable(api, args.base_url)
        if args.export_only:
            export_feeders(api, args.export_dir, args.export_rows)
        if args.prepare_reviews:
            rows = args.review_rows if args.review_rows is not None else required_review_rows()
            prepare_reviews(api, args.export_dir, rows, args.order_workers)
    else:
        seed(args)


if __name__ == "__main__":
    main()
