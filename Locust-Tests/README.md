# Test Suite — Monolith vs Microservices Project (macOS)

This folder contains 6 Locust tests that systematically measure each major
trade-off between the two architectures.

## Prerequisites

### Install Docker Desktop for Mac
Download from https://www.docker.com/products/docker-desktop/

Pick the right version for your Mac:
- **Apple Silicon (M1/M2/M3/M4)**: download the "Mac with Apple chip" build
- **Intel Mac**: download the "Mac with Intel chip" build

After installing, launch Docker Desktop from Applications. You'll see the
whale icon in your menu bar at the top of the screen — when it's steady
(not animating), Docker is ready.

Verify in Terminal:
```bash
docker --version
docker compose version
```

### Install Locust

The cleanest approach on macOS is to use a virtual environment so you
don't pollute the system Python:

```bash
python3 -m venv venv
source venv/bin/activate
pip install locust
```

Verify:
```bash
python3 -m locust --version
```

**Important:** every time you open a new Terminal tab to run a test, you'll
need to re-activate the venv with `source venv/bin/activate` from the project
folder. Your prompt will show `(venv)` when it's active.

Alternatively, if you have Homebrew, you can install Locust globally:
```bash
brew install locust
```

## Test Suite Overview

| Test | What it Measures | Expected Winner | Time |
|------|------------------|-----------------|------|
| test1_read_heavy | Baseline read throughput | Roughly equal | 2m × 2 |
| test2_mixed_workload | Realistic e-commerce traffic | Mixed | 3m × 2 |
| test3_checkout_latency | Multi-step operation latency | Monolith | 2m × 2 |
| test4_fault_tolerance | Graceful degradation | Microservices | 3m × 2 |
| test5_data_consistency | Race condition / overselling | Monolith | 30s × 10 (5 runs each) |
| test6_horizontal_scaling | Targeted scaling efficiency | Microservices | 2m × 4 |

**Total active testing time: ~1.5 hours of test runs, plus setup/reset between each.**

## Recommended Execution Order

Run all 6 tests in order against ONE architecture, then repeat for the other.
This minimizes context switching between docker compose configurations.

### Day 1: Monolith
1. `cd monolith && docker compose up --build`
2. Run test1, test2, test3 (resetting between each: `docker compose down -v && docker compose up --build`)
3. For test4: start test, manually `docker stop monolith-app-1` mid-test, then `docker start monolith-app-1`
4. For test5: edit init.sql to set product 1 stock to 5, run 5 times with full reset between each
5. For test6: run twice (Run A baseline, then Run B with more resources)

### Day 2: Microservices
1. `cd microservices && docker compose up --build`
2. Repeat tests 1-5 with `MICROSERVICES=1` prefixed for tests 2 and 4 (e.g. `MICROSERVICES=1 python3 -m locust ...`)
3. For test6: run twice (Run C default, Run D with `--scale catalog-service=3`)

## Setting the MICROSERVICES Environment Variable

Tests 2 and 4 use this to switch URL routing. On macOS, set it inline with
the locust command:

```bash
MICROSERVICES=1 python3 -m locust -f test2_mixed_workload.py --host=http://localhost:5002 --users 30 --spawn-rate 3 --run-time 3m
```

Or export it for the whole terminal session:
```bash
export MICROSERVICES=1
python3 -m locust -f test2_mixed_workload.py ...
```

## Data Collection Template

Create a spreadsheet (Numbers, Excel, or Google Sheets) with one tab per test.
Suggested column structure:

### Tab: Test 1 — Read Heavy
| Architecture | Avg (ms) | p50 | p95 | p99 | RPS | Failures | Peak CPU% | Peak Mem |
|---|---|---|---|---|---|---|---|---|
| Monolith | | | | | | | | |
| Microservices | | | | | | | | |

### Tab: Test 3 — Checkout Latency (THE KEY CHART)
Same columns as Test 1 — this is your headline comparison.

### Tab: Test 4 — Fault Tolerance
| Architecture | Endpoint | Failure Rate (Before) | Failure Rate (During) | Failure Rate (After) | Recovery Time (s) |
|---|---|---|---|---|---|
| Monolith | /products | | | | |
| Monolith | /auth | | | | |
| Monolith | /orders | | | | |
| Monolith | /checkout | | | | |
| Microservices | /products | | | | |
| Microservices | /auth | | | | |
| Microservices | /orders | | | | |
| Microservices | /checkout | | | | |

### Tab: Test 5 — Data Consistency
| Architecture | Run | Initial Stock | Successful Orders | Final Stock | Conserves? (S+F=I) | Oversold? |
|---|---|---|---|---|---|---|
| Monolith | 1 | 5 | | | | |
| Monolith | 2 | 5 | | | | |
| ... | | | | | | |
| Microservices | 1 | 5 | | | | |
| ... | | | | | | |

### Tab: Test 6 — Scaling
| Run | Architecture | Configuration | RPS | p95 | Total CPU% | RPS per 1% CPU |
|---|---|---|---|---|---|---|
| A | Monolith | Default 0.5 CPU | | | | |
| B | Monolith | Vertical scale 1.5 CPU | | | | |
| C | Microservices | Default | | | | |
| D | Microservices | 3x catalog | | | | |

## Tips for Clean Data

1. **Always reset between runs.** `docker compose down -v && docker compose up --build`
   The `-v` flag is critical — it wipes the database volumes so init.sql re-runs.

2. **Wait 10-15 seconds after `docker compose up`** before starting a test.
   Containers take a moment to fully initialize, especially Postgres.

3. **Close other resource-heavy apps** during testing. Browser tabs, IDE,
   Spotlight indexing, Time Machine backups can all skew Docker container
   resource usage. Activity Monitor is your friend for spotting these.

4. **Run tests at least twice** if results look weird. Sometimes the first
   run has cold-start effects (Python import, connection pool warmup).

5. **Capture docker stats during EVERY test** in a second terminal:
   ```bash
   while true; do docker stats --no-stream; sleep 5; done
   ```
   To save it to a file:
   ```bash
   while true; do docker stats --no-stream >> docker-stats-test3-monolith.txt; sleep 5; done
   ```
   Press Ctrl+C to stop the loop.

6. **Save all Locust CSV exports.** Click "Download Data" tab in the UI,
   download all three CSVs (requests, failures, exceptions). Keep them
   organized in folders per test.

## macOS-Specific Tips

### curl works natively
Unlike Windows PowerShell, macOS Terminal's `curl` is the real curl.
Use single quotes around JSON to avoid shell escaping headaches:

```bash
curl -X POST http://localhost:5000/checkout \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 1, "product_id": 1}'
```

### Apple Silicon (M-series chip) considerations
Docker images for Postgres and Python both have native ARM builds, so
performance should be excellent. If you ever see warnings about platform
mismatch (e.g. "image was built for linux/amd64"), it means an image is
running through Rosetta 2 emulation — which is slower. The base images
in your project (postgres:15, python:3.11-slim) are multi-arch, so this
shouldn't be an issue.

### File watching and resource usage
Docker Desktop on Mac uses a virtual machine under the hood, which can be
heavy on resources. In Docker Desktop's Settings → Resources, allocate
at least 4 GB of memory and 2 CPUs. For load testing, 6-8 GB is better.

### Finding container names
The `docker ps` output shows container names. On Mac, they typically look
like `monolith-app-1` or `microservices-catalog-service-1`. Use these
exact names with `docker stop` and `docker start`:

```bash
docker ps                              # find the name
docker stop monolith-app-1
docker start monolith-app-1
```

## What Your Final Paper Will Show

When you have all the data collected, the story it tells should look like this:

- **Tests 1, 2, 3**: Monolith is faster for individual operations,
  with the gap widening as operations become more complex.
- **Test 4**: Microservices contain failures while monoliths don't —
  the "blast radius" comparison is dramatic and visual.
- **Test 5**: Monoliths give you correctness for free; microservices
  require explicit coordination patterns and may still get it wrong.
- **Test 6**: Microservices scale resources more efficiently when only
  part of the system is under pressure.

That's a complete trade-off picture supported by data, which is exactly
what a senior CS project should deliver.
