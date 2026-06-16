import os
import time
import benchmark_utils as utils
import benchmark_config as config

logger = utils.setup_logger("browser_test")

def run():
    logger.info("Starting Browser Performance Tests...")
    
    results = {}
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright is not installed. Skipping Browser Tests.")
        return {"error": "playwright not installed. Run 'pip install playwright' and 'playwright install'"}
        
    try:
        with sync_playwright() as p:
            # We use chromium for standard testing
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigate to the main page
            start_time = time.perf_counter()
            response = page.goto(config.BASE_URL, wait_until="networkidle")
            dom_load_time = (time.perf_counter() - start_time) * 1000
            
            if response and response.ok:
                # Get performance metrics via JavaScript
                perf_entries = page.evaluate("""
                    () => {
                        const paint = performance.getEntriesByType('paint');
                        const fcpEntry = paint.find(entry => entry.name === 'first-contentful-paint');
                        
                        // LCP is harder without PerformanceObserver in page, but we can try to estimate
                        // or just get standard nav timings
                        const nav = performance.getEntriesByType('navigation')[0];
                        
                        return {
                            fcp: fcpEntry ? fcpEntry.startTime : null,
                            domInteractive: nav.domInteractive,
                            domComplete: nav.domComplete,
                            loadEventEnd: nav.loadEventEnd
                        };
                    }
                """)
                
                # Take a screenshot as visual evidence
                screenshot_path = os.path.join(config.SCREENSHOTS_DIR, "browser_test_home.png")
                os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
                page.screenshot(path=screenshot_path)
                
                results = {
                    "dom_load_time_ms": dom_load_time,
                    "first_contentful_paint_ms": perf_entries.get("fcp"),
                    "dom_interactive_ms": perf_entries.get("domInteractive"),
                    "dom_complete_ms": perf_entries.get("domComplete"),
                    "load_event_end_ms": perf_entries.get("loadEventEnd"),
                    "screenshot_path": screenshot_path
                }
                logger.info(f"Browser Load Time: {dom_load_time:.2f}ms")
            else:
                logger.error(f"Failed to load {config.BASE_URL}")
                results["error"] = "Failed to load page"
                
            browser.close()
            
    except Exception as e:
        logger.error(f"Browser test failed: {e}")
        results["error"] = str(e)
        
    logger.info("Browser Tests Completed.")
    return results
