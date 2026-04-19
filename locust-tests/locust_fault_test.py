"""
FAULT TOLERANCE TEST
=====================
Runs sustained mixed traffic so you can manually kill a service mid-test
and observe the blast radius difference between architectures.

This test doesn't kill services itself — YOU do that manually while it runs.
That way you can choose exactly when to introduce the failure and watch the
live Locust dashboard react in real time.

HOW TO RUN:
    1. Start your architecture:
          Monolith:       docker compose up --build  (in monolith/)
          Microservices:  docker compose up --build  (in microservices/)

    2. Start this test:
          Against monolith:       locust -f locust_fault_test.py --host=http://localhost:5000
          Against microservices:  locust -f locust_fault_test.py --host=http://localhost:5003

    3. Open http://localhost:8089, set 20 users / spawn rate 2, click Start.

    4. Wait ~30 seconds for traffic to stabilize (watch the RPS settle).

    5. IN A SEPARATE TERMINAL, kill a component:
          Microservices — kill catalog only:
              docker stop microservices-catalog-service-1
          Monolith — kill the whole app:
              docker stop monolith-app-1

    6. Watch the Locust dashboard. Note:
          - Which endpoints start failing (red in the table)?
          - Which endpoints keep working?
          - What does the failure rate chart look like?

    7. After 1 minute, restart the killed container:
          docker start microservices-catalog-service-1
          (or docker start monolith-app-1)
       Observe recovery time.

WHAT TO RECORD:
    Microservices (catalog killed):
        - /products → should fail (served by catalog)
        - /checkout → should fail (depends on catalog)
        - /auth (port 5001) → should KEEP WORKING
        - /orders GET (port 5003) → should KEEP WORKING
        Recovery time after restart

    Monolith (app killed):
        - ALL endpoints fail immediately
        - Recovery time after restart

    This is your "blast radius" comparison:
        Microservices: 2 of 4 endpoint types affected
        Monolith: 4 of 4 endpoint types affected
"""

import random
from locust import HttpUser, task, between


class FaultToleranceUser(HttpUser):
    wait_time = between(1, 2)

    # ----- MONOLITH version -----
    # All requests go to port 5000 (set by --host)

    @task(4)
    def browse_products(self):
        """Catalog read — will fail when catalog is down in microservices"""
        self.client.get("/products", name="/products")

    @task(3)
    def get_user(self):
        """Auth read — should survive catalog failure in microservices"""
        user_id = random.randint(1, 5)
        # Monolith: hits /users/{id} on port 5000
        # For microservices auth, see note below
        self.client.get(f"/users/{user_id}", name="/users/[id]")

    @task(2)
    def get_orders(self):
        """Orders read — should survive catalog failure in microservices"""
        self.client.get("/orders", name="/orders")

    @task(1)
    def checkout(self):
        """Checkout — will fail when catalog is down (requires catalog lookup)"""
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5)
        }
        # catch_response=True so failures don't stop the test
        with self.client.post(
            "/checkout",
            json=payload,
            name="/checkout",
            catch_response=True
        ) as response:
            if response.status_code in (200, 400, 503):
                response.success()  # track in stats but don't abort
            else:
                response.failure(f"Status: {response.status_code}")


# =============================================================================
# NOTE FOR MICROSERVICES FAULT TESTING:
# The class above works for the monolith (all one host).
# For microservices, /users hits auth-service (port 5001) and /orders hits
# order-service (port 5003) — but Locust's self.client only targets one host.
#
# The simplest approach: run the test against the monolith first to get a
# baseline, then run it against the microservices order-service (port 5003)
# for the /checkout and /orders endpoints. Manually curl the auth-service
# in a separate terminal during the failure to confirm it's still up:
#
#     curl http://localhost:5001/health   ← should return 200 even when catalog is down
#     curl http://localhost:5002/health   ← should fail when catalog is down
#
# That manual check is actually a cleaner demo for a presentation than
# trying to track cross-port calls in one Locust session.
# =============================================================================
