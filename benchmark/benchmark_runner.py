import os
import json
import time
from datetime import datetime
import benchmark_utils as utils
import benchmark_config as config

# Import all tests
from tests import (
    system_info, latency_test, cpu_memory_test, concurrent_users_test,
    throughput_test, stress_test, endurance_test, fault_tolerance_test,
    database_test, admin_test, browser_test, scalability_test
)

logger = utils.setup_logger("benchmark_runner")

def collect_metadata():
    start_dt = datetime.now()
    sys_info = system_info.run()
    
    metadata = {
        "Benchmark Version": config.BENCHMARK_VERSION,
        "Target Environment": config.TARGET,
        "Host URL": config.BASE_URL,
        "Git Commit Hash": utils.get_git_commit(),
        "Test Machine": sys_info.get("CPU Name", "Unknown"),
        "Operating System": sys_info.get("OS", "Unknown"),
        "CPU Cores": sys_info.get("Total Cores (Logical)", "Unknown"),
        "RAM": sys_info.get("Total RAM", "Unknown"),
        "GPU": sys_info.get("GPU", "Unknown"),
        "Python Version": sys_info.get("Python Version", "Unknown"),
        "Benchmark Start Time": start_dt.strftime('%Y-%m-%d %H:%M:%S'),
        "system_info_full": sys_info
    }
    return metadata, start_dt

def run_all_tests():
    logger.info("Starting Full Benchmark Suite V2")
    utils.get_report_dirs() # Initialize timestamp folder
    
    metadata, start_dt = collect_metadata()
    results = {"metadata": metadata}
    
    logger.info("Running Latency Tests...")
    results["latency"] = latency_test.run()
    
    logger.info("Running CPU & Memory Tests...")
    results["cpu_memory"] = cpu_memory_test.run()
    
    logger.info("Running Concurrent Users Tests...")
    results["concurrent_users"] = concurrent_users_test.run()
    
    logger.info("Running Throughput Tests...")
    results["throughput"] = throughput_test.run()
    
    logger.info("Running Stress Tests...")
    results["stress"] = stress_test.run()
    
    logger.info("Running Endurance Tests...")
    results["endurance"] = endurance_test.run()
    
    logger.info("Running Fault Tolerance Tests...")
    results["fault_tolerance"] = fault_tolerance_test.run()
    
    logger.info("Running Database Tests...")
    results["database"] = database_test.run()
    
    logger.info("Running Admin Tests...")
    results["admin"] = admin_test.run()
    
    logger.info("Running Browser Tests...")
    results["browser"] = browser_test.run()
    
    logger.info("Running Scalability Projection...")
    results["scalability"] = scalability_test.run(results)
    
    end_dt = datetime.now()
    metadata["Benchmark End Time"] = end_dt.strftime('%Y-%m-%d %H:%M:%S')
    metadata["Total Duration"] = str(end_dt - start_dt)
    
    # Save overall results
    utils.save_json(results, "benchmark_results.json")
    save_csv_summary(results)
    
    score = utils.calculate_score(results)
    results["overall_score"] = score
    
    generate_markdown_report(results)
    generate_pdf_report()
    
    utils.copy_to_latest()
    
    logger.info(f"Full Benchmark Suite Completed. Overall Score: {score:.1f}/100")
    return results

def run_specific_test(test_name):
    logger.info(f"Starting specific test: {test_name}")
    utils.get_report_dirs()
    
    metadata, start_dt = collect_metadata()
    results = {"metadata": metadata}
    
    test_module = globals().get(test_name)
    if not test_module:
        logger.error(f"Test module {test_name} not found.")
        return
        
    results[test_name] = test_module.run()
    
    end_dt = datetime.now()
    metadata["Benchmark End Time"] = end_dt.strftime('%Y-%m-%d %H:%M:%S')
    metadata["Total Duration"] = str(end_dt - start_dt)
    
    utils.save_json(results, f"benchmark_{test_name}_results.json")
    utils.copy_to_latest()
    logger.info(f"Completed {test_name}.")
    return results

def generate_markdown_report(results):
    logger.info("Generating Markdown Report V2...")
    rep_dir, _ = utils.get_report_dirs()
    report_path = os.path.join(rep_dir, "benchmark_report.md")
    
    meta = results.get("metadata", {})
    score = results.get("overall_score", 0)
    
    with open(report_path, "w", encoding="utf-8") as f:
        # 1. Cover Page / Title
        f.write("# Performance Benchmark Report\n\n")
        f.write(f"**Date:** {meta.get('Benchmark Start Time')}\n")
        f.write(f"**Environment:** {meta.get('Target Environment')} ({meta.get('Host URL')})\n\n")
        
        # 2. Executive Summary
        f.write("## Executive Summary\n\n")
        f.write(f"### Overall Performance Score: {score:.1f} / 100\n\n")
        
        f.write("| Category | Status |\n| --- | --- |\n")
        f.write("| API Latency | " + ("Excellent" if score > 80 else "Good" if score > 50 else "Poor") + " |\n")
        f.write("| Throughput | " + ("Excellent" if results.get("throughput", {}).get("requests_per_second", 0) > 200 else "Good") + " |\n")
        f.write("| Fault Tolerance | " + ("Passed" if results.get("fault_tolerance", {}).get("pass_rate_percent", 0) == 100 else "Issues Found") + " |\n")
        f.write("\n")
        
        # 3. Test Environment & System Configuration
        f.write("## Test Environment & System Configuration\n\n")
        for k in ["Benchmark Version", "Git Commit Hash", "Test Machine", "Operating System", "CPU Cores", "RAM", "GPU", "Python Version"]:
            f.write(f"- **{k}:** {meta.get(k)}\n")
        f.write("\n")
        
        # 4. Benchmark Methodology
        f.write("## Benchmark Methodology\n")
        f.write("This test isolates performance, scalability, and stability, explicitly excluding accuracy evaluations. ")
        f.write("Warm-ups were utilized prior to latency recordings to eliminate cold-start bias. Raw metrics were saved as CSVs for reproducibility.\n\n")
        
        # 5. Individual Test Results
        f.write("## Individual Test Results\n\n")
        if "latency" in results:
            l = results["latency"]
            f.write("### API Latency\n")
            f.write(f"- **Cold Start Latency:** {l.get('cold_start_latency_ms', 0):.2f} ms\n")
            f.write(f"- **Warm Start Avg:** {l.get('warm_start_latency_ms', 0):.2f} ms\n")
            f.write(f"- **P95 Latency:** {l.get('overall_metrics', {}).get('p95', 0):.2f} ms\n\n")
            
        if "throughput" in results:
            t = results["throughput"]
            f.write("### Throughput\n")
            f.write(f"- **Max Requests/Sec (RPS):** {t.get('requests_per_second', 0):.2f}\n")
            f.write(f"- **Total Requests Made:** {t.get('total_requests', 0)}\n\n")
            
        # 6. Graphs and Visualizations
        f.write("## Graphs and Visualizations\n")
        f.write("Refer to the `graphs/` directory for visual charts including Latency Histograms, CPU/Memory timelines, and Scalability projections.\n\n")
        
        # 7. Conclusion & Bottleneck Analysis
        f.write("## Conclusion & Bottlenecks\n")
        f.write("Based on the generated artifacts, review the stress test failure points to identify hardware constraints.\n")
        
    logger.info(f"Markdown report generated at {report_path}")

def save_csv_summary(results):
    logger.info("Generating CSV Summary...")
    headers = ["Test Category", "Metric", "Value"]
    rows = []
    
    if "latency" in results and "overall_metrics" in results["latency"]:
        for k, v in results["latency"]["overall_metrics"].items():
            rows.append(["Latency", k, f"{v:.2f}"])
            
    if "throughput" in results:
        rows.append(["Throughput", "RPS", f"{results['throughput'].get('requests_per_second', 0):.2f}"])
        
    utils.save_csv(headers, rows, "benchmark_results.csv")
    
def generate_pdf_report():
    logger.info("Attempting to generate PDF Report...")
    rep_dir, _ = utils.get_report_dirs()
    md_path = os.path.join(rep_dir, "benchmark_report.md")
    pdf_path = os.path.join(rep_dir, "benchmark_report.pdf")
    
    try:
        import markdown
        import pdfkit
        
        with open(md_path, 'r', encoding='utf-8') as f:
            html_text = markdown.markdown(f.read())
            
        pdfkit.from_string(html_text, pdf_path)
        logger.info(f"PDF report generated at {pdf_path}")
    except ImportError:
        logger.warning("markdown or pdfkit not installed. Run 'pip install markdown pdfkit' and install wkhtmltopdf to generate PDFs.")
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
