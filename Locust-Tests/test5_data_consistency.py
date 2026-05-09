"""
TEST 5: DATA CONSISTENCY (Race Condition / Overselling)
=========================================================

PURPOSE:
    Demonstrates the data consistency trade-off. The MONOLITH uses a single
    database transaction with row-level locking, making overselling
    impossible. The MICROSERVICES version coordinates across separate
    databases with no distributed transaction, creating a race condition
    window where overselling can occur.

WHAT THIS TESTS:
    - Trade-off dimension: DATA CONSISTENCY under concurrent writes
    - Expected winner: Monolith — perfect consistency every time
    - Why it matters: ACID transactions are a major hidden benefit of
      monoliths. Microservices need explicit (and often complex) patterns
      like Sagas to approximate this, and even then guarantees are weaker.

THE EXPERIMENTAL SETUP:
    1. Set product 1's stock to a small number (e.g. 5)
    2. Fire ~50 concurrent checkouts at product 1 simultaneously
    3. Count: successful orders, "out of stock" rejections, final stock value
    4. Verify: successful_orders + remaining_stock == initial_stock

    MONOLITH expected: 5 successes, 45 rejections, 0 stock remaining.
                      Numbers add up perfectly. Every. Single. Run.

    MICROSERVICES expected: Possibly more than 5 successes (overselling),
                           OR mismatched stock and order counts. Results
                           may even vary between runs (non-deterministic
                           is itself the data point).

PRE-TEST SETUP (do this for each architecture before running):
    Set product 1's stock to exactly 5 by editing the init.sql.
    For monolith, edit monolith/init.sql:
        INSERT INTO products (name, price, stock) VALUES
            ('The Pragmatic Programmer', 39.99, 5),    ← change to 5
            ('Clean Code', 34.99, 100), ...

    For microservices, edit microservices/db-init/catalog-init.sql the same way.

    Then bring up fresh:
        docker compose down -v && docker compose up --build

HOW TO RUN — MONOLITH:
    1. With product 1 stock = 5, start fresh containers.
    2. Run with EXACT iteration count (no time-based — we want all 50
       requests fired as fast as possible):
        python3 -m locust -f test5_data_consistency.py --host=http://localhost:5000 --users 50 --spawn-rate 50 --run-time 30s --headless
    3. The --headless flag is REQUIRED here so we get the final printed
       stats. The on_stop hook prints the success/rejection breakdown.
    4. Verify final state:
        curl http://localhost:5000/products
        curl http://localhost:5000/orders

HOW TO RUN — MICROSERVICES:
    1. With catalog stock for product 1 = 5, start fresh.
    2. Run identically:
        MICROSERVICES=1 python3 -m locust -f test5_data_consistency.py --host=http://localhost:5003 --users 50 --spawn-rate 50 --run-time 30s --headless
    3. Verify final state:
        curl http://localhost:5002/products/1
        curl http://localhost:5003/orders

WHAT TO RECORD (run AT LEAST 5 times for each architecture):
    For each run, record in a table:
    | Run | Initial Stock | Successful Orders | Final Stock | Total Orders |
    |-----|---------------|-------------------|-------------|--------------|
    | 1   | 5             | ?                 | ?           | ?            |
    | 2   | 5             | ?                 | ?           | ?            |
    | ... |               |                   |             |              |

    KEY ANALYSIS for your paper:
    1. CONSERVATION CHECK: Does (successful_orders + final_stock) == 5?
       Monolith: always yes. Microservices: may not always.
    2. OVERSELLING: Did successful_orders ever exceed 5?
       Monolith: never. Microservices: possibly.
    3. CONSISTENCY ACROSS RUNS: Are results identical run-to-run?
       Monolith: deterministic. Microservices: may vary.

    To verify final state via curl after each run:
        # Monolith
        curl http://localhost:5000/products       # check stock
        curl http://localhost:5000/orders          # count orders for product 1

        # Microservices
        curl http://localhost:5002/products/1      # check stock
        curl http://localhost:5003/orders          # count orders for product 1

NOTE ON FOCUSING ON PRODUCT 1:
    This test ONLY targets product_id=1. We want all 50 concurrent requests
    to compete for the same product's inventory — that's where the race
    condition exposes itself. If users are spread across 5 products, each
    only sees ~10 concurrent requests and the race window is harder to hit.

RESET BETWEEN EACH RUN (mandatory):
    docker compose down -v && docker compose up --build
    Otherwise stock will stay at 0 from the previous run.
"""
import random
from locust import HttpUser, task, constant, events

# Per-process counters (each Locust user has its own, summed at end)
_success_count = 0
_out_of_stock_count = 0
_other_failure_count = 0


class ConsistencyTestUser(HttpUser):
    # No wait at all — fire requests as fast as possible to maximize
    # the chance of triggering race conditions in the microservices version
    wait_time = constant(0)

    @task
    def checkout_product_one(self):
        global _success_count, _out_of_stock_count, _other_failure_count

        # ALL traffic targets product 1 to maximize contention
        payload = {
            "user_id": random.randint(1, 5),
            "product_id": 1,
        }
        with self.client.post(
            "/checkout", json=payload, name="/checkout", catch_response=True
        ) as response:
            if response.status_code == 200:
                _success_count += 1
                response.success()
            elif response.status_code == 409:
                _out_of_stock_count += 1
                response.success()  # Expected business outcome
            else:
                _other_failure_count += 1
                response.failure(f"Status {response.status_code}")

    def on_stop(self):
        # Each user prints when stopping; sum across all users in your head
        # (Locust runs users in the same process so the globals accumulate)
        pass


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print the final breakdown when the test ends."""
    total = _success_count + _out_of_stock_count + _other_failure_count
    print("\n" + "=" * 60)
    print("DATA CONSISTENCY TEST RESULTS")
    print("=" * 60)
    print(f"Total requests sent:         {total}")
    print(f"Successful orders (200):     {_success_count}")
    print(f"Out-of-stock rejections (409): {_out_of_stock_count}")
    print(f"Other failures:              {_other_failure_count}")
    print("=" * 60)
    print("\nNEXT STEPS:")
    print("1. Check final stock:")
    print("   Monolith:      curl http://localhost:5000/products")
    print("   Microservices: curl http://localhost:5002/products/1")
    print("2. Verify conservation: successful_orders + final_stock == initial_stock")
    print("3. If they don't match, you've demonstrated a consistency bug!")
    print("=" * 60)
