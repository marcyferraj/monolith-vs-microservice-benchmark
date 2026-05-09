"""
TEST 3: CHECKOUT LATENCY (Network Overhead Comparison)
========================================================

PURPOSE:
    Isolates the /checkout endpoint to measure the cost of distributed
    coordination. This is THE most important test for showing the latency
    trade-off because the architectural difference is largest here.

WHAT THIS TESTS:
    - Trade-off dimension: LATENCY of multi-step business operations
    - Expected winner: Monolith — substantially lower latency
    - Why it matters: Quantifies the "network tax" of microservices

ARCHITECTURAL DIFFERENCE:
    MONOLITH /checkout flow (single transaction, 1 DB connection):
        SELECT user → SELECT product → UPDATE stock → INSERT order → COMMIT

    MICROSERVICES /checkout flow (3 HTTP round trips + 1 local DB write):
        order-service → HTTP → auth-service → query DB → respond
        order-service → HTTP → catalog-service → query DB → respond
        order-service → HTTP → catalog-service → update DB → respond
        order-service → INSERT order in own DB

    Each HTTP hop adds: TCP setup, JSON serialization, network latency,
    JSON deserialization. Even on localhost, this typically costs 5-20ms
    per call, so expect 15-60ms of pure overhead in the microservices flow.

HOW TO RUN — MONOLITH:
    1. IMPORTANT: Increase stock so it doesn't run out mid-test.
       Edit monolith/init.sql and change `stock` from 100 to 10000:
            INSERT INTO products (name, price, stock) VALUES
                ('The Pragmatic Programmer', 39.99, 10000), ...
    2. Start fresh:
        cd monolith
        docker compose down -v
        docker compose up --build
    3. Run test:
        python3 -m locust -f test3_checkout_latency.py --host=http://localhost:5000 --users 20 --spawn-rate 2 --run-time 2m
    4. Save CSVs.

HOW TO RUN — MICROSERVICES:
    1. Bump stock in microservices/db-init/catalog-init.sql the same way.
    2. Start fresh:
        cd microservices
        docker compose down -v
        docker compose up --build
    3. Run test:
        python3 -m locust -f test3_checkout_latency.py --host=http://localhost:5003 --users 20 --spawn-rate 2 --run-time 2m
    4. Save CSVs.

DATA TO COLLECT (THE money chart for your paper):
    From Locust:
    - Average checkout latency (ms)
    - p50 latency (ms)
    - p95 latency (ms)              ← headline number
    - p99 latency (ms)
    - Requests per second
    - Failure rate

    From docker stats during test, record peak CPU% per container.
    The microservices version distributes load across 3 service containers
    plus 3 DB containers — this is itself an interesting observation.

EXPECTED RESULTS:
    Monolith p95: probably 20-60ms
    Microservices p95: probably 80-250ms
    The ratio of these two is your "cost of microservices coordination"
    headline statistic.

RESET BETWEEN RUNS:
    YES — checkout consumes stock. Always run:
        docker compose down -v && docker compose up --build
    before each test run for a clean state.
"""
import random
from locust import HttpUser, task, constant


class CheckoutUser(HttpUser):
    # Small constant wait — we want consistent, reproducible pressure
    wait_time = constant(0.5)

    @task
    def checkout(self):
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5),
        }
        with self.client.post(
            "/checkout", json=payload, name="/checkout", catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 409:
                # Out of stock — expected behavior, not an error
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
