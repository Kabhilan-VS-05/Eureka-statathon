import time
import requests
import random
import concurrent.futures
import benchmark_utils as utils
import benchmark_config as config
from tests import cpu_memory_test

logger = utils.setup_logger("stress_test")

def make_request(session, worker_id):
    query = random.choice(config.SAMPLE_QUERIES)
    start_req = time.perf_counter()
    try:
        response = session.post(
            config.SEARCH_API, 
            json={"query": query, "language": "en"},
            timeout=10
        )
        latency = (time.perf_counter() - start_req) * 1000
        return latency, response.status_code != 200, [time.time(), worker_id, query, latency, response.status_code]
    except Exception:
        return 0, True, [time.time(), worker_id, query, -1, "Error"]

def run():
    logger.info("Starting Stress Test...")
    
    current_rps = config.STRESS_START_RPS
    step = config.STRESS_STEP_RPS
    max_rps = config.STRESS_MAX_RPS
    duration_per_step = 5  # short duration for stress steps
    
    results = {}
    failure_point = None
    
    rps_targets = []
    actual_rps = []
    error_rates = []
    latencies = []
    raw_rows = []
    
    with requests.Session() as session:
        while current_rps <= max_rps:
            logger.info(f"Stress step: Target {current_rps} RPS")
            
            cpu_memory_test.start_monitor(interval=0.5)
            
            # Since generating exact RPS with requests is tricky, 
            # we'll approximate by spawning tasks with sleep
            # A more precise way is to sleep the main thread between submissions
            
            step_latencies = []
            errors = 0
            requests_made = 0
            
            start_time = time.time()
            end_time = start_time + duration_per_step
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(current_rps, 200)) as executor:
                futures = []
                worker_id = 0
                while time.time() < end_time:
                    # Submit requests to maintain the target RPS
                    # We submit a batch and sleep
                    futures.append(executor.submit(make_request, session, worker_id))
                    worker_id += 1
                    time.sleep(1.0 / current_rps)
                    
                for future in concurrent.futures.as_completed(futures):
                    lat, is_error, raw_dat = future.result()
                    raw_rows.append(raw_dat)
                    if is_error:
                        errors += 1
                    elif lat > 0:
                        step_latencies.append(lat)
                    requests_made += 1
            
            actual_duration = time.time() - start_time
            sys_res = cpu_memory_test.stop_monitor()
            
            calc_rps = requests_made / actual_duration
            error_rate = (errors / requests_made * 100) if requests_made > 0 else 100
            avg_lat = sum(step_latencies)/len(step_latencies) if step_latencies else 0
            
            rps_targets.append(current_rps)
            actual_rps.append(calc_rps)
            error_rates.append(error_rate)
            latencies.append(avg_lat)
            
            results[f"target_{current_rps}"] = {
                "actual_rps": calc_rps,
                "error_rate": error_rate,
                "average_latency": avg_lat,
                "cpu_avg_percent": sys_res.get("cpu_avg", 0),
                "mem_avg_percent": sys_res.get("mem_avg", 0)
            }
            
            logger.info(f"Result: {calc_rps:.1f} RPS, Err: {error_rate:.1f}%, Lat: {avg_lat:.1f}ms")
            
            if error_rate > 5.0 or avg_lat > 5000: # 5% error or 5s latency
                failure_point = current_rps
                logger.warning(f"Failure point reached at target {current_rps} RPS")
                break
                
            current_rps += step

    results["failure_point_rps"] = failure_point or "Did not fail"
    
    utils.save_csv(
        ["Timestamp", "Worker_ID", "Query", "Latency_ms", "StatusCode"], 
        raw_rows, 
        "stress_raw.csv", 
        is_raw=True
    )
    
    # Generate Stress Curve
    utils.generate_line_chart(
        rps_targets, error_rates,
        "Stress Test: Error Rate vs Target RPS",
        "Target RPS", "Error Rate (%)",
        "stress_error_curve.png"
    )
    
    utils.generate_line_chart(
        rps_targets, latencies,
        "Stress Test: Latency vs Target RPS",
        "Target RPS", "Average Latency (ms)",
        "stress_latency_curve.png"
    )
    
    logger.info("Stress Test Completed.")
    return results
