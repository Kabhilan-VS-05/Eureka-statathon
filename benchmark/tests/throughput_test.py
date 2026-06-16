import time
import requests
import random
import concurrent.futures
import benchmark_utils as utils
import benchmark_config as config
from tests import cpu_memory_test

logger = utils.setup_logger("throughput_test")

def throughput_worker(worker_id, duration, end_event):
    requests_made = 0
    errors = 0
    return_data = []
    
    with requests.Session() as session:
        while not end_event.is_set():
            query = random.choice(config.SAMPLE_QUERIES)
            try:
                response = session.post(
                    config.SEARCH_API, 
                    json={"query": query, "language": "en"},
                    timeout=5
                )
                if response.status_code != 200:
                    errors += 1
                return_data.append([time.time(), worker_id, query, response.status_code])
            except Exception:
                errors += 1
                return_data.append([time.time(), worker_id, query, "Error"])
            requests_made += 1
            
    return requests_made, errors, return_data

def run():
    logger.info("Starting Throughput Test...")
    
    duration = 30  # seconds
    workers = 50  # high number of workers to saturate the server
    
    cpu_memory_test.start_monitor(interval=0.5)
    
    # We use an event to signal workers to stop simultaneously
    import threading
    end_event = threading.Event()
    
    logger.info(f"Blasting API with {workers} workers for {duration} seconds...")
    start_time = time.time()
    
    total_requests = 0
    total_errors = 0
    raw_rows = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(throughput_worker, i, duration, end_event) for i in range(workers)]
        
        time.sleep(duration)
        end_event.set()
        
        for future in concurrent.futures.as_completed(futures):
            reqs, errs, raw_dat = future.result()
            total_requests += reqs
            total_errors += errs
            raw_rows.extend(raw_dat)
            
    actual_duration = time.time() - start_time
    res_sys = cpu_memory_test.stop_monitor()
    
    utils.save_csv(
        ["Timestamp", "Worker_ID", "Query", "StatusCode"], 
        raw_rows, 
        "throughput_raw.csv", 
        is_raw=True
    )
    
    rps = total_requests / actual_duration if actual_duration > 0 else 0
    rpm = rps * 60
    
    results = {
        "duration_seconds": actual_duration,
        "total_requests": total_requests,
        "total_errors": total_errors,
        "requests_per_second": rps,
        "requests_per_minute": rpm,
        "cpu_avg_percent": res_sys.get("cpu_avg", 0),
        "mem_avg_percent": res_sys.get("mem_avg", 0)
    }
    
    logger.info(f"Throughput Result: {rps:.2f} RPS ({rpm:.2f} RPM)")
    logger.info("Throughput Test Completed.")
    
    return results
