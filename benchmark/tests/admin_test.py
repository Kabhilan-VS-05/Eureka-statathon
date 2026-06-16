import time
import requests
import benchmark_utils as utils
import benchmark_config as config

logger = utils.setup_logger("admin_test")

def run():
    logger.info("Starting Admin Performance Tests...")
    results = {}
    
    with requests.Session() as session:
        # 1. Login
        start_time = time.perf_counter()
        try:
            login_resp = session.post(
                f"{config.ADMIN_API}/login", 
                data={"password": config.ADMIN_PASSWORD},
                timeout=5
            )
            login_time = (time.perf_counter() - start_time) * 1000
            if login_resp.status_code not in [200, 302]:
                logger.warning(f"Admin login returned {login_resp.status_code}")
                
            results["login_latency_ms"] = login_time
            
        except Exception as e:
            logger.error(f"Admin login failed: {e}")
            results["error"] = "Login failed"
            return results

        # Simulated payloads
        occ_payload = {
            "title": "Benchmark Occupation",
            "description": "Created during benchmark",
            "requirements": "None"
        }
        
        # 2. Add Occupation
        start_time = time.perf_counter()
        occ_id = None
        try:
            resp = session.post(f"{config.ADMIN_API}/occupations/add", data=occ_payload, timeout=5)
            results["add_occupation_latency_ms"] = (time.perf_counter() - start_time) * 1000
            
            # If API returns JSON with ID
            if resp.status_code == 200:
                try:
                    occ_id = resp.json().get("id", 999999)
                except:
                    occ_id = 999999
        except Exception as e:
            logger.error(f"Add occupation failed: {e}")
            
        # 3. Edit Occupation
        start_time = time.perf_counter()
        if occ_id:
            try:
                occ_payload["description"] = "Updated by benchmark"
                session.post(f"{config.ADMIN_API}/occupations/edit/{occ_id}", data=occ_payload, timeout=5)
                results["edit_occupation_latency_ms"] = (time.perf_counter() - start_time) * 1000
            except Exception as e:
                logger.error(f"Edit occupation failed: {e}")
                
        # 4. Delete Occupation
        start_time = time.perf_counter()
        if occ_id:
            try:
                session.post(f"{config.ADMIN_API}/occupations/delete/{occ_id}", timeout=5)
                results["delete_occupation_latency_ms"] = (time.perf_counter() - start_time) * 1000
            except Exception as e:
                logger.error(f"Delete occupation failed: {e}")

        # Rebuild operations (might take long)
        rebuild_endpoints = {
            "search_asset_rebuild": "/api/rebuild/search",
            "embedding_rebuild": "/api/rebuild/embeddings",
            "faiss_rebuild": "/api/rebuild/faiss"
        }
        
        for name, path in rebuild_endpoints.items():
            start_time = time.perf_counter()
            try:
                resp = session.post(f"{config.ADMIN_API}{path}", timeout=120) # Larger timeout for rebuilds
                latency = (time.perf_counter() - start_time) * 1000
                results[f"{name}_latency_ms"] = latency
                logger.info(f"{name} completed in {latency:.1f}ms (Status: {resp.status_code})")
            except Exception as e:
                logger.error(f"{name} failed: {e}")
                
    logger.info("Admin Tests Completed.")
    return results
