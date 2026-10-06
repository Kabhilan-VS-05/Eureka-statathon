import csv
import json
import os
import re

# We use a standard list of English stopwords to filter out noise
STOPWORDS = set([
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will",
    "just", "don", "should", "now", "perform", "performs", "requires", "includes",
    "involves", "workers", "worker", "job", "occupations", "occupation", "related",
    "various", "duties", "tasks", "work", "works"
])

def clean_text(text):
    """Lowercase and extract alphabetical words"""
    if not text:
        return []
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return [w for w in words if w not in STOPWORDS]

def generate_graph(csv_path, output_json_path):
    print(f"Reading dataset from {csv_path}...")
    
    graph_data = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                nco_code = row.get("NCO 2015", "").strip()
                if not nco_code:
                    continue
                    
                title = row.get("Occupational Title", "")
                division = row.get("Division", "Unknown Sector")
                description = row.get("Occupation Description", "")
                
                # Combine title and description for keyword extraction
                combined_text = f"{title} {description}"
                
                # Extract clean, unique keywords
                keywords = list(set(clean_text(combined_text)))
                
                # We want to ensure keywords from the Title are heavily prioritized/always present
                title_keywords = clean_text(title)
                for tk in title_keywords:
                    if tk not in keywords:
                        keywords.append(tk)
                
                graph_data[nco_code] = {
                    "sector": division,
                    "keywords": keywords
                }
                
        print(f"Successfully processed {len(graph_data)} occupations.")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2)
            
        print(f"Knowledge Graph successfully generated at: {output_json_path}")
        
    except Exception as e:
        print(f"Error generating graph: {e}")

if __name__ == "__main__":
    # Paths relative to the project root
    CSV_PATH = os.path.join("data", "raw", "nco_dataset_v6_final.csv")
    OUTPUT_JSON_PATH = os.path.join("data", "processed", "nco_graph.json")
    
    generate_graph(CSV_PATH, OUTPUT_JSON_PATH)
