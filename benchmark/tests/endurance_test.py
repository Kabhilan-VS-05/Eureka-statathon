import time
import requests
import random
import concurrent.futures
import threading
import benchmark_utils as utils
import benchmark_config as config
from tests import cpu_memory_test

logger = utils.setup_logger("endurance_test")

def endurance_worker(end_event, stats, lock):
    with requests.Session() as session:
        while not end_event.is_set():
            query = random.choice(config.SAMPLE_QUERIES)
            start_req = time.perf_counter()
            try:
                response = session.post(
                    config.SEARCH_API, 
                    json={"query": query, "language": "en"},
                    timeout=10
                )
                latency = (time.perf_counter() - start_req) * 1000
                is_error = response.status_code != 200
            except Exception:
                latency = 0
                is_error = True
                
            with lock:
                stats['requests'] += 1
                if is_error:
                    stats['errors'] += 1
                elif latency > 0:
                    stats['latencies'].append(latency)
                    
            time.sleep(1.0) # 1 request per second per worker

def run():
    logger.info(f"Starting Endurance Test for {config.ENDURANCE_DURATION_MINUTES} minutes...")
    
    duration_seconds = config.ENDURANCE_DURATION_MINUTES * 60
    workers = 5  # Moderate load
    
    cpu_memory_test.start_monitor(interval=5.0) # less frequent monitoring for long test
    
    end_event = threading.Event()
    stats = {'requests': 0, 'errors': 0, 'latencies': []}
    lock = threading.Lock()
    
    # Background thread to record periodic snapshots
    snapshots = []
    
    def snapshot_loop():
        start_time = time.time()
        while not end_event.is_set():
            time.sleep(60) # snapshot every minute
            if end_event.is_set():
                break
                
            with lock:
                reqs = stats['requests']
                errs = stats['errors']
                lats = stats['latencies'][:]
                
                # Reset for next minute
                stats['requests'] = 0
                stats['errors'] = 0
                stats['latencies'] = []
                
            avg_lat = sum(lats)/len(lats) if lats else 0
            err_rate = (errs / reqs * 100) if reqs > 0 else 0
            elapsed_mins = (time.time() - start_time) / 60
            
            snapshots.append({
                "minute": elapsed_mins,
                "requests": reqs,
                "error_rate": err_rate,
                "average_latency": avg_lat
            })
            logger.info(f"Endurance Min {elapsed_mins:.1f}: {reqs} reqs, {err_rate:.1f}% errs, {avg_lat:.1f}ms avg lat")

    snapshot_thread = threading.Thread(target=snapshot_loop, daemon=True)
    snapshot_thread.start()
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(endurance_worker, end_event, stats, lock) for _ in range(workers)]
        
        # We don't sleep for the whole duration, we loop to allow graceful interruption
        while time.time() - start_time < duration_seconds:
            time.sleep(1)
            
        end_event.set()
        
        for future in concurrent.futures.as_completed(futures):
            future.result()
            
    snapshot_thread.join(timeout=2)
    sys_res = cpu_memory_test.stop_monitor()
    
    results = {
        "duration_minutes": (time.time() - start_time) / 60,
        "snapshots": snapshots,
        "cpu_avg_percent": sys_res.get("cpu_avg", 0),
        "mem_avg_percent": sys_res.get("mem_avg", 0)
    }
    
    # Generate timeline graphs
    if snapshots:
        mins = [s["minute"] for s in snapshots]
        lats = [s["average_latency"] for s in snapshots]
        
        utils.generate_line_chart(
            mins, lats,
            "Endurance Test: Latency Drift Over Time",
            "Time (Minutes)", "Average Latency (ms)",
            "endurance_latency_timeline.png"
        )

    logger.info("Endurance Test Completed.")
    return results
