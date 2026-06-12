# PROJECT_DOCUMENTATION.md

## 1) Project Overview
This project is an AI-assisted **NCO occupation search and management system** built with Flask.

Primary goals:
- Map free-text job queries to **NCO 2015** occupations using semantic retrieval.
- Support multilingual input via translation.
- Provide an admin dashboard for analytics and controlled CRUD over occupation data.

Core runtime entrypoint:
- `app.py`

Current runtime mode:
- Flask dev server on port `5000` (`debug=True` in `app.py`).

---

## 2) Tech Stack
- Backend: Python, Flask
- Retrieval/ML: `sentence-transformers` (`BAAI/bge-small-en-v1.5`), `faiss-cpu`, `numpy`
- Data utilities: `pandas`, `csv`, `json`
- Translation + language detection: `requests`, `langdetect`
- Storage: PostgreSQL for occupations, admin settings/password hash, prompt history, semantic documents, graph data, embeddings, and serialized FAISS index bytes
- Frontend: HTML/CSS/Vanilla JS + Bootstrap + Chart.js

Dependencies declared in `requirements.txt`:
- `pandas`
- `numpy`
- `flask`
- `sentence-transformers`
- `faiss-cpu`
- `langdetect`
- `requests`

---

## 3) Repository Structure (Functional)
- `app.py`: Main Flask app, API routes, admin validation, data mutation, search asset rebuilds
- `database/db_store.py`: PostgreSQL schema and storage helpers
- `config/wsgi.py`: Production WSGI entry point
- `config/gunicorn.conf.py`: Production web server configuration
- `scripts/migrate_to_postgres.py`: one-time importer from the previous CSV/JSON/SQLite files into PostgreSQL
- `scripts/legacy_pipeline/`: Legacy standalone scripts for generating embeddings and graphs (no longer used by runtime)
- `templates/`: HTML views for user and admin
- `static/`: Frontend assets (CSS, JS)
- `utils/`: Core helper services including `searchapp.py`, `dynamic_prompts.py`, `translation_service.py`, `ip_location.py`, and `nco_prompts.py`
- `data/raw/nco_dataset_v6_final.csv`: previous import source for migration
- `data/processed/`: previous JSON sources for migration
- `tests/`: Project tests directory

---

## 4) Data Model and Artifacts
### Primary source-of-truth data
- PostgreSQL table: `occupations`
- Previous CSV import source: `data/raw/nco_dataset_v6_final.csv`
- Important columns used:
  - `S No`
  - `Occupational Title`
  - `NCO 2015`
  - `NCO 2004`
  - `Division`
  - `Sub Division`
  - `Group`
  - `Family`
  - `Division Description`
  - `Sub Division Description`
  - `Group Description`
  - `Family Description`
  - `Occupation Description`

### Derived/search artifacts
- PostgreSQL table: `search_documents`
- PostgreSQL table: `nco_graph`
- PostgreSQL table: `search_assets`
  - `nco_embeddings.npy`
  - `nco_faiss.index`

### Operational telemetry
- PostgreSQL table: `prompt_history` (search history, top result details, query metadata)

### Admin settings
- PostgreSQL table: `admin_settings(key TEXT PRIMARY KEY, value TEXT)`
- Password stored as PBKDF2 hash with salt in format: `salt$digest`

---

## 5) Search Architecture
### Runtime module loading
`app.py` imports the core search engine from `utils/searchapp.py` at startup.

### Hybrid scoring in `06_searchapp.py`
For each query:
1. Encode query using SBERT/BGE model (`BAAI/bge-small-en-v1.5`) with query instruction prepended.
2. Search two FAISS indexes:
   - Full occupation document index
   - Title-only index
3. For each candidate, compute:
   - semantic score
   - title score
   - graph overlap score from `nco_graph.json`
4. Blend with weights and boosts:
   - `ALPHA=0.7`, `BETA=0.3`
   - score multiplier and title overlap boost
5. Return top-k sorted by final score.

### NCO direct search mode
`/api/search` supports `search_mode: "nco"` and performs exact normalized match against NCO 2015 codes.

---

## 6) Prompt Intelligence (PIGS)
PIGS logic is exposed from `06_searchapp.py` and used in `app.py` response generation.

It:
- Computes hierarchy-level similarity signals (division/sub-division/group/family context)
- Generates friendly guidance suggestions
- Combines with `utils/dynamic_prompts.py` examples for prompt refinement

Returned in `/api/search` under key `pigs`.

---

## 7) Translation and Language Handling
Implemented in `utils/translation_service.py`.

Flow:
- Detect language confidence using `langdetect`.
- If ambiguous and user language not confirmed, backend sends `language_ambiguity` object.
- Translation strategy:
  - MyMemory first (fast)
  - LibreTranslate fallback endpoints
  - Optional Bhashini integration (credentials required)

`/api/translate` is available for explicit translation calls.

---

## 8) Flask Routes and API Contracts
## UI routes
- `GET /` -> `templates/index.html`
- `GET /admin` -> `templates/admin/dashboard.html`

## Public API
- `POST /api/search`
  - Input: `query`, optional `user_language`, `search_mode`, `top_k`
  - Modes:
    - `general`: semantic search
    - `nco`: exact NCO code lookup
  - Output includes results, translation notice, ambiguity flags, pigs details, counts

- `POST /api/translate`
  - Input: `text`, `source_lang`, `target_lang`, `preferred_service`

- `GET /api/languages`
  - Returns supported language map

## Admin API
- `GET /admin/api/prompt-history?limit=...&occupation_title=...`
- `GET /admin/api/occupations`
- `POST /admin/api/occupations` (password protected)
- `PUT /admin/api/occupations/<row_id>` (password protected)
- `DELETE /admin/api/occupations/<row_id>` (password protected)

Note: All admin charts and metrics are computed dynamically on the frontend via JavaScript (in `admin_dashboard.js`) by consuming the `/admin/api/prompt-history` endpoint. Legacy granular analytics routes have been removed.

---

## 9) Admin Security and Validation (Current State)
## Password protection
- Add, Edit, Delete all require `admin_password`.
- First successful password usage initializes and locks admin password hash in SQLite.

## NCO format rules enforced backend-side
- NCO 2015: `XXXX.XXXX` mandatory on add/edit
- NCO 2004: `XXXX.XX`
  - optional on add
  - required on edit only when existing row already has an NCO 2004 code

## Required field validation
On add/edit:
- Occupation Title
- Division
- Sub Division
- Group
- Family
- Occupation Description

## Duplicate prevention
- Duplicate NCO 2015 blocked
- Duplicate NCO 2004 blocked when provided

## Rebuild behavior after successful mutation
Add/Edit/Delete triggers:
1. CSV rewrite
2. Rebuild semantic documents + metadata
3. Rebuild graph JSON
4. Re-encode embeddings
5. Rebuild FAISS index

This guarantees consistency but can be compute-heavy during frequent edits.

---

## 10) Admin Frontend Behavior (Current)
File: `templates/admin/dashboard.html`

### Analytics tab
- Replaced earlier static analysis blocks with 6 chart cards.
- Uses Chart.js with periodic refresh logic.
- Layout constrained to fixed chart-card heights to prevent runaway page growth.

### Database Management tab
- Occupation table with search/filter/pagination.
- Add/Edit modals include segmented NCO input UX:
  - NCO 2015: first 4 digits + second 4 digits
  - NCO 2004: first 4 digits + second 2 digits
- Edit modal behavior:
  - If row has NCO 2004 code, editable section shown
  - If missing, NCO 2004 edit section hidden/disabled
- Cascading dropdowns implemented:
  - Division -> Sub Division -> Group -> Family

### Validation UX
- Required field checks in JS before submission
- Numeric sanitization and fixed-length checks for segmented NCO parts
- Server errors displayed via notification (includes wrong password/duplicate/format errors)

---

## 11) End-to-End Request Flows
## Search flow
1. User submits query from `index.html`.
2. Backend optionally translates query.
3. Search module returns ranked results.
4. Backend appends prompt history entry.
5. UI renders ranked results + optional PIGS guidance.

## Admin add/edit/delete flow
1. User fills modal and enters admin password.
2. Frontend validates required fields + NCO segmentation.
3. API validates again (authoritative).
4. On success, CSV and search assets rebuild.
5. UI refreshes occupation table and analytics.

---

## 12) Known Gaps / Risks
- Full asset rebuild on each admin mutation may be slow for large datasets.
- `dashboard.html` contains duplicate `refreshAnalytics` function declarations and legacy fragments from earlier iterations; behavior works but file can be refactored for maintainability.
- Some text in templates/scripts appears mojibake-encoded in source comments/labels; functional impact is minimal but readability can improve.
- Flask app currently runs in debug mode by default in `__main__`.

---

## 13) Runbook
## Local setup
1. Create/activate Python env.
2. Create PostgreSQL database and set `DATABASE_URL`, for example:
   ```bash
   set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/statathon_nco
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the one-time migration/import:
   ```bash
   python scripts/migrate_to_postgres.py
   ```
5. Run:
   ```bash
   python app.py
   ```
6. Open:
   - App: `http://127.0.0.1:5000/`
   - Admin: `http://127.0.0.1:5000/admin`

## Rebuild pipeline manually
```bash
python scripts/legacy_pipeline/01_preparation.py
python scripts/legacy_pipeline/05_searchGN.py
python scripts/legacy_pipeline/02_generateEmbedding.py
python scripts/legacy_pipeline/03_build_faiss_index.py
```

---

## 14) Current Status Snapshot
As of latest changes in this workspace:
- Admin analytics redesigned into chart-based real-time dashboard.
- Chart expansion/infinite page growth issue addressed with constrained card/canvas sizing.
- Occupation add/edit module upgraded with:
  - password protection on edit
  - segmented NCO 2015 and NCO 2004 inputs
  - NCO format enforcement
  - duplicate checks
  - required hierarchy validations
  - conditional NCO 2004 edit visibility
- Existing search APIs and core architecture preserved.
- Added a 4-level NCO Search Demand Sunburst Chart (Division, Sub-Division, Group, Family) to the admin dashboard.
- Integrated PIGS v3 (Prompt Intelligence & Guidance System) to use query specificity and result diversity heuristics instead of basic semantic scores.
- Redesigned search flow to use a "title-first, semantic-fill" strategy with instant debounced rendering (no spinner or artificial delays).
- Updated Translation Usage chart to show detailed breakdown by detected language (English, Tamil, Hindi, etc.) instead of a binary state.
- Cleaned up obsolete scratch files and static vocabulary lists.
- Replaced "Zero-Result Queries" analytics metric with an "Avg Match Confidence" heuristic using string similarity.
- Optimized the Sunburst Chart logic to dynamically group microscopic slices into an "Other" category to prevent rendering crashes, and fixed its leaf-node summation calculation.
- Executed a major repository restructuring to achieve a professional standard: merged all scattered documents into `docs/`, relocated deployment configurations to `config/`, relocated the core database interface to `database/db_store.py`, and completely removed unused prototype files (`frontend/`).

---

## 15) Suggested Next Engineering Tasks
1. Refactor `templates/admin/dashboard.html` JS into modular files.
2. Add automated tests for admin API validations and duplicate handling.
3. Move expensive rebuild operations to async/background jobs.
4. Add role-based auth/session guard for `/admin` route.
5. Add structured logging and health-check endpoint.
