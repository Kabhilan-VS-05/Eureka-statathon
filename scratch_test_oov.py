import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

# Add project root to sys.path
PROJECT_ROOT = r"d:\The Project\statathon1.1"
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.oov_handler import oov_handler

print("=== Testing Layer 1 (Fast Track / Known Brands) ===")
query1 = "i traveled in rapido"
res1 = oov_handler.process_query(query1)
print(f"Input: {query1}")
print(f"Output: {res1}\n")

print("=== Testing Layer 2 (AI Fallback / Unknown Brands) ===")
# Suppose a new company 'zepto' is used but we didn't add it to our dictionary
# (wait, zepto IS in our dictionary. Let's use 'flybike')
query2 = "i delivered food using flybike"
res2 = oov_handler.process_query(query2)
print(f"Input: {query2}")
print(f"Output: {res2}\n")

query3 = "i fixed my sink with magictools"
res3 = oov_handler.process_query(query3)
print(f"Input: {query3}")
print(f"Output: {res3}\n")
