"""
TEST 2: MIXED WORKLOAD (Realistic E-Commerce Traffic)
=======================================================

PURPOSE:
    Simulates real-world e-commerce traffic patterns: lots of browsing, some
    auth checks, occasional purchases. This is the test that most closely
    represents what each architecture would face in production.

WHAT THIS TESTS:
    - Trade-off dimension: OVERALL THROUGHPUT under realistic mixed load
    - Expected winner: Depends on load level. Monolith may win at low load,
      microservices may match or exceed at high load if bottleneck is isolated.
    - Why it matters: Real systems don't see uniform traffic — this captures
      how each architecture handles a realistic ratio of read vs. write ops.

TRAFFIC DISTRIBUTION (matches typical e-commerce ratios):
    @task(7) browse_products  — 70% of traffic
    @task(2) check_auth       — 20% of traffic
    @task(1) checkout         — 10% of traffic

NOTE ON MICROSERVICES PORTS:
    Monolith runs everything on one port (5000).
    Microservices run on separate ports — this test handles both via the
    HOST environment variable. For monolith, use --host=http://localhost:5000.
    For microservices, this test hits each service's port individually
    by overriding the URL per task.

HOW TO RUN — MONOLITH:
    1. Start monolith:
        cd monolith
        docker compose up --build
    2. Run test:
        python3 -m locust -f test2_mixed_workload.py --host=http://localhost:5000 --users 30 --spawn-rate 3 --run-time 3m
    3. Open http://localhost:8089, click "Start swarming"
    4. Save CSVs from the Download Data tab.

HOW TO RUN — MICROSERVICES:
    1. Start microservices:
        cd microservices
        docker compose up --build
    2. Run test (uses MICROSERVICES=1 to switch URL routing):
        export MICROSERVICES=1
        python3 -m locust -f test2_mixed_workload.py --host=http://localhost:5002 --users 30 --spawn-rate 3 --run-time 3m

       Or as a one-liner:
        MICROSERVICES=1 python3 -m locust -f test2_mixed_workload.py --host=http://localhost:5002 --users 30 --spawn-rate 3 --run-time 3m
    3. Save CSVs from the Download Data tab.

DATA TO COLLECT:
    For each endpoint type (/products, /auth, /checkout), record from Locust:
    - Average response time (ms)
    - p95 response time (ms)        ← key metric per endpoint
    - p99 response time (ms)
    - Requests per second
    - Failure rate

    Capture docker stats during test for resource utilization comparison.

    KEY OBSERVATION FOR YOUR PAPER:
    Compare /checkout latency between architectures — this should show the
    biggest gap because microservices checkout makes 3 HTTP calls.

RESET BETWEEN RUNS:
    YES — checkout consumes stock. Reset before each run:
        docker compose down -v && docker compose up --build
"""
import os
import random
from locust import HttpUser, task, between

# Switch URL routing based on whether we're testing microservices
USE_MICROSERVICES = os.getenv("MICROSERVICES", "0") == "1"

# Microservice base URLs (override --host for individual tasks)
AUTH_URL = "http://localhost:5001"
CATALOG_URL = "http://localhost:5002"
ORDER_URL = "http://localhost:5003"


class MixedWorkloadUser(HttpUser):
    # Realistic think time — users don't fire requests instantly
    wait_time = between(0.5, 1.5)

    @task(7)
    def browse_products(self):
        url = f"{CATALOG_URL}/products" if USE_MICROSERVICES else "/products"
        self.client.get(url, name="/products")

    @task(2)
    def check_auth(self):
        url = f"{AUTH_URL}/auth" if USE_MICROSERVICES else "/auth"
        self.client.get(url, name="/auth")

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
            # 200 = order placed, 409 = out of stock (expected business outcome)
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
