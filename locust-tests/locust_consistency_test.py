"""
DATA CONSISTENCY TEST — RACE CONDITION DEMO
============================================
Fires many concurrent checkouts at a low-stock product to expose the
difference in how each architecture handles simultaneous writes.

    Monolith:        Uses SELECT ... FOR UPDATE (row lock).
                     Exactly N orders succeed where N = initial stock.
                     Database enforces this — no overselling possible.

    Microservices:   Stock check (catalog-service) and order insert (order-service)
                     are TWO separate operations with no distributed lock.
                     Race window: multiple requests can pass the stock check
                     before any of them decrement it.
                     Result: you may see MORE orders than stock allows.

SETUP — BEFORE RUNNING:
    1. Reset your database so you start fresh:
          docker compose down -v && docker compose up --build

    2. Set one product to very low stock so the race is easy to trigger.
       Connect to your DB and run:

       Monolith:
          docker exec -it monolith-db-1 psql -U user -d bookstore
          UPDATE products SET stock = 5 WHERE product_id = 1;

       Microservices catalog DB:
          docker exec -it microservices-catalog-db-1 psql -U user -d catalogdb
          UPDATE products SET stock = 5 WHERE product_id = 1;

    3. Run this test with HIGH concurrency and NO wait time:
          Against monolith:
              locust -f locust_consistency_test.py --host=http://localhost:5000 \
                     --users 30 --spawn-rate 30 --run-time 30s --headless

          Against microservices:
              locust -f locust_consistency_test.py --host=http://localhost:5003 \
                     --users 30 --spawn-rate 30 --run-time 30s --headless

       --headless runs without the browser UI and prints summary to terminal.
       --spawn-rate 30 starts all 30 users at once (maximizes the race window).

    4. After the test, count the results:

       Monolith — check orders and stock:
          docker exec -it monolith-db-1 psql -U user -d bookstore \
              -c "SELECT COUNT(*) FROM orders WHERE product_id = 1;"
          docker exec -it monolith-db-1 psql -U user -d bookstore \
              -c "SELECT stock FROM products WHERE product_id = 1;"

       Microservices — check orders (order-service DB) and stock (catalog DB):
          docker exec -it microservices-order-db-1 psql -U user -d ordersdb \
              -c "SELECT COUNT(*) FROM orders WHERE product_id = 1;"
          docker exec -it microservices-catalog-db-1 psql -U user -d catalogdb \
              -c "SELECT stock FROM products WHERE product_id = 1;"

WHAT TO RECORD:
    |                    | Monolith | Microservices |
    |--------------------|----------|---------------|
    | Initial stock      |    5     |      5        |
    | Successful orders  |    ?     |      ?        |
    | Final stock count  |    ?     |      ?        |
    | Oversold?          |   No     |    Maybe      |

    If microservices shows more successful orders than initial stock,
    that's your race condition data point. Run it 3x and average the results
    since races are non-deterministic.
"""

from locust import HttpUser, task, constant


class ConsistencyUser(HttpUser):
    # NO wait time — we want maximum concurrency to trigger the race
    wait_time = constant(0)

    # All requests target product_id=1 (the one you set to low stock)
    # All use user_id=1 for simplicity — the key variable is product stock
    TARGET_PRODUCT_ID = 1
    TARGET_USER_ID = 1

    @task
    def checkout_low_stock_item(self):
        """
        Every virtual user hammers the same low-stock product.
        The goal is to have many requests hit the stock check simultaneously
        before any of them complete the write — that's the race window.
        """
        payload = {
            "user_id": self.TARGET_USER_ID,
            "product_id": self.TARGET_PRODUCT_ID
        }
        with self.client.post(
            "/checkout",
            json=payload,
            name="/checkout [consistency test]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                # Successful order — count these
                response.success()
            elif response.status_code == 400:
                # Out of stock response — expected and fine
                # Mark success so Locust doesn't flag these as errors
                response.success()
            else:
                response.failure(f"Unexpected: {response.status_code} - {response.text}")
