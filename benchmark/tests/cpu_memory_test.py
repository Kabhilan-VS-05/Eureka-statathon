import time
import threading
import psutil
import benchmark_utils as utils

logger = utils.setup_logger("cpu_memory_test")

_monitoring_active = False
_monitor_thread = None
_cpu_data = []
_mem_data = []
_disk_data = []
_net_data = []
_thread_data = []
_timestamps = []
_start_time = None

_last_disk_io = None
_last_net_io = None

def _monitor_loop(interval=1.0):
    global _monitoring_active, _cpu_data, _mem_data, _disk_data, _net_data, _thread_data, _timestamps
    global _last_disk_io, _last_net_io
    
    while _monitoring_active:
        try:
            current_time = time.time()
            elapsed = current_time - _start_time
            
            # CPU & Mem
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            threads = threading.active_count()
            
            # Disk IO
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io and _last_disk_io:
                    disk_bytes_per_sec = ((disk_io.read_bytes + disk_io.write_bytes) - (_last_disk_io.read_bytes + _last_disk_io.write_bytes)) / interval
                else:
                    disk_bytes_per_sec = 0
                _last_disk_io = disk_io
            except Exception:
                disk_bytes_per_sec = 0
            disk_val = disk_bytes_per_sec / (1024*1024)
            
            # Net IO
            try:
                net_io = psutil.net_io_counters()
                if net_io and _last_net_io:
                    net_bytes_per_sec = ((net_io.bytes_sent + net_io.bytes_recv) - (_last_net_io.bytes_sent + _last_net_io.bytes_recv)) / interval
                else:
                    net_bytes_per_sec = 0
                _last_net_io = net_io
            except Exception:
                net_bytes_per_sec = 0
            net_val = net_bytes_per_sec / (1024*1024)
            
            # Append all at once
            _cpu_data.append(cpu)
            _mem_data.append(mem)
            _thread_data.append(threads)
            _disk_data.append(disk_val)
            _net_data.append(net_val)
            _timestamps.append(elapsed)
        except Exception as e:
            logger.debug(f"Monitor loop error: {e}")
            
        time.sleep(interval)

def start_monitor(interval=1.0):
    global _monitoring_active, _monitor_thread, _cpu_data, _mem_data, _disk_data, _net_data, _thread_data, _timestamps, _start_time
    global _last_disk_io, _last_net_io
    
    logger.info("Starting background Resource monitoring...")
    _cpu_data.clear()
    _mem_data.clear()
    _disk_data.clear()
    _net_data.clear()
    _thread_data.clear()
    _timestamps.clear()
    
    try:
        _last_disk_io = psutil.disk_io_counters()
    except Exception:
        _last_disk_io = None
        
    try:
        _last_net_io = psutil.net_io_counters()
    except Exception:
        _last_net_io = None
    
    _monitoring_active = True
    _start_time = time.time()
    
    psutil.cpu_percent(interval=None) # init
    
    _monitor_thread = threading.Thread(target=_monitor_loop, args=(interval,), daemon=True)
    _monitor_thread.start()

def stop_monitor():
    global _monitoring_active, _monitor_thread
    logger.info("Stopping Resource monitoring...")
    _monitoring_active = False
    if _monitor_thread:
        _monitor_thread.join()
        
    return process_results()

def process_results():
    if not _cpu_data:
        return {}
        
    # Generate Charts
    utils.generate_line_chart(_timestamps, _cpu_data, "CPU Utilization Over Time", "Time (s)", "CPU Usage (%)", "cpu_usage_graph.png")
    utils.generate_line_chart(_timestamps, _mem_data, "Memory Utilization Over Time", "Time (s)", "Memory Usage (%)", "memory_usage_graph.png")
    utils.generate_line_chart(_timestamps, _disk_data, "Disk I/O Over Time", "Time (s)", "Disk I/O (MB/s)", "disk_io_graph.png")
    utils.generate_line_chart(_timestamps, _net_data, "Network I/O Over Time", "Time (s)", "Network I/O (MB/s)", "network_io_graph.png")
    
    # Save Raw CSV
    raw_rows = []
    min_len = min(len(_timestamps), len(_cpu_data), len(_mem_data), len(_thread_data), len(_disk_data), len(_net_data))
    for i in range(min_len):
        raw_rows.append([_timestamps[i], _cpu_data[i], _mem_data[i], _thread_data[i], _disk_data[i], _net_data[i]])
    utils.save_csv(["Time_s", "CPU_Percent", "Memory_Percent", "Thread_Count", "Disk_MB_s", "Net_MB_s"], raw_rows, "cpu_memory_raw.csv", is_raw=True)
    
    return {
        "cpu_avg": sum(_cpu_data) / len(_cpu_data) if _cpu_data else 0,
        "cpu_max": max(_cpu_data) if _cpu_data else 0,
        "mem_avg": sum(_mem_data) / len(_mem_data) if _mem_data else 0,
        "mem_max": max(_mem_data) if _mem_data else 0,
        "disk_io_avg_mb_s": sum(_disk_data) / len(_disk_data) if _disk_data else 0,
        "net_io_avg_mb_s": sum(_net_data) / len(_net_data) if _net_data else 0,
        "thread_count_avg": sum(_thread_data) / len(_thread_data) if _thread_data else 0
    }

def run():
    logger.info("Running standalone CPU/Memory test for 10 seconds...")
    start_monitor(1.0)
    time.sleep(10)
    return stop_monitor()
