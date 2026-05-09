"""
TEST 6: HORIZONTAL SCALING (Targeted vs. Whole-System Scaling)
================================================================

PURPOSE:
    Demonstrates the scaling trade-off. With MICROSERVICES, you can scale
    just the bottleneck service (e.g. spin up 3 catalog-service instances
    while leaving auth and orders at 1). With a MONOLITH, you must
    duplicate the entire app even if only one part is under pressure.

WHAT THIS TESTS:
    - Trade-off dimension: SCALING EFFICIENCY (resource utilization)
    - Expected winner: Microservices — can target resources where needed
    - Why it matters: Shows why companies migrate to microservices when
      different parts of their system have very different load profiles.

THE COMPARISON — 5 RUNS TOTAL:
    Run A: Monolith default            (0.5 CPU / 256M)
    Run B: Monolith vertical scaled    (1.5 CPU / 768M)
    Run C: Microservices default       (~0.5 CPU / 256M total, matches A)
    Run D: Microservices vertical      (1.5 CPU / 768M total, matches B)
    Run E: Microservices horizontal    (3x catalog-service, ~0.85 CPU total)

    The headline comparison: Run B (mono vertical) vs Run E (micro horizontal).
    Both are "scaled up" versions, but E should achieve similar throughput
    using significantly fewer resources because it adds capacity ONLY where
    the bottleneck is.

IMPORTANT — TWO TASKS BELOW:
    This file has TWO @task functions, but only ONE is enabled at a time
    (the other has @task(0) which means "never run"). Switch which one
    runs by changing the @task numbers based on which run you're doing:

    For Runs A, B, C, D: enable hammer_products, disable hammer_checkout
        @task(1) hammer_products
        @task(0) hammer_checkout

    For Run E only: enable hammer_checkout, disable hammer_products
        @task(0) hammer_products
        @task(1) hammer_checkout

    Why? When catalog-service is scaled to 3 instances, you must REMOVE
    its host port mapping (5002) from docker-compose.yml because Docker
    can't bind 3 containers to the same port. After removing it, Locust
    can no longer hit /products directly. Instead, hit /checkout on the
    order-service (port 5003), which calls catalog-service internally
    via Docker DNS — that DOES round-robin across the 3 instances.

PRE-TEST SETUP — RUN A (Monolith baseline):
    1. monolith/docker-compose.yml resource limits:
        cpus: '0.5'
        memory: 256M
    2. cd monolith && docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN B (Monolith vertically scaled):
    1. Edit monolith/docker-compose.yml, change app service limits to:
        cpus: '1.5'
        memory: 768M
    2. docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN C (Microservices default):
    1. microservices/docker-compose.yml — each app service:
        cpus: '0.17'
        memory: 86M
    2. Make sure catalog-service has its `ports: - "5002:5002"` mapping ENABLED.
    3. cd microservices && docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN D (Microservices vertically scaled):
    1. Edit microservices/docker-compose.yml — each app service:
        cpus: '0.5'
        memory: 256M
    2. Make sure catalog-service has its `ports: - "5002:5002"` mapping ENABLED.
    3. docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN E (Microservices horizontal):
    1. Restore each app service to small resources:
        cpus: '0.17'
        memory: 86M
    2. CRITICAL: REMOVE or COMMENT OUT the catalog-service port mapping:
            catalog-service:
              build: ./catalog-service
              # ports:                       <-- comment out
              #   - "5002:5002"              <-- comment out
              depends_on:
                - catalog_db
              ...
       Otherwise Docker fails with "port 5002 already allocated".
    3. cd microservices && docker compose down -v
    4. docker compose up --build --scale catalog-service=3
    5. Verify with `docker ps` — you should see 3 catalog-service containers.
    6. SWITCH THE @task NUMBERS in this file (see "IMPORTANT" note above).

HOW TO RUN — Runs A, B, C, D:
    python3 -m locust -f test6_horizontal_scaling.py --host=<HOST> --users 100 --spawn-rate 10 --run-time 2m

    Where <HOST> is:
        Run A: http://localhost:5000  (monolith)
        Run B: http://localhost:5000  (monolith, scaled)
        Run C: http://localhost:5002  (microservices catalog directly)
        Run D: http://localhost:5002  (microservices catalog, scaled vertically)

HOW TO RUN — Run E (different host AND different task):
    1. Switch @task numbers (hammer_products → 0, hammer_checkout → 1)
    2. Run:
        python3 -m locust -f test6_horizontal_scaling.py --host=http://localhost:5003 --users 100 --spawn-rate 10 --run-time 2m

DATA TO COLLECT (for each run):
    - Total Requests Per Second (Locust UI Statistics tab, Aggregated row)
    - p95 latency (Locust UI Statistics tab, "95%" column)
    - Total CPU % across ALL containers (sum from `docker stats` snapshots)
    - Total memory limits (sum from your docker-compose limits)

    To capture CPU during a test, in a separate terminal run a few times:
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    Take the highest values you see during the test and sum CPU across containers.

THE ANALYSIS YOUR DATA SHOULD SUPPORT:
    Calculate "RPS per CPU %" for each run — this is your efficiency metric.

    Expected pattern:
        Run A: baseline RPS at baseline resources
        Run B: higher RPS but with diminishing returns per CPU spent
        Run C: similar to A (matched resources)
        Run D: similar to B (matched resources, but spread across 3 services
               that don't all need it = wasted)
        Run E: HIGH RPS using FEWER resources = best RPS/CPU ratio

    The headline finding: Run E should achieve close to Run B's RPS while
    using roughly half the total CPU, because it only added capacity where
    the bottleneck actually was.

NOTE ON COMPARING RUN E TO OTHERS:
    Runs A-D all hit a simple read endpoint (/products). Run E hits
    /checkout because that's the only way to exercise the load-balanced
    catalog cluster without Nginx. This means Run E's absolute RPS
    numbers will be LOWER than A-D (checkout is more work per request),
    so don't compare raw RPS across these endpoints. Instead, compare:
    - RPS per CPU% within Run E vs other runs
    - Run E's RPS relative to its OWN resource usage
    - The fact that adding 2 extra catalog containers (only ~0.34 extra
      CPU) significantly boosted checkout throughput vs default microservices

RESET BETWEEN RUNS:
    docker compose down -v && docker compose up --build [with appropriate flags]
"""
import random
from locust import HttpUser, task, constant

class ScalingTestUser(HttpUser):
    wait_time = constant(0)

    @task(0)  # DISABLED for Run E
    def hammer_products(self):
        """Direct read against /products. Use for Runs A-D."""
        self.client.get("/products", name="/products")

    @task(1)  # ENABLED for Run E
    def hammer_checkout(self):
        """Checkout via order-service. Use for Run E (horizontal scaling)."""
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": random.randint(1, 5),
        }
        with self.client.post(
            "/checkout", json=payload, name="/checkout", catch_response=True
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
