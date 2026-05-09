"""
TEST 1: READ-HEAVY LOAD TEST (Baseline Throughput)
====================================================

PURPOSE:
    Measures baseline performance of read-only endpoints under sustained load.
    This establishes how each architecture handles simple, non-mutating traffic.
    Read endpoints touch only one service/module so the architectural difference
    is minimal here — expect similar performance with monolith slightly ahead.

WHAT THIS TESTS:
    - Trade-off dimension: THROUGHPUT under light read load
    - Expected winner: Monolith (slightly) — no network overhead between layers
    - Why it matters: Shows that microservices overhead is negligible for
      simple reads, supporting "start monolithic" advice for small systems.

ENDPOINTS HIT:
    GET /products  (catalog data)

HOW TO RUN — MONOLITH:
    1. Start the monolith:
        cd monolith
        docker compose up --build
    2. In a new terminal:
        python3 -m locust -f test1_read_heavy.py --host=http://localhost:5000 --users 50 --spawn-rate 5 --run-time 2m
    3. Open http://localhost:8089, click "Start swarming"
    4. When test finishes, click "Download Data" tab and save:
        - requests_monolith_read.csv
        - failures_monolith_read.csv

HOW TO RUN — MICROSERVICES:
    1. Stop monolith (docker compose down -v), then start microservices:
        cd microservices
        docker compose up --build
    2. In a new terminal:
        python3 -m locust -f test1_read_heavy.py --host=http://localhost:5002 --users 50 --spawn-rate 5 --run-time 2m
    3. Save CSVs as requests_microservices_read.csv and failures_microservices_read.csv

DATA TO COLLECT (record both architectures):
    From the Locust UI Statistics tab:
    - Average response time (ms)
    - Median (p50) response time (ms)
    - p95 response time (ms)        ← key metric
    - p99 response time (ms)
    - Requests per second (RPS)
    - Failure count / failure rate

    From a second terminal during the test, run:
        docker stats --no-stream
    Capture peak CPU% and memory usage per container.

RESET BETWEEN RUNS:
    Not strictly necessary — this test is read-only and doesn't mutate state.
    But to keep runs comparable, restart containers fresh:
        docker compose down -v && docker compose up --build
"""
from locust import HttpUser, task, constant


class ReadHeavyUser(HttpUser):
    # No wait time — we want sustained throughput pressure
    wait_time = constant(0)

    @task
    def list_products(self):
        self.client.get("/products", name="/products")
