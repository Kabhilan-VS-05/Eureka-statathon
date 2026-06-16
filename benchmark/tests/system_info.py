import platform
import psutil
from datetime import datetime
import subprocess
import benchmark_utils as utils

logger = utils.setup_logger("system_info")

def get_software_version(cmd, name):
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        output = result.stdout.strip() or result.stderr.strip()
        # grab the first line if multiple
        if output:
            return output.split('\n')[0]
        return "Unknown"
    except Exception as e:
        logger.debug(f"Could not get version for {name}: {e}")
        return "Not Installed"

def run():
    logger.info("Collecting system information...")
    
    info = {}
    info["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    info["OS"] = f"{platform.system()} {platform.release()} ({platform.version()})"
    info["CPU Architecture"] = platform.machine()
    info["CPU Name"] = platform.processor()
    info["Physical Cores"] = psutil.cpu_count(logical=False)
    info["Total Cores (Logical)"] = psutil.cpu_count(logical=True)
    
    ram = psutil.virtual_memory()
    info["Total RAM"] = f"{ram.total / (1024**3):.2f} GB"
    
    # Python Version
    info["Python Version"] = platform.python_version()
    
    # GPU check
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            info["GPU"] = gpus[0].name
        else:
            info["GPU"] = "None Detected"
    except ImportError:
        info["GPU"] = "GPUtil not installed. Cannot detect."
        
    # Software versions
    info["PostgreSQL Version"] = get_software_version(["psql", "--version"], "PostgreSQL")
    info["Flask Version"] = get_software_version(["flask", "--version"], "Flask")
    
    # Try to get pip module versions
    try:
        import faiss
        info["FAISS Version"] = getattr(faiss, "__version__", "Installed")
    except ImportError:
        info["FAISS Version"] = "Not Installed"
        
    try:
        import sentence_transformers
        info["SentenceTransformer Version"] = getattr(sentence_transformers, "__version__", "Installed")
    except ImportError:
        info["SentenceTransformer Version"] = "Not Installed"
        
    # Dataset size could be dynamically queried if db connection is established
    # For now it's static
    info["Dataset Size"] = "Dynamic (Run Database tests for accurate count)"
    
    logger.info("System information collected successfully.")
    return info
