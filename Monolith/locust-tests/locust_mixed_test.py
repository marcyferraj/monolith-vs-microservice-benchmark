"""
MIXED WORKLOAD TEST
===================
Simulates realistic traffic hitting all endpoints in weighted proportions:
    70% product browsing
    20% auth lookups
    10% checkouts

This is your most important comparison because checkout triggers cross-service
HTTP calls in the microservices version but not in the monolith.

HOW TO RUN:
    Against monolith:
        locust -f locust_mixed_test.py --host=http://localhost:5000 --tags monolith

    Against microservices:
        locust -f locust_mixed_test.py --host=http://localhost:5003 --tags microservices

NOTE: For microservices, the MonolithMixedUser class won't work directly because
auth/catalog/orders are on different ports. Use MicroservicesMixedUser instead.
See the class docstrings below.

SUGGESTED SETTINGS:
    Number of users: 30
    Spawn rate: 3
    Run time: 3 minutes

WHAT TO RECORD:
    - Per-endpoint RPS and latency (Locust shows these separately in the table)
    - Overall failure rate
    - How /checkout latency compares between architectures — this is your key data point
"""

import random
from locust import HttpUser, task, between


# =============================================================================
# MONOLITH VERSION — all endpoints on the same host (port 5000)
# Run with: locust -f locust_mixed_test.py --host=http://localhost:5000
# =============================================================================
class MonolithMixedUser(HttpUser):
    wait_time = between(1, 2)

    # This user will only run when host is the monolith
    # To avoid running both classes at once, comment out the other class
    # or use Locust's --tags flag

    @task(7)
    def browse_products(self):
        """70% of traffic — product listing"""
        self.client.get("/products", name="/products")

    @task(2)
    def auth_lookup(self):
        """20% of traffic — user authentication check"""
        user_id = random.randint(1, 5)
        self.client.get(f"/users/{user_id}", name="/users/[id]")

    @task(1)
    def checkout(self):
        """
        10% of traffic — the critical endpoint.
        In the monolith: 1 function, 1 DB, no network hops.
        Watch its latency here vs. the microservices version.
        """
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5)
        }
        self.client.post(
            "/checkout",
            json=payload,
            name="/checkout"
        )


# =============================================================================
# MICROSERVICES VERSION — each service on its own port
# This class makes calls to all three ports from within one user.
# Run with: locust -f locust_mixed_test.py --host=http://localhost:5003
# (host is ignored for auth/catalog calls — those ports are hardcoded below)
# =============================================================================
class MicroservicesMixedUser(HttpUser):
    wait_time = between(1, 2)

    # Ports for each service — adjust if yours differ
    AUTH_URL = "http://localhost:5001"
    CATALOG_URL = "http://localhost:5002"
    # ORDER_URL is the --host argument (http://localhost:5003)

    @task(7)
    def browse_products(self):
        """70% — hits catalog-service directly"""
        # Note: self.client uses the --host arg, so we use a raw request
        # for cross-service calls
        import requests
        requests.get(f"{self.CATALOG_URL}/products")

    @task(2)
    def auth_lookup(self):
        """20% — hits auth-service directly"""
        import requests
        user_id = random.randint(1, 5)
        requests.get(f"{self.AUTH_URL}/users/{user_id}")

    @task(1)
    def checkout(self):
        """
        10% — hits order-service /checkout.
        This single request internally triggers 3 HTTP calls:
            order-service → auth-service (verify user)
            order-service → catalog-service (get product)
            order-service → catalog-service (decrement stock)
        Compare this latency to the monolith checkout above.
        """
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5)
        }
        self.client.post(
            "/checkout",
            json=payload,
            name="/checkout"
        )
