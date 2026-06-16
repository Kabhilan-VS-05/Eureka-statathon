# AI Semantic Search NCO - Performance Benchmarking Framework V2

## Purpose of Benchmarking
This local benchmarking framework is designed specifically for evaluating the **performance, scalability, and stability** of the AI Semantic Search NCO project. 

> **Important Scope Restrictions:**
> This framework explicitly does **NOT** measure search accuracy, Top-K retrieval quality, Precision, Recall, MRR, or NDCG. It is strictly a performance validation suite.

## Test Architecture
The framework is completely isolated from production code. It utilizes a centralized runner (`benchmark_runner.py`) to orchestrate a suite of modular tests located in the `tests/` directory.

The architecture allows for:
1. **Local execution** against a development server.
2. **Remote execution** against an AWS EC2 instance by simply changing the `TARGET` and `BASE_URL` in `benchmark_config.py`.

### Folder Structure & Reproducibility
Every benchmark execution automatically generates a timestamped directory (e.g. `reports/2026-06-12_14-30-15/`). This ensures **zero data loss** and perfect reproducibility. The framework automatically copies the newest run to `reports/latest/` for convenience.

```text
benchmark/
├── README.md                  
├── benchmark_config.py        # Centralized configurations (URLs, targets, warmups)
├── benchmark_runner.py        # Core orchestration engine
├── run_benchmark.py           # CLI entry point
├── benchmark_utils.py         # Helpers for logging, math, and graphing
├── tests/                     # Modular test files
│   ├── system_info.py         
│   ├── latency_test.py        # Cold start, warm-ups, and latency metrics
│   ├── cpu_memory_test.py     # Background CPU, RAM, Disk I/O, Network I/O
│   ├── concurrent_users_test.py 
│   ├── throughput_test.py     
│   ├── stress_test.py         
│   ├── endurance_test.py      
│   ├── fault_tolerance_test.py
│   ├── database_test.py       
│   ├── admin_test.py          
│   ├── browser_test.py        
│   └── scalability_test.py    
├── logs/                      # Raw unaggregated CSV dumps (proof of execution)
└── reports/                   
    ├── 2026-06-12_14-30-15/   # Timestamped execution artifact
    │   ├── benchmark_report.md
    │   ├── benchmark_report.pdf
    │   ├── benchmark_results.json
    │   ├── benchmark_results.csv
    │   └── graphs/            # Matplotlib visual artifacts
    └── latest/                # Copy of the most recent benchmark run
```

---

## Methodology & Individual Tests

### Warm-Ups & Cold Starts
Before latency is measured, the system fires a configurable number of "Warm-up" requests to populate caches and initialize models. The very first request sent to the server is recorded separately as the **Cold Start Latency**. 

### Overall Performance Score
An unweighted average score out of 100 is automatically calculated based on the performance across multiple categories (e.g., Latency, CPU Usage, Fault Tolerance, Throughput). This provides a quick baseline for evaluating server health.

### 1. System Information (`system_info.py`)
- **Why it matters:** Provides context to the benchmark results. 
- **Industry best practices:** Baseline the hardware and software stack (Git commit, Python version) before load testing.
- **Evidence collected:** OS, CPU, RAM, GPU, versions.

### 2. API & Search Latency (`latency_test.py`)
- **Why it matters:** Direct measure of User Experience. High latency leads to abandonment.
- **Expected interpretation:** P95 should ideally be under 500ms.
- **Evidence collected:** Cold start latency, Warm start latency, P95, raw CSV logs (`latency_raw.csv`).

### 3. CPU & Memory Usage (`cpu_memory_test.py`)
- **Why it matters:** Identifies bottlenecks (CPU-bound vs Memory-bound).
- **Industry best practices:** Continuous monitoring during load.
- **Evidence collected:** CPU %, RAM %, Disk I/O, Network I/O, raw CSV logs (`cpu_memory_raw.csv`).

### 4. Concurrent User Benchmark (`concurrent_users_test.py`)
- **Why it matters:** Simulates real-world traffic with multiple users.
- **Evidence collected:** Avg latency, Max latency, RPS, Error rate, raw CSV logs (`concurrency_*_raw.csv`).

### 5. Throughput Benchmark (`throughput_test.py`)
- **Why it matters:** Defines the maximum capacity of the server (Requests Per Second).
- **Evidence collected:** Max RPS, Max RPM, raw CSV logs (`throughput_raw.csv`).

### 6. Stress Test (`stress_test.py`)
- **Why it matters:** Finds the exact breaking point of the system.
- **Expected interpretation:** The "Failure Point" RPS tells you the absolute maximum traffic the node can handle before crashing.
- **Evidence collected:** Failure point RPS, Error rate curve, raw CSV logs (`stress_raw.csv`).

### 7. Endurance Test (`endurance_test.py`)
- **Why it matters:** Uncovers memory leaks and thermal throttling over time.

### 8. Fault Tolerance (`fault_tolerance_test.py`)
- **Why it matters:** Ensures malicious or malformed input doesn't crash the server.

### 9. Database Performance (`database_test.py`)
- **Why it matters:** Isolates Postgres performance from Flask/Python overhead.

### 10. Admin Performance (`admin_test.py`)
- **Why it matters:** Rebuilding the FAISS index or embedding model can lock the server.

### 11. Browser Performance (`browser_test.py`)
- **Why it matters:** API latency is only half the story; DOM rendering time completes the UX.

### 12. Scalability Projection (`scalability_test.py`)
- **Why it matters:** Predicts AWS costs and hardware requirements for future growth.

---

## Execution Guide

### Prerequisites
Install the benchmark-specific dependencies:
```bash
pip install requests psutil matplotlib playwright psycopg2-binary markdown pdfkit
playwright install chromium
```
*(Note: PDF generation requires `wkhtmltopdf` to be installed on your operating system).*

### How to Run Benchmarks
Use the CLI entry point `run_benchmark.py`:

```bash
python run_benchmark.py --test all
python run_benchmark.py --test latency
python run_benchmark.py --test stress
```

### Reproducibility & AWS Comparison
Every report generates a `benchmark_results.json` containing the exact configurations used.
To benchmark your AWS environment:
1. Open `benchmark_config.py`.
2. Change `TARGET = "AWS"` and `BASE_URL = "https://your-aws-domain.com"`.
3. Run the tests.
4. Compare the new timestamped folder with your previous `Local` runs.
