"""
READ-HEAVY LOAD TEST
====================
Tests basic throughput and latency on read endpoints.
This is your baseline comparison — simple GET requests with no writes.

HOW TO RUN:
    Against monolith:
        locust -f locust_read_test.py --host=http://localhost:5000

    Against microservices catalog:
        locust -f locust_read_test.py --host=http://localhost:5002

Then open http://localhost:8089 in your browser to configure and start the test.

SUGGESTED SETTINGS in the Locust UI:
    Number of users: 50
    Spawn rate: 5 (adds 5 users per second until target is reached)
    Run time: 3 minutes

WHAT TO RECORD:
    - Requests/sec (RPS) — shown in the UI and in the downloaded CSV
    - p50, p95 latency (ms)
    - Failure rate (%)
    - Peak CPU/memory from: docker stats (run in a separate terminal while test runs)
"""

from locust import HttpUser, task, between


class ReadHeavyUser(HttpUser):
    # Each simulated user waits 1-2 seconds between requests (realistic pacing)
    wait_time = between(1, 2)

    @task(5)
    def browse_products(self):
        """
        Weight 5 — 5x more likely than get_single_product.
        Simulates a user hitting the product listing page.
        Works on both monolith (port 5000) and catalog-service (port 5002).
        """
        self.client.get("/products", name="/products")

    @task(3)
    def get_single_product(self):
        """
        Weight 3 — fetches a specific product by ID.
        Rotates through products 1-5 (your seeded data).
        """
        import random
        product_id = random.randint(1, 5)
        self.client.get(f"/products/{product_id}", name="/products/[id]")

    @task(2)
    def health_check(self):
        """
        Weight 2 — hits the health endpoint.
        Useful baseline: this endpoint does NO database work,
        so its latency shows your pure network/framework overhead.
        Compare this to /products latency to isolate DB cost.
        """
        self.client.get("/health", name="/health")
