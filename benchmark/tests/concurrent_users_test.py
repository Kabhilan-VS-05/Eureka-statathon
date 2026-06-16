import time
import requests
import random
import concurrent.futures
import benchmark_utils as utils
import benchmark_config as config
from tests import cpu_memory_test

logger = utils.setup_logger("concurrent_users_test")

def simulate_user(user_id, duration):
    end_time = time.time() + duration
    latencies = []
    return_data = []
    errors = 0
    requests_made = 0
    
    with requests.Session() as session:
        while time.time() < end_time:
            query = random.choice(config.SAMPLE_QUERIES)
            start_req = time.perf_counter()
            try:
                # Add a small timeout so tests don't hang indefinitely under load
                response = session.post(
                    config.SEARCH_API, 
                    json={"query": query, "language": "en"},
                    timeout=15
                )
                if response.status_code == 200:
                    lat = (time.perf_counter() - start_req) * 1000
                    latencies.append(lat)
                    return_data.append([time.time(), user_id, query, lat, response.status_code])
                else:
                    errors += 1
                    return_data.append([time.time(), user_id, query, -1, response.status_code])
            except Exception:
                errors += 1
                return_data.append([time.time(), user_id, query, -1, "Error"])
            
            requests_made += 1
            # Small think time
            time.sleep(0.5)
            
    return latencies, errors, requests_made, return_data

def run():
    logger.info("Starting Concurrent Users Test...")
    
    levels = config.CONCURRENT_USERS_LEVELS
    duration_per_level = 10  # Seconds to run each concurrency level
    
    results = {}
    
    avg_latencies = []
    max_latencies = []
    rps_list = []
    
    for num_users in levels:
        logger.info(f"Testing with {num_users} concurrent users for {duration_per_level}s...")
        
        cpu_memory_test.start_monitor(interval=0.5)
        start_time = time.time()
        
        all_latencies = []
        raw_rows = []
        total_errors = 0
        total_requests = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(simulate_user, i, duration_per_level) for i in range(num_users)]
            for future in concurrent.futures.as_completed(futures):
                lats, errs, reqs, raw_dat = future.result()
                all_latencies.extend(lats)
                raw_rows.extend(raw_dat)
                total_errors += errs
                total_requests += reqs
                
        actual_duration = time.time() - start_time
        res_sys = cpu_memory_test.stop_monitor()
        
        # Save raw data for this level
        utils.save_csv(
            ["Timestamp", "User_ID", "Query", "Latency_ms", "StatusCode"], 
            raw_rows, 
            f"concurrency_{num_users}_raw.csv", 
            is_raw=True
        )
        
        rps = total_requests / actual_duration if actual_duration > 0 else 0
        
        if all_latencies:
            avg_lat = sum(all_latencies)/len(all_latencies)
            max_lat = max(all_latencies)
        else:
            avg_lat = 0
            max_lat = 0
            
        avg_latencies.append(avg_lat)
        max_latencies.append(max_lat)
        rps_list.append(rps)
        
        results[f"users_{num_users}"] = {
            "average_latency_ms": avg_lat,
            "max_latency_ms": max_lat,
            "error_rate_percent": (total_errors / total_requests * 100) if total_requests > 0 else 0,
            "requests_per_second": rps,
            "cpu_avg_percent": res_sys.get("cpu_avg", 0),
            "mem_avg_percent": res_sys.get("mem_avg", 0)
        }
        
        logger.info(f"Level {num_users}: RPS={rps:.2f}, AvgLat={avg_lat:.2f}ms, Errors={total_errors}")

    # Generate comparative charts
    utils.generate_line_chart(
        levels, avg_latencies,
        "Average Latency vs Concurrent Users",
        "Concurrent Users", "Avg Latency (ms)",
        "concurrent_users_latency.png"
    )
    
    utils.generate_line_chart(
        levels, rps_list,
        "Throughput vs Concurrent Users",
        "Concurrent Users", "Requests per Second (RPS)",
        "concurrent_users_rps.png"
    )

    logger.info("Concurrent Users Test Completed.")
    return results
