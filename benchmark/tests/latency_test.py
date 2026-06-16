import time
import requests
import random
import benchmark_utils as utils
import benchmark_config as config

logger = utils.setup_logger("latency_test")

def run():
    logger.info("Starting Latency Tests V2...")
    
    end_to_end_latencies = []
    raw_data = []
    
    cold_start_latency = 0
    
    # 1. Cold Start
    logger.info("Executing Cold Start Request...")
    try:
        query = random.choice(config.SAMPLE_QUERIES)
        start_time = time.perf_counter()
        response = requests.post(config.SEARCH_API, json={"query": query, "language": "en"}, timeout=10)
        cold_start_latency = (time.perf_counter() - start_time) * 1000
        raw_data.append(["Cold_Start", query, cold_start_latency, response.status_code])
    except Exception as e:
        logger.error(f"Cold start request failed: {e}")
        raw_data.append(["Cold_Start", query, -1, "Error"])

    # 2. Warm-Up Phase
    logger.info(f"Executing {config.WARMUP_ITERATIONS} Warm-up requests...")
    for i in range(config.WARMUP_ITERATIONS):
        try:
            query = random.choice(config.SAMPLE_QUERIES)
            requests.post(config.SEARCH_API, json={"query": query, "language": "en"}, timeout=10)
        except Exception:
            pass # Ignore warmup failures
            
    # 3. Actual Benchmarking
    logger.info(f"Executing {config.ITERATIONS} Benchmark iterations...")
    for i in range(config.ITERATIONS):
        query = random.choice(config.SAMPLE_QUERIES)
        payload = {"query": query, "language": "en"}
        
        start_time = time.perf_counter()
        try:
            response = requests.post(config.SEARCH_API, json=payload, timeout=10)
            end_time = time.perf_counter()
            
            if response.status_code == 200:
                latency_ms = (end_time - start_time) * 1000
                end_to_end_latencies.append(latency_ms)
                raw_data.append(["Benchmark", query, latency_ms, response.status_code])
            else:
                logger.warning(f"Iteration {i}: Received non-200 status code: {response.status_code}")
                raw_data.append(["Benchmark", query, -1, response.status_code])
        except Exception as e:
            logger.error(f"Iteration {i}: Request failed: {e}")
            raw_data.append(["Benchmark", query, -1, "Error"])
            
    metrics = utils.calculate_metrics(end_to_end_latencies)
    
    # Generate histogram
    utils.generate_histogram(
        end_to_end_latencies, 
        "API Response Latency Distribution", 
        "Latency (ms)", 
        "Frequency", 
        "latency_histogram.png"
    )
    
    # Dump Raw CSV
    utils.save_csv(["Type", "Query", "Latency_ms", "StatusCode"], raw_data, "latency_raw.csv", is_raw=True)
    
    results = {
        "cold_start_latency_ms": cold_start_latency,
        "warm_start_latency_ms": metrics.get("average", 0),
        "overall_metrics": metrics,
        "iterations_successful": len(end_to_end_latencies),
        "iterations_attempted": config.ITERATIONS
    }
    
    logger.info(f"Latency Tests Completed. Cold Start: {cold_start_latency:.2f}ms, Warm Avg: {metrics.get('average', 0):.2f}ms")
    return results
