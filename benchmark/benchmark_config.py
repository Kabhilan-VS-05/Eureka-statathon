import os

# Base Configuration
TARGET = os.getenv("BENCHMARK_TARGET", "Local")
# Change this to your AWS EC2 public IP or domain when benchmarking remotely
BASE_URL = os.getenv("BENCHMARK_BASE_URL", "http://127.0.0.1:5000")

# Benchmark Metadata
BENCHMARK_VERSION = "2.0.0"

# API Endpoints
SEARCH_API = f"{BASE_URL}/api/search"
ADMIN_API = f"{BASE_URL}/admin"
TRANSLATE_API = f"{BASE_URL}/api/translate"

# Database Configuration (for raw DB latency tests)
# Default is the local Postgres instance used by the app
DB_URI = os.getenv("BENCHMARK_DB_URI", "postgresql://postgres:postgres@localhost:5432/statathon_db")

# Admin Credentials
ADMIN_PASSWORD = os.getenv("BENCHMARK_ADMIN_PASSWORD", "admin123")

# Benchmark Execution Settings
WARMUP_ITERATIONS = int(os.getenv("BENCHMARK_WARMUP", 15))
ITERATIONS = int(os.getenv("BENCHMARK_ITERATIONS", 100))
CONCURRENT_USERS_LEVELS = [1, 5, 10, 25, 50, 100]

# Stress Test Settings
STRESS_START_RPS = 10
STRESS_MAX_RPS = 500
STRESS_STEP_RPS = 25

# Endurance Test Settings
ENDURANCE_DURATION_MINUTES = int(os.getenv("BENCHMARK_ENDURANCE_MINS", 60))

# Sample Queries for Benchmarking
SAMPLE_QUERIES = [
    "Software Engineer",
    "Data Scientist",
    "Nurse",
    "Teacher",
    "Mechanic",
    "Chef",
    "Pilot",
    "Electrician",
    "Plumber",
    "Designer"
]

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
GRAPHS_DIR = os.path.join(REPORTS_DIR, "graphs")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
