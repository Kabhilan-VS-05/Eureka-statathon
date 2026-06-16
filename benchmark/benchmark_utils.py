import os
import json
import csv
import logging
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import benchmark_config as config
import shutil
import subprocess

_current_report_dir = None
_current_graphs_dir = None

def get_report_dirs():
    global _current_report_dir, _current_graphs_dir
    if _current_report_dir is None:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        _current_report_dir = os.path.join(config.REPORTS_DIR, timestamp)
        _current_graphs_dir = os.path.join(_current_report_dir, "graphs")
        os.makedirs(_current_report_dir, exist_ok=True)
        os.makedirs(_current_graphs_dir, exist_ok=True)
    return _current_report_dir, _current_graphs_dir

def copy_to_latest():
    if not _current_report_dir:
        return
    latest_dir = os.path.join(config.REPORTS_DIR, "latest")
    if os.path.exists(latest_dir):
        shutil.rmtree(latest_dir)
    shutil.copytree(_current_report_dir, latest_dir)

def get_git_commit():
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else "Unknown"
    except Exception:
        return "Unknown"

def calculate_score(results):
    # Calculates an overall score out of 100 based on arbitrary but sensible baselines.
    score_components = []
    
    if "latency" in results and "overall_metrics" in results["latency"]:
        avg_lat = results["latency"]["overall_metrics"].get("average", 1000)
        # 100 points if < 50ms, 0 points if > 1000ms
        lat_score = max(0, min(100, 100 - ((avg_lat - 50) / 950 * 100)))
        score_components.append(lat_score)
        
    if "cpu_memory" in results:
        cpu_avg = results["cpu_memory"].get("cpu_avg", 100)
        # 100 points if < 20%, 0 points if > 90%
        cpu_score = max(0, min(100, 100 - ((cpu_avg - 20) / 70 * 100)))
        score_components.append(cpu_score)
        
    if "throughput" in results:
        rps = results["throughput"].get("requests_per_second", 0)
        # 100 points if > 500 RPS, 0 points if 0 RPS
        rps_score = max(0, min(100, (rps / 500) * 100))
        score_components.append(rps_score)
        
    if "fault_tolerance" in results:
        pass_rate = results["fault_tolerance"].get("pass_rate_percent", 0)
        score_components.append(pass_rate)
        
    if not score_components:
        return 0
        
    return sum(score_components) / len(score_components)

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        log_file = os.path.join(config.LOGS_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

def calculate_metrics(latencies):
    if not latencies:
        return {}
    
    return {
        "average": float(np.mean(latencies)),
        "minimum": float(np.min(latencies)),
        "maximum": float(np.max(latencies)),
        "median": float(np.median(latencies)),
        "p95": float(np.percentile(latencies, 95)),
        "p99": float(np.percentile(latencies, 99)),
        "stddev": float(np.std(latencies))
    }

def save_json(data, filename):
    rep_dir, _ = get_report_dirs()
    filepath = os.path.join(rep_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return filepath

def save_csv(headers, rows, filename, is_raw=False):
    if is_raw:
        # Raw files go to logs directory
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        filepath = os.path.join(config.LOGS_DIR, filename)
    else:
        rep_dir, _ = get_report_dirs()
        filepath = os.path.join(rep_dir, filename)
        
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return filepath

MAX_GRAPH_POINTS = 2000

def downsample(data):
    if len(data) <= MAX_GRAPH_POINTS:
        return data
    step = len(data) / MAX_GRAPH_POINTS
    return [data[int(i * step)] for i in range(MAX_GRAPH_POINTS)]

def downsample_xy(x, y):
    if len(x) <= MAX_GRAPH_POINTS:
        return x, y
    step = len(x) / MAX_GRAPH_POINTS
    indices = [int(i * step) for i in range(MAX_GRAPH_POINTS)]
    return [x[i] for i in indices], [y[i] for i in indices]

def generate_line_chart(x_data, y_data, title, xlabel, ylabel, filename):
    logger = logging.getLogger("benchmark_utils")
    if not x_data or not y_data:
        logger.warning(f"Skipping graph '{title}': Empty data.")
        return None
    if len(x_data) != len(y_data):
        logger.warning(f"Skipping graph '{title}': Length mismatch (x={len(x_data)}, y={len(y_data)}).")
        return None
        
    x_data, y_data = downsample_xy(x_data, y_data)
    
    _, graph_dir = get_report_dirs()
    try:
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        ax.plot(x_data, y_data, marker='o', linestyle='-', color='b')
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True)
        
        filepath = os.path.join(graph_dir, filename)
        fig.savefig(filepath)
        plt.close(fig)
        return filepath
    except Exception as e:
        logger.exception(f"Graph generation failed for {title}: {e}")
        return None

def generate_histogram(data, title, xlabel, ylabel, filename):
    logger = logging.getLogger("benchmark_utils")
    if not data:
        logger.warning(f"Skipping graph '{title}': Empty data.")
        return None
        
    data = downsample(data)
    
    _, graph_dir = get_report_dirs()
    try:
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        ax.hist(data, bins=30, color='c', edgecolor='black')
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True)
        
        filepath = os.path.join(graph_dir, filename)
        fig.savefig(filepath)
        plt.close(fig)
        return filepath
    except Exception as e:
        logger.exception(f"Graph generation failed for {title}: {e}")
        return None

def generate_bar_chart(categories, values, title, xlabel, ylabel, filename):
    logger = logging.getLogger("benchmark_utils")
    if not categories or not values:
        logger.warning(f"Skipping graph '{title}': Empty data.")
        return None
    if len(categories) != len(values):
        logger.warning(f"Skipping graph '{title}': Length mismatch.")
        return None
        
    categories, values = downsample_xy(categories, values)
    
    _, graph_dir = get_report_dirs()
    try:
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        ax.bar(categories, values, color='g')
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(axis='y')
        
        filepath = os.path.join(graph_dir, filename)
        fig.savefig(filepath)
        plt.close(fig)
        return filepath
    except Exception as e:
        logger.exception(f"Graph generation failed for {title}: {e}")
        return None
