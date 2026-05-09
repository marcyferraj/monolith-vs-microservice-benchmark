"""
TEST 4: FAULT TOLERANCE (Graceful Degradation Under Failure)
==============================================================

PURPOSE:
    Demonstrates how each architecture responds when a component fails
    during active traffic. This is where MICROSERVICES SHINE — the rest
    of the system keeps working even when one service dies. The monolith
    has no such isolation.

WHAT THIS TESTS:
    - Trade-off dimension: FAULT TOLERANCE / FAULT ISOLATION
    - Expected winner: Microservices — clear, dramatic difference
    - Why it matters: This is one of the primary reasons companies migrate
      to microservices in the first place.

THE TEST PROCEDURE:
    This test runs continuous mixed traffic against all endpoints. While
    it's running, YOU manually kill a container in a second terminal and
    observe the impact on each endpoint type. Then restart the container
    and observe recovery.

    Locust will keep counting failures separately per endpoint, so you
    get a clear view of what's affected vs. what keeps working.

HOW TO RUN — MONOLITH:
    1. Start monolith:
        cd monolith
        docker compose up --build
    2. In a new terminal, start the test:
        python3 -m locust -f test4_fault_tolerance.py --host=http://localhost:5000 --users 20 --spawn-rate 2 --run-time 3m
    3. Open http://localhost:8089 and click "Start swarming"
    4. After 30 seconds of stable traffic, kill the monolith app container:
        # In a third terminal:
        docker ps   # find the actual container name (e.g. "monolith-app-1")
        docker stop monolith-app-1
    5. Watch the Locust UI for 30 seconds — ALL endpoints should fail.
    6. Restart it:
        docker start monolith-app-1
    7. Watch for recovery (~10-30 seconds).
    8. Let test finish, save CSVs as failures_monolith_fault.csv.

HOW TO RUN — MICROSERVICES:
    1. Start microservices:
        cd microservices
        docker compose up --build
    2. Start test (uses MICROSERVICES=1 like test2):
        MICROSERVICES=1 python3 -m locust -f test4_fault_tolerance.py --host=http://localhost:5002 --users 20 --spawn-rate 2 --run-time 3m
    3. After 30 seconds of stable traffic, kill ONLY the catalog service:
        docker ps   # find the catalog container name
        docker stop microservices-catalog-service-1
    4. CRITICAL OBSERVATION: in the Locust UI, watch which endpoints fail:
        /auth      → should KEEP WORKING (independent service)
        /orders    → should KEEP WORKING (independent service, read only)
        /products  → should FAIL (catalog service is down)
        /checkout  → should FAIL (depends on catalog service)
    5. Restart catalog:
        docker start microservices-catalog-service-1
    6. Save CSVs as failures_microservices_fault.csv.

DATA TO COLLECT:
    The KEY data is the per-endpoint failure breakdown in the Locust UI.
    Take screenshots of the Statistics tab at three points:
    - Before failure (everything green, ~0 failures)
    - During failure (showing which endpoints are affected)
    - After recovery (back to ~0 failures)

    Quantify "blast radius":
    - Monolith blast radius: 4/4 endpoints affected (100%)
    - Microservices blast radius: 2/4 endpoints affected (50%)

    Recovery time:
    - How many seconds from `docker start` until error rate returns to zero?

EXPECTED RESULTS — THE STORY YOUR DATA WILL TELL:
    MONOLITH: When the single container dies, error rate jumps to ~100%
    instantly across ALL endpoints. Recovery requires the entire app to
    come back up. There is no partial availability.

    MICROSERVICES: When the catalog service dies, /auth and /orders
    continue serving traffic with 0% error rate. Only /products and
    /checkout (which depends on catalog) fail. This is graceful
    degradation — the system stays partially available.

RESET BETWEEN RUNS:
    docker compose down -v && docker compose up --build
"""
import os
import random
from locust import HttpUser, task, between

USE_MICROSERVICES = os.getenv("MICROSERVICES", "0") == "1"

AUTH_URL = "http://localhost:5001"
CATALOG_URL = "http://localhost:5002"
ORDER_URL = "http://localhost:5003"


class FaultToleranceUser(HttpUser):
    wait_time = between(0.3, 0.8)

    @task(3)
    def browse_products(self):
        url = f"{CATALOG_URL}/products" if USE_MICROSERVICES else "/products"
        with self.client.get(url, name="/products", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                # We WANT failures recorded here so we can see the impact
                response.failure(f"Status {response.status_code}")

    @task(2)
    def check_auth(self):
        url = f"{AUTH_URL}/auth" if USE_MICROSERVICES else "/auth"
        with self.client.get(url, name="/auth", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def list_orders(self):
        url = f"{ORDER_URL}/orders" if USE_MICROSERVICES else "/orders"
        with self.client.get(url, name="/orders", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def checkout(self):
        url = f"{ORDER_URL}/checkout" if USE_MICROSERVICES else "/checkout"
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5),
        }
        with self.client.post(
            url, json=payload, name="/checkout", catch_response=True
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
