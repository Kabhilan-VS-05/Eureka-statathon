import math
import benchmark_utils as utils

logger = utils.setup_logger("scalability_test")

def run(previous_results=None):
    logger.info("Starting Scalability Projection...")
    previous_results = previous_results or {}
    
    # Try to get baseline metrics from throughput or latency test
    baseline_rps = 50.0 # fallback
    baseline_lat = 50.0 # fallback ms
    
    if "throughput" in previous_results and previous_results["throughput"].get("requests_per_second", 0) > 0:
        baseline_rps = previous_results["throughput"]["requests_per_second"]
        
    if "latency" in previous_results and "overall_metrics" in previous_results["latency"]:
        baseline_lat = previous_results["latency"]["overall_metrics"].get("average", baseline_lat)
        
    logger.info(f"Using baseline: {baseline_rps:.1f} RPS, {baseline_lat:.1f}ms latency")
    
    # Current dataset size (approximation if not available)
    current_size = 1000 
    
    # We assume search latency in FAISS (FlatL2) scales linearly with N.
    # Total latency = Network/API overhead + Search time
    # Let's assume 50% of the baseline latency is fixed overhead, and 50% scales linearly with dataset size.
    fixed_overhead = baseline_lat * 0.5
    search_time_per_1k = (baseline_lat * 0.5) / (current_size / 1000) if current_size > 0 else 10
    
    target_sizes = [1000, 10000, 25000, 50000, 100000]
    
    projections = {}
    projected_latencies = []
    projected_rps = []
    
    for size in target_sizes:
        # Projected latency = fixed + search_time_per_1k * (size / 1000)
        proj_lat = fixed_overhead + search_time_per_1k * (size / 1000)
        
        # Projected RPS = (baseline RPS) * (baseline latency / projected latency)
        # Assuming system is CPU bound by search
        proj_rps = baseline_rps * (baseline_lat / proj_lat) if proj_lat > 0 else 0
        
        projections[f"size_{size}"] = {
            "dataset_size": size,
            "projected_latency_ms": proj_lat,
            "projected_rps": proj_rps
        }
        
        projected_latencies.append(proj_lat)
        projected_rps.append(proj_rps)
        
        logger.info(f"Projection for {size} items: {proj_lat:.1f}ms Latency, {proj_rps:.1f} RPS")

    # Generate Projection Charts
    utils.generate_line_chart(
        target_sizes, projected_latencies,
        "Scalability Projection: Latency vs Dataset Size",
        "Dataset Size", "Projected Latency (ms)",
        "scalability_latency_projection.png"
    )
    
    utils.generate_line_chart(
        target_sizes, projected_rps,
        "Scalability Projection: Throughput vs Dataset Size",
        "Dataset Size", "Projected RPS",
        "scalability_rps_projection.png"
    )

    logger.info("Scalability Projection Completed.")
    return projections
