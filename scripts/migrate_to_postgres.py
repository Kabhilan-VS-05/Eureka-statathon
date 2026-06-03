import json
import os
import re
import sqlite3
import sys

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

import db_store


CSV_PATH = os.path.join(PROJECT_DIR, "data", "raw", "data_with_descriptions.csv")
PROMPT_HISTORY_PATH = os.path.join(PROJECT_DIR, "data", "processed", "prompt_history.json")
ADMIN_DB_PATH = os.path.join(PROJECT_DIR, "data", "admin.db")
MODEL_NAME = "all-MiniLM-L6-v2"


def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def build_documents_and_metadata(rows):
    documents = []
    metadata = []
    for idx, row in enumerate(rows):
        row_id = int(row.get("_row_id") or idx)
        doc = f"""
Occupation Title: {safe_text(row.get('Occupational Title'))}
NCO 2015 Code: {safe_text(row.get('NCO 2015'))}

Hierarchy:
Division: {safe_text(row.get('Division'))}
Sub Division: {safe_text(row.get('Sub Division'))}
Group: {safe_text(row.get('Group'))}
Family: {safe_text(row.get('Family'))}

Occupation Description:
{safe_text(row.get('Occupation Description'))}

Family Description:
{safe_text(row.get('Family Description'))}

Group Description:
{safe_text(row.get('Group Description'))}
""".strip()
        documents.append(doc)
        metadata.append({
            "row_id": row_id,
            "nco_2015": safe_text(row.get("NCO 2015")),
            "occupation_title": safe_text(row.get("Occupational Title")),
        })
    return documents, metadata


def build_graph(documents, metadata):
    graph = {}
    for idx, item in enumerate(metadata):
        code = item["nco_2015"]
        desc = documents[idx].lower() if idx < len(documents) else ""
        words = re.findall(r"\b[a-z]{3,}\b", desc)
        keywords = list(set(words))
        sector = "unknown"
        if "division:" in desc:
            for line in desc.split("\n"):
                if line.strip().startswith("division:"):
                    sector = line.split(":", 1)[1].strip().title()
                    break
        graph[code] = {"sector": sector, "keywords": keywords}
    return graph


def import_admin_settings():
    if not os.path.exists(ADMIN_DB_PATH):
        return
    conn = sqlite3.connect(ADMIN_DB_PATH)
    try:
        cur = conn.execute("SELECT key, value FROM admin_settings")
        for key, value in cur.fetchall():
            db_store.set_admin_setting(key, value)
    except sqlite3.Error:
        return
    finally:
        conn.close()


def rebuild_search_assets():
    _, rows = db_store.load_csv_rows()
    documents, metadata = build_documents_and_metadata(rows)
    db_store.save_search_documents(documents, metadata)

    graph = build_graph(documents, metadata)
    db_store.save_graph(graph)

    print("Loading SBERT model...")
    model = SentenceTransformer(MODEL_NAME)
    print("Generating embeddings...")
    embeddings = model.encode(
        documents,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    db_store.save_embeddings(embeddings)

    print("Building FAISS index...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    serialized_index = faiss.serialize_index(index)
    db_store.save_asset("nco_faiss.index", bytes(serialized_index), "application/x-faiss")


def main():
    print("Initializing PostgreSQL schema...")
    db_store.init_db()

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing source CSV: {CSV_PATH}")

    print("Importing occupations from CSV...")
    db_store.replace_occupations_from_csv(CSV_PATH)

    print("Importing prompt history JSON...")
    db_store.replace_prompt_history_from_json(PROMPT_HISTORY_PATH)

    print("Importing admin settings from SQLite...")
    import_admin_settings()

    print("Building PostgreSQL-backed search assets...")
    rebuild_search_assets()

    print("Migration complete.")
    print(f"Database URL: {db_store.DATABASE_URL}")


if __name__ == "__main__":
    main()
