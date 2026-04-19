"""
CHECKOUT-FOCUSED LOAD TEST
===========================
Hammers the /checkout endpoint exclusively to isolate its latency.
This is where monolith vs. microservices difference is most visible:

    Monolith checkout:      1 DB connection, 3 queries, 1 transaction
    Microservices checkout: 3 HTTP round trips + 1 DB write (order-service)

The network overhead in the microservices version should show up clearly
in the p95/p99 latency numbers even at low concurrency.

HOW TO RUN:
    Against monolith:
        locust -f locust_checkout_test.py --host=http://localhost:5000

    Against microservices order-service:
        locust -f locust_checkout_test.py --host=http://localhost:5003

SUGGESTED SETTINGS:
    Number of users: 20
    Spawn rate: 2
    Run time: 2 minutes

IMPORTANT — RESET DATABASE BETWEEN RUNS:
    Stock gets consumed during this test. Reset with:
        docker compose down -v
        docker compose up --build
    The -v flag wipes volumes so init.sql seeds fresh data.

WHAT TO RECORD:
    - Average latency (ms)
    - p95 latency (ms)   ← most important number
    - Requests/sec
    - Failure rate (once stock runs out, checkouts will fail — that's expected)
"""

import random
from locust import HttpUser, task, between, constant


class CheckoutUser(HttpUser):
    # Shorter wait time to generate more checkout pressure
    wait_time = constant(0.5)

    @task
    def checkout(self):
        """
        Single task — all virtual users only do checkout.
        Randomly picks from users 1-5 and products 1-5.
        """
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5)
        }
        with self.client.post(
            "/checkout",
            json=payload,
            name="/checkout",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 400:
                # Out of stock — expected once inventory runs dry
                # Mark as success so it doesn't skew your failure rate
                response.success()
            else:
                # Actual failures (500s, timeouts) — these are the ones to watch
                response.failure(f"Unexpected status: {response.status_code}")
