# Locust Testing Suite — Monolith vs. Microservices

## Installation

```powershell
pip install locust
locust --version   # verify
```

---

## Files Overview

| File | What it tests | Key metric |
|------|--------------|------------|
| `locust_read_test.py` | Basic read throughput | RPS, p95 latency |
| `locust_mixed_test.py` | Realistic mixed traffic | Per-endpoint latency |
| `locust_checkout_test.py` | Checkout under load | p95 latency (shows network overhead) |
| `locust_fault_test.py` | Failure + blast radius | Which endpoints survive |
| `locust_consistency_test.py` | Race condition / overselling | Orders vs. stock count |

---

## How to Run Each Test

### 1. Read-Heavy Test
```powershell
# Monolith
locust -f locust_read_test.py --host=http://localhost:5000

# Microservices (catalog service)
locust -f locust_read_test.py --host=http://localhost:5002
```
Open http://localhost:8089 → set **50 users, spawn rate 5, run 3 min**

---

### 2. Mixed Workload Test
```powershell
# Monolith — comment out MicroservicesMixedUser class first
locust -f locust_mixed_test.py --host=http://localhost:5000

# Microservices — comment out MonolithMixedUser class first
locust -f locust_mixed_test.py --host=http://localhost:5003
```
Open http://localhost:8089 → set **30 users, spawn rate 3, run 3 min**

---

### 3. Checkout-Focused Test
```powershell
# Monolith
locust -f locust_checkout_test.py --host=http://localhost:5000

# Microservices
locust -f locust_checkout_test.py --host=http://localhost:5003
```
Open http://localhost:8089 → set **20 users, spawn rate 2, run 2 min**

> ⚠️ Reset DB between runs: `docker compose down -v && docker compose up --build`

---

### 4. Fault Tolerance Test (manual + Locust)
```powershell
# Start test
locust -f locust_fault_test.py --host=http://localhost:5000   # or 5003

# After traffic stabilizes (~30s), in a NEW terminal:

# Kill catalog only (microservices):
docker stop microservices-catalog-service-1

# Or kill entire monolith:
docker stop monolith-app-1

# After 1 min, restart:
docker start microservices-catalog-service-1
```
Watch the Locust dashboard live for failure spikes and recovery.

---

### 5. Data Consistency Test (headless — no browser needed)
```powershell
# Step 1: Set stock to 5
docker exec -it monolith-db-1 psql -U user -d bookstore -c "UPDATE products SET stock = 5 WHERE product_id = 1;"

# Step 2: Run headless (no browser)
locust -f locust_consistency_test.py --host=http://localhost:5000 --users 30 --spawn-rate 30 --run-time 30s --headless

# Step 3: Count results
docker exec -it monolith-db-1 psql -U user -d bookstore -c "SELECT COUNT(*) FROM orders WHERE product_id = 1;"
docker exec -it monolith-db-1 psql -U user -d bookstore -c "SELECT stock FROM products WHERE product_id = 1;"
```
Repeat Steps 1-3 for microservices, swapping the host and DB container names.

---

## Saving Results

After each test, click **Download Data → Download Report** in the Locust UI.
Or capture terminal output:
```powershell
locust -f locust_read_test.py --host=http://localhost:5000 --users 50 --spawn-rate 5 --run-time 3m --headless 2>&1 | Tee-Object -FilePath monolith-read-results.txt
```

---

## Testing Matrix — Fill This In

| Test | Architecture | Users | RPS | Avg (ms) | p95 (ms) | Error % |
|------|-------------|-------|-----|----------|----------|---------|
| Read | Monolith | 50 | | | | |
| Read | Microservices | 50 | | | | |
| Mixed | Monolith | 30 | | | | |
| Mixed | Microservices | 30 | | | | |
| Checkout | Monolith | 20 | | | | |
| Checkout | Microservices | 20 | | | | |

---

## Docker Stats (run while Locust test is active)

In a separate terminal during each test:
```powershell
docker stats --no-stream
```
Record peak CPU % and MEM for each container. This is your resource utilization data.
