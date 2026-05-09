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

THE COMPARISON:
    This test fires read-heavy traffic at the catalog endpoint (the assumed
    bottleneck). You'll run it FOUR times and compare RPS and p95:

    Run A: Monolith, single instance        (baseline)
    Run B: Monolith, vertical scaled        (more CPU/memory)
    Run C: Microservices, default           (1 of each service)
    Run D: Microservices, horizontal scaled (3x catalog-service)

    The story: doubling resources for the monolith improves performance
    less efficiently than tripling JUST the catalog service in
    microservices, because monolith resources are wasted on services that
    weren't bottlenecked.

PRE-TEST SETUP — RUN A (Monolith baseline):
    1. Use the default monolith/docker-compose.yml resource limits:
        cpus: '0.5'
        memory: 256M
    2. Start: cd monolith && docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN B (Monolith vertically scaled):
    1. Edit monolith/docker-compose.yml, change app service limits to:
        cpus: '1.5'
        memory: 768M
    2. Start: docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN C (Microservices default):
    1. Use default microservices/docker-compose.yml (1 of each service).
    2. Start: cd microservices && docker compose down -v && docker compose up --build

PRE-TEST SETUP — RUN D (Microservices horizontally scaled):
    1. Use Docker Compose's --scale flag to spin up 3 catalog instances:
        cd microservices
        docker compose down -v
        docker compose up --build --scale catalog-service=3
    2. NOTE: With multiple catalog instances, you need a load balancer in
       front, OR you target each instance directly. For simplicity in this
       test, Docker's internal DNS will round-robin between the 3
       instances when other services call "catalog-service" by name.
       But your Locust test (running outside Docker) hits localhost:5002,
       which maps to only ONE container. To test the full horizontal
       scaling benefit, you need an Nginx load balancer.

    QUICK ALTERNATIVE without Nginx: Use the order-service /checkout
    endpoint instead of /products directly, since order-service uses
    the internal Docker DNS that DOES load-balance across the 3
    catalog instances. Then this test becomes essentially the checkout
    latency test under horizontal scaling.

HOW TO RUN (each of the 4 configurations):
    python3 -m locust -f test6_horizontal_scaling.py --host=<HOST> --users 100 --spawn-rate 10 --run-time 2m
    python3 -m locust -f test6_horizontal_scalingTestE.py --host=http://localhost:5003 --users 100 --spawn-rate 10 --run-time 2m

    Where <HOST> is:
        Run A: http://localhost:5000 (monolith)
        Run B: http://localhost:5000 (monolith, scaled up)
        Run C: http://localhost:5002 (microservices catalog directly)
        Run D: http://localhost:5002 (microservices catalog, scaled to 3)

DATA TO COLLECT (for each of the 4 runs):
    - Total Requests Per Second
    - p95 latency
    - Total CPU usage across all containers (sum from docker stats)
    - Total memory usage across all containers

THE ANALYSIS YOUR DATA WILL SUPPORT:
    Calculate "RPS per CPU%" for each run — this shows efficiency.

    Example expected result:
        Run A: 200 RPS at 50% CPU  = 4 RPS per 1% CPU
        Run B: 350 RPS at 150% CPU = 2.3 RPS per 1% CPU (diminishing returns)
        Run C: 220 RPS at 50% CPU (across all containers) = 4.4 RPS per 1%
        Run D: 580 RPS at 150% CPU (across all containers) = 3.9 RPS per 1%

    Microservices horizontal scaling typically maintains better efficiency
    because you're only adding resources where the bottleneck is.

RESET BETWEEN RUNS:
    docker compose down -v && docker compose up --build [with appropriate flags]
"""
from locust import HttpUser, task, constant


class ScalingTestUser(HttpUser):
    # Aggressive — we want to actually saturate the system
    wait_time = constant(0)

    @task
    def hammer_catalog(self):
        self.client.get("/products", name="/products")
