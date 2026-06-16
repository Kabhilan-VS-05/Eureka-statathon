import argparse
import sys
import os

# Add the benchmark directory to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import benchmark_runner

def main():
    parser = argparse.ArgumentParser(description="AI Semantic Search NCO - Local Benchmarking Framework")
    parser.add_argument(
        "--test", 
        type=str, 
        default="all", 
        help="Specify the test suite to run (e.g., 'latency', 'stress', 'all')"
    )
    
    args = parser.parse_args()
    
    if args.test == "all":
        benchmark_runner.run_all_tests()
    else:
        test_module = f"{args.test}_test" if not args.test.endswith("_test") else args.test
        if test_module == "system_info_test":
            test_module = "system_info" # exception
        benchmark_runner.run_specific_test(test_module)

if __name__ == "__main__":
    main()
