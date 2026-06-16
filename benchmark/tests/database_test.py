import time
import benchmark_utils as utils
import benchmark_config as config

logger = utils.setup_logger("database_test")

def run():
    logger.info("Starting Database Performance Tests...")
    
    results = {}
    
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        logger.error("psycopg2 is not installed. Skipping Database Tests.")
        return {"error": "psycopg2 not installed"}
        
    try:
        # Connect to DB
        conn = psycopg2.connect(config.DB_URI)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Setup temporary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_temp_table (
                id SERIAL PRIMARY KEY,
                data VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("TRUNCATE TABLE benchmark_temp_table")
        
        # 1. INSERT Latency
        insert_latencies = []
        for i in range(100):
            start = time.perf_counter()
            cursor.execute("INSERT INTO benchmark_temp_table (data) VALUES (%s)", (f"test_data_{i}",))
            insert_latencies.append((time.perf_counter() - start) * 1000)
        results["insert_latency_ms"] = utils.calculate_metrics(insert_latencies)
        
        # 2. SELECT Latency
        select_latencies = []
        for i in range(100):
            start = time.perf_counter()
            cursor.execute("SELECT * FROM benchmark_temp_table WHERE data = %s", (f"test_data_{i}",))
            cursor.fetchall()
            select_latencies.append((time.perf_counter() - start) * 1000)
        results["select_latency_ms"] = utils.calculate_metrics(select_latencies)
        
        # 3. UPDATE Latency
        update_latencies = []
        for i in range(100):
            start = time.perf_counter()
            cursor.execute("UPDATE benchmark_temp_table SET data = %s WHERE data = %s", (f"updated_{i}", f"test_data_{i}"))
            update_latencies.append((time.perf_counter() - start) * 1000)
        results["update_latency_ms"] = utils.calculate_metrics(update_latencies)
        
        # 4. DELETE Latency
        delete_latencies = []
        for i in range(100):
            start = time.perf_counter()
            cursor.execute("DELETE FROM benchmark_temp_table WHERE data = %s", (f"updated_{i}",))
            delete_latencies.append((time.perf_counter() - start) * 1000)
        results["delete_latency_ms"] = utils.calculate_metrics(delete_latencies)
        
        # 5. Bulk INSERT Latency
        bulk_data = [(f"bulk_data_{i}",) for i in range(1000)]
        start = time.perf_counter()
        psycopg2.extras.execute_batch(cursor, "INSERT INTO benchmark_temp_table (data) VALUES (%s)", bulk_data)
        results["bulk_insert_1000_latency_ms"] = (time.perf_counter() - start) * 1000
        
        # Cleanup
        cursor.execute("DROP TABLE IF EXISTS benchmark_temp_table")
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        results["error"] = str(e)
        
    logger.info("Database Tests Completed.")
    return results
