import requests
import benchmark_utils as utils
import benchmark_config as config

logger = utils.setup_logger("fault_tolerance_test")

def check_graceful_failure(name, response, expected_status_codes):
    passed = response.status_code in expected_status_codes
    status = "PASS" if passed else f"FAIL (Got {response.status_code})"
    logger.info(f"[{status}] {name}")
    return passed

def run():
    logger.info("Starting Fault Tolerance Tests...")
    
    results = {}
    total_tests = 0
    passed_tests = 0
    
    # 1. Empty Query
    try:
        total_tests += 1
        resp = requests.post(config.SEARCH_API, json={"query": "", "language": "en"}, timeout=5)
        if check_graceful_failure("Empty Query", resp, [400, 422]):
            passed_tests += 1
    except Exception as e:
        logger.error(f"[FAIL] Empty Query (Exception: {e})")
        
    # 2. Invalid JSON (Sending string instead of dict)
    try:
        total_tests += 1
        resp = requests.post(config.SEARCH_API, data="Invalid JSON String", headers={"Content-Type": "application/json"}, timeout=5)
        if check_graceful_failure("Invalid JSON Format", resp, [400]):
            passed_tests += 1
    except Exception as e:
        logger.error(f"[FAIL] Invalid JSON Format (Exception: {e})")
        
    # 3. Very Long Query
    try:
        total_tests += 1
        long_query = "Software Engineer " * 1000
        resp = requests.post(config.SEARCH_API, json={"query": long_query, "language": "en"}, timeout=15)
        # Should either process it successfully (200) or gracefully reject it (400/413) but NOT crash (500)
        if check_graceful_failure("Very Long Query", resp, [200, 400, 413, 422]):
            passed_tests += 1
    except Exception as e:
        logger.error(f"[FAIL] Very Long Query (Exception: {e})")
        
    # 4. Unsupported Language
    try:
        total_tests += 1
        resp = requests.post(config.SEARCH_API, json={"query": "Ingeniero", "language": "xyz"}, timeout=5)
        if check_graceful_failure("Unsupported Language", resp, [200, 400, 422]):
            passed_tests += 1
    except Exception as e:
        logger.error(f"[FAIL] Unsupported Language (Exception: {e})")
        
    # 5. Invalid Admin Login
    try:
        total_tests += 1
        resp = requests.post(f"{config.ADMIN_API}/login", data={"password": "wrongpassword"}, timeout=5)
        # Usually a redirect or a 401/403
        if check_graceful_failure("Invalid Admin Login", resp, [200, 302, 401, 403]):
            passed_tests += 1
    except Exception as e:
        logger.error(f"[FAIL] Invalid Admin Login (Exception: {e})")
        
    # Note: Server Restart and Database Reconnect are harder to test automatically from the client
    # without SSH access to the server, so they are typically manual or require agent scripts.
    
    results = {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "pass_rate_percent": (passed_tests / total_tests * 100) if total_tests > 0 else 0
    }
    
    logger.info(f"Fault Tolerance Test Completed. Pass Rate: {results['pass_rate_percent']:.1f}%")
    return results
