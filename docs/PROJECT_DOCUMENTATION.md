# PROJECT_DOCUMENTATION.md

> Last updated: 2026-06-18

---

## 1. Project Overview

An AI-assisted **NCO occupation search and management system** built with Flask and deployed on AWS.

Primary goals:
- Map free-text job queries to **NCO 2015** occupations using semantic retrieval.
- Support multilingual input (any Indian language) via automatic translation.
- Provide an admin dashboard for real-time analytics, state-wise demand analysis, and controlled CRUD over occupation data.

Runtime entrypoint: `app.py`

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3.1 |
| ML / Retrieval | `sentence-transformers` (`BAAI/bge-small-en-v1.5`), `faiss-cpu`, `numpy` |
| Database | PostgreSQL (via `psycopg2-binary`) |
| Auth | Werkzeug `generate_password_hash` / `check_password_hash` (PBKDF2-SHA256) |
| Translation | `deep-translator`, `langdetect`, `requests` |
| IP Geolocation | `ip-api.com` (free tier, no API key) |
| Compression | `flask-compress` (gzip all text/JSON responses) |
| Frontend | Vanilla JS + Bootstrap 5.3 + Chart.js 4.4 + D3 v7 |
| Web server | Gunicorn (production), Flask dev server (local) |

---

## 3. Repository Structure

```
app.py                          Main Flask app — routes, auth, search, analytics
requirements.txt                Pinned dependencies
database/
  db_store.py                   All PostgreSQL schema creation and helpers
utils/
  searchapp.py                  SBERT + FAISS hybrid search engine (in-memory)
  synonym_bank.py               Layer 1 — dataset-derived synonym loader (PG + CSV)
  oov_handler.py                Layer 2 — curated OOV expansion loader (PG + CSV)
  spell_correction.py           Layer 3 — conservative dataset-driven spell corrector
  dynamic_prompts.py            PIGS v2/v3 prompt intelligence system
  translation_service.py        Multi-service translation (MyMemory, LibreTranslate)
  ip_location.py                IP → city/state/country via ip-api.com (cached)
  nco_prompts.py                NCO query prompt templates
templates/
  index.html                    Public search page
  admin/
    login.html                  Admin login page (government-themed)
    dashboard.html              Admin dashboard (3 tabs)
static/
  gov-style.css                 Public page styles
  admin_dashboard.css           Admin dashboard styles
  admin_dashboard.js            Admin dashboard JS (all tab logic)
scripts/
  migrate_to_postgres.py        One-time CSV → PostgreSQL migration (also builds Layers 1 & 2)
  generate_synonym_bank.py      Layer 1 — build dataset-derived synonym bank → CSV + PostgreSQL
  generate_oov_dictionary.py    Layer 2 — build curated OOV dictionary → CSV + PostgreSQL
  set_admin_password.py         Interactive admin password manager
  import_prompt_history.py      Bulk import prompt_history from JSON file
docs/
  PROJECT_DOCUMENTATION.md      This file
  AWS_TROUBLESHOOTING_GUIDE.md  AWS deployment troubleshooting
  GITHUB_AWS_WORKFLOW.md        GitHub → AWS CI/CD workflow
config/
  wsgi.py                       Production WSGI entry point
  gunicorn.conf.py              Gunicorn configuration
data/raw/
  nco_dataset_v6_final.csv      Source CSV for migration (not runtime)
data/processed/
  synonym_bank.csv              Layer 1 editable artifact (word,synonyms)
  oov_dictionary.csv            Layer 2 editable artifact (term,concepts)
```

---

## 4. PostgreSQL Schema

### `occupations` — master occupation data
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| s_no | TEXT | |
| occupation_title | TEXT | |
| nco_2015 | TEXT UNIQUE | Format: `XXXX.XXXX` |
| nco_2004 | TEXT | Format: `XXXX.XX` (optional) |
| division | TEXT | |
| sub_division | TEXT | |
| group | TEXT | |
| family | TEXT | |
| occupation_description | TEXT | |
| family_description | TEXT | |
| group_description | TEXT | |

### `search_documents` — FAISS index source text
| Column | Type | Notes |
|---|---|---|
| row_id | INT PK → occupations.id | |
| document | TEXT | Text used to build embeddings |
| metadata | JSONB | occupation_title, nco_2015, row_id |

### `search_assets` — serialized binary artifacts
| Column | Type |
|---|---|
| name | TEXT PK |
| data | BYTEA |

Stores: `nco_faiss.index`, `nco_embeddings.npy`

### `nco_graph` — keyword graph for overlap scoring
| Column | Type |
|---|---|
| nco_code | TEXT PK |
| data | JSONB |

Each entry: `{"keywords": [...], "related": [...]}`

### `synonym_bank` — Layer 1 dataset-derived synonyms
| Column | Type | Notes |
|---|---|---|
| word | TEXT PK | meaningful term from the NCO dataset |
| synonyms | JSONB | ranked list of co-occurring synonyms |

Built by `scripts/generate_synonym_bank.py` from NCO family co-occurrence (no manual lists). Mirrored to `data/processed/synonym_bank.csv` for editing/audit. PostgreSQL is the runtime source of truth; CSV is the fallback.

### `oov_dictionary` — Layer 2 curated OOV terms
| Column | Type | Notes |
|---|---|---|
| term | TEXT PK | brand / vernacular / abbreviation (single- or multi-word) |
| concepts | JSONB | standard-English concepts the engine understands |

Built by `scripts/generate_oov_dictionary.py` from a small curated seed; the generator auto-drops any single-word key already in the NCO dataset so the dictionary never duplicates dataset knowledge. Mirrored to `data/processed/oov_dictionary.csv`. PostgreSQL primary, CSV fallback.

### `prompt_history` — search telemetry
| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| ts | TIMESTAMPTZ | Query timestamp |
| query | TEXT | Raw user query |
| translated_query | TEXT | Query after translation |
| was_translated | BOOL | |
| occupation_title | TEXT | Top result title |
| nco_code | TEXT | Top result NCO code |
| top_k | INT | Requested result count |
| returned_count | INT | Actual result count |
| client_ip | TEXT | |
| geo_city | TEXT | From ip-api.com lookup |
| geo_state | TEXT | Indian state name |
| geo_country | TEXT | Country name |
| raw | JSONB | Full result details |

### `admin_users` — authentication
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| username | VARCHAR(64) UNIQUE | Always `"admin"` |
| password_hash | TEXT | Werkzeug PBKDF2-SHA256 hash |
| created_at | TIMESTAMPTZ | |

### `admin_settings` — key-value config store (non-auth)
| Column | Type |
|---|---|
| key | TEXT PK |
| value | TEXT |

---

## 5. Admin Authentication

All authentication is stored in the `admin_users` PostgreSQL table. No `.env` variables or hardcoded passwords are used.

### First-run bootstrap
On startup, `_ensure_admin_account()` in `app.py` checks if `admin_users` is empty. If so:
1. Generates a random password via `secrets.token_urlsafe(16)`
2. Hashes it with `werkzeug.security.generate_password_hash` (PBKDF2-SHA256)
3. Stores in `admin_users`
4. Prints the plaintext password once to the server console — it is never stored or logged again

### Login / logout
- `GET /admin/login` — renders login page
- `POST /admin/login` — verifies password, sets `session['admin_authenticated'] = True`
- `GET /admin/logout` — clears session, redirects to login

### Route protection
Two decorators protect admin routes:
- `@admin_required` — for HTML page routes: redirects to `/admin/login` if not authenticated
- `@admin_api_required` — for `/admin/api/*` routes: returns `401 JSON` if not authenticated

The admin dashboard JS has a global `fetch` interceptor that catches 401 responses and redirects to the login page automatically.

### Password management
Run from the project root:
```bash
python scripts/set_admin_password.py
```
Options:
1. Change password (prompts for new password twice, minimum 8 chars)
2. Reset (delete + recreate with a new random password printed to console)

---

## 6. Search Architecture

### Module loading
`utils/searchapp.py` is imported once at startup (`import utils.searchapp as search_module`). All data is loaded into RAM:
- FAISS index (deserialized from `search_assets`)
- Title FAISS index (built in-memory from occupation titles)
- SBERT model
- Metadata list
- Graph network dict
- Job details dict (descriptions, hierarchy)
- Description word sets (pre-built for fast keyword matching)

### Query understanding pipeline (Layers 1–3)

Before retrieval, every query passes through three dataset-driven layers
(`searchapp.search()`):

1. **Layer 2 — OOV expansion** (`utils/oov_handler.py`): appends standard-English
   concepts for recognised brands / vernacular / abbreviations. Greedy
   longest-match n-gram scan, so multi-word keys (`"ward boy"`, `"asha worker"`,
   `"data entry operator"`) fire. Original wording preserved.
2. **Layer 3 — conservative spell correction** (`utils/spell_correction.py`):
   corrects only genuine non-words against the dataset vocabulary, within a small
   edit distance. Valid English words (star, chair) and protected OOV/brand terms
   are never altered — *an unknown word is not assumed to be a typo*. No hardcoded
   typo maps, no aggressive fuzzy fallback.
3. **Layer 1 — synonym expansion** (`utils/synonym_bank.py`): applied at scoring
   time inside the graph/description scorers (not as a query-string mutation, to
   avoid diluting the SBERT vector). Synonyms are dataset-derived from NCO family
   co-occurrence — no manual lists.

Order: OOV expand → conservative spell → (synonyms at scoring). Layers 1 & 2 are
loaded from PostgreSQL (`synonym_bank` / `oov_dictionary` tables) with CSV
fallback, and re-seeded on `reload_from_db()`.

### Hybrid search algorithm (`utils/searchapp.py`)

**Constants:**
```
ALPHA = 0.65    # semantic SBERT score weight
BETA  = 0.15    # graph keyword coverage weight
GAMMA = 0.20    # description keyword match weight
CANDIDATE_K = 150
TITLE_CANDIDATE_K = 100
```

**Step 1 — Substring title match**
- Exact substring matches against occupation titles
- Sorted: exact → starts-with → substring
- If `len(matches) >= top_k`, return immediately (no SBERT needed)

**Step 2 — Semantic search**
1. `_preprocess_query(query)` strips first-person filler (`"I am a"`, `"I work as"`, `"My job is"`) to expose the core occupation concept
2. `embed_query()` encodes with BGE instruction prefix; appends `" occupation"` for single-word queries
3. FAISS search on full document index → semantic scores
4. FAISS search on title index → title scores
5. For each candidate:
   - `compute_graph_score()` — fraction of **query** words (minus stopwords, plus Layer-1 synonyms) covered by the occupation's keyword graph
   - `compute_description_score()` — fraction of query words found in the occupation title + description (exact / synonym / prefix credit)
   - `combined = ALPHA×semantic + BETA×graph + GAMMA×desc`
   - `final_score = combined_w × combined + title_w × title_score`, with **adaptive title weight** — short queries (≤2 meaningful words): `title_w=0.28`; longer queries: `title_w=0.18`
6. Sort by `(title_match_priority, -final_score)`
7. Merge title matches + semantic candidates (deduplicated by NCO code)

**Search result cache**
- In-memory LRU-style cache keyed on `(translated_query, top_k, filters)`
- TTL: 5 minutes, max 500 entries
- Skips SBERT inference for repeated queries (saves 200–500ms)
- History logging still runs on every request regardless of cache hit

### NCO direct search mode
`search_mode: "nco"` — exact/prefix match against NCO 2015 codes, no SBERT.

### Reload after admin mutations
`search_module.reload_from_db()` is called after every successful add/edit/delete to refresh all in-memory state from PostgreSQL.

---

## 7. IP Geolocation (`utils/ip_location.py`)

Uses `ip-api.com` (free, 1000 req/min, no API key):
- Private/loopback IPs (`127.0.0.1`, `192.168.x.x`, etc.) → `{"city": "", "state": "", "country": "India"}`
- Public IPs → `{"city": "...", "state": "<Indian state>", "country": "India"}` or foreign country
- Results cached in-memory per IP (no expiry, process lifetime)
- Timeout: 1 second (never blocks a search if slow)

Stored in `prompt_history.geo_state/geo_city/geo_country` after every search.

---

## 8. Translation and Language Handling

`utils/translation_service.py`

Flow:
1. Detect language with `langdetect`
2. If user explicitly selected a non-English language (`user_language` param), translate using `deep-translator`
3. Translation notice included in API response if translation occurred

Supported services: MyMemory → LibreTranslate (fallback)

---

## 9. Flask Routes

### Public routes
| Method | Route | Description |
|---|---|---|
| GET | `/` | Search page |
| POST | `/api/search` | Semantic / NCO search |
| POST | `/api/translate` | Explicit translation |
| GET | `/api/languages` | Supported language map |
| GET | `/favicon.ico` | Returns 204 (no content) |
| GET | `/.well-known/appspecific/com.chrome.devtools.json` | Returns 204 (suppresses Chrome DevTools 404 noise) |

### Admin UI routes (session-protected)
| Method | Route | Description |
|---|---|---|
| GET | `/admin/login` | Login page |
| POST | `/admin/login` | Authenticate |
| GET | `/admin/logout` | Log out |
| GET | `/admin` | Dashboard (3 tabs) |

### Admin API routes (`@admin_api_required`)
| Method | Route | Description |
|---|---|---|
| GET | `/admin/api/prompt-history` | Search history (`?limit=5000&occupation_title=`) |
| GET | `/admin/api/occupations` | All occupations |
| POST | `/admin/api/occupations` | Add occupation |
| PUT | `/admin/api/occupations/<row_id>` | Edit occupation |
| DELETE | `/admin/api/occupations/<row_id>` | Delete occupation |
| POST | `/admin/api/import-csv` | Bulk import from CSV |
| GET | `/admin/api/analytics/states` | Search count per Indian state |
| GET | `/admin/api/analytics/states/<state_name>` | State drill-down (occupations + divisions) |
| GET | `/admin/api/analytics/countries` | Search count per non-India country |
| GET | `/admin/api/analytics/search-trend` | Daily search trend (last 7 days) |
| GET | `/admin/api/analytics/top-queries` | Top 10 repeated queries |

---

## 10. Admin Dashboard (3 Tabs)

### Analytics tab
- Metric tiles: Total Searches, Unique Queries, Translation Rate, Active Occupations
- Charts: Search Trend (7-day), Top Occupations, Translation Language Breakdown
- Full search history table with location column (city + state from geolocation)
- Auto-refresh every **5 minutes** (was 90 seconds — reduced for low-end systems)
- Occupation filter dropdown in history table

### Database Management tab
- Paginated occupation table (40 per page) with search
- Add / Edit / Delete with NCO format validation:
  - NCO 2015: `XXXX.XXXX`
  - NCO 2004: `XXXX.XX`
- Password verified on every write operation
- Cascading division → sub-division → group → family dropdowns
- Import CSV bulk-load option
- Export as CSV / Excel

### State-wise Demand tab
- Interactive India map (D3 v7 + GeoJSON from geohacker/india)
- Heat map colored by search count per state (blue gradient)
- Click any state to see: top 10 occupations, division breakdown chart
- Metric strip: Total Searches (India), Active States, Top State, Top Occupation
- **Only India searches shown** — non-India (VPN etc.) are filtered by `geo_country = 'India'`
- International Searches box below the map: shows search counts per non-India country with progress bars
- GeoJSON is cached in `window.__ncoIndiaGeoData` after first load (no re-fetch on tab switch)
- Map works only with real public IPs in production; local `127.0.0.1` produces no geo data

---

## 11. Security

| Feature | Implementation |
|---|---|
| Admin password | Werkzeug PBKDF2-SHA256, stored in PostgreSQL `admin_users`, never in `.env` or source |
| Session auth | Flask server-side sessions with `SECRET_KEY` env var |
| Password hashing | Timing-safe via `check_password_hash` (uses `hmac.compare_digest` internally) |
| First-run seed | `secrets.token_urlsafe(16)` printed once to console |
| Security headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` |
| Static asset caching | Versioned files served with `Cache-Control: public, max-age=31536000, immutable` |
| No hardcoded passwords | No passwords in JS, templates, or `.env` |

---

## 12. Performance Optimizations

### Backend
- **Flask-Compress** — all text/JSON responses automatically gzip'd (~70–80% size reduction)
- **Search result cache** — in-memory, 5-minute TTL, 500-entry max; skips SBERT for repeated queries
- **FAISS in-memory** — zero DB hits per search after startup; only `prompt_history` insert per query
- **ip-api.com in-memory cache** — one geolocation lookup per unique IP

### Frontend (search page)
- **AbortController** — cancels in-flight requests when user types faster; no stale-response overwrites
- **Debounce: 400ms** — reduced from 250ms; fewer server hits while typing
- **System font stack** — no Google Fonts CDN; text renders instantly on any network
- **Paginated directory** — 40 rows rendered at a time, "Show More" on demand

### Frontend (admin dashboard)
- **Deferred scripts** — Bootstrap, Chart.js, D3 all load with `defer` (non-blocking)
- **5-minute auto-refresh** — analytics polling reduced from 90s
- **D3 path cache** — map SVG paths pre-computed once; hover/click don't re-project
- **rAF-throttled tooltip** — map tooltip updates at most once per animation frame
- **Chart.js in-place update** — existing chart instances updated via `.data =` + `.update()`, never recreated
- **GeoJSON cache** — India GeoJSON fetched once, cached in `window.__ncoIndiaGeoData`

---

## 13. Search Accuracy Details

### Graph score (fixed)
Old formula divided by `len(keywords)` (occupation's keyword count, often 50+), making occupations with many keywords score near zero. Fixed to divide by `len(query_words)` — measures what fraction of the query is covered by the occupation.

### Description score (new signal)
After SBERT scoring, query words are matched against the pre-built word sets from `occupation_description + family_description + group_description`. Gives a lightweight keyword signal independent of SBERT embeddings.

### Query preprocessing
Strips first-person filler before embedding:
- `"I am a farmer"` → embeds as `"farmer"`
- `"I am a professor in a private college"` → `"professor in a private college"`
- `"I grow banana trees"` → `"grow banana trees"` (action verbs kept)

### Stopwords
Common English words (`i`, `am`, `the`, `a`, `and`, etc.) are stripped from graph and description scoring to prevent false matches.

### Synonym / OOV / spell architecture (3 layers)
The query-understanding stack is dataset-driven, with minimal manual curation
(target split ≈ 70% dataset / 20% OOV / 10% spell). **CSV is the editable
artifact; PostgreSQL is the runtime source of truth** (loaders fall back to CSV
if the DB is empty/unavailable).

- **Layer 1 — Dataset-derived synonyms** (`generate_synonym_bank.py` →
  `synonym_bank` table / `synonym_bank.csv`). Synonyms come from NCO **Family
  co-occurrence** with field-weighted TF-IDF (Title=5, Family/Group name=3,
  Occupation Description=1; Family/Group *descriptions excluded* as boilerplate).
  `MIN_CLUSTER_SALIENCE=3` trims weak cross-links. No manual synonym lists;
  regenerate whenever the dataset changes. (Terms NCO titles differently — e.g.
  Physician vs "doctor" — yield 0 synonyms here and are handled by SBERT instead.)
- **Layer 2 — Curated OOV dictionary** (`generate_oov_dictionary.py` →
  `oov_dictionary` table / `oov_dictionary.csv`). A curated seed of brands,
  Indian vernacular (Hindi + Tamil/Telugu/Kannada/Malayalam/Bengali/Marathi/
  Gujarati/Punjabi), abbreviations, and modern/gig roles. The generator
  **auto-drops any single-word key already in the NCO dataset**, so the file
  never duplicates dataset knowledge. Add terms by editing the `SEED` dict and
  rerunning the script (CSV + DB update together).
- **Layer 3 — Conservative spell correction** (`spell_correction.py`).
  Candidates are built from dataset vocabulary; only genuine non-words are fixed,
  within edit distance ≤ 2 (distance-2 must land on a dataset word). Valid words
  and OOV/brand terms are always preserved. Replaces the old aggressive
  `difflib` cutoff-0.45 fallback that forced gibberish onto vocabulary.

---

## 14. Scripts

### `scripts/migrate_to_postgres.py`
One-time import from CSV/JSON/SQLite into PostgreSQL. Also builds embeddings, FAISS index, graph, and — at the end — runs both Layer 1 and Layer 2 generators so a fresh deploy populates everything in one command.
```bash
python scripts/migrate_to_postgres.py
```

### `scripts/generate_synonym_bank.py` (Layer 1)
Rebuilds the dataset-derived synonym bank from the NCO CSV. Writes `data/processed/synonym_bank.csv` and stores it in the `synonym_bank` PostgreSQL table. Run after any dataset change.
```bash
python scripts/generate_synonym_bank.py
```

### `scripts/generate_oov_dictionary.py` (Layer 2)
Rebuilds the curated OOV dictionary from the `SEED` dict, auto-dropping any term already in the NCO dataset. Writes `data/processed/oov_dictionary.csv` and stores it in the `oov_dictionary` PostgreSQL table. Edit `SEED` + rerun to add brands / vernacular / abbreviations.
```bash
python scripts/generate_oov_dictionary.py
```

### `scripts/set_admin_password.py`
Interactive admin credential manager. Run from project root:
```bash
python scripts/set_admin_password.py
```
Options: change password | reset to new random password

### `scripts/import_prompt_history.py`
Replace the entire `prompt_history` table from a JSON backup file:
```bash
python scripts/import_prompt_history.py "path/to/prompt_history.json"
```
JSON format: array of objects with fields `ts`, `query`, `translated_query`, `was_translated`, `occupation_title`, `nco_code`, `client_ip`.

---

## 15. Local Setup

```bash
# 1. Create PostgreSQL database
# 2. Create .env
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/statathon_nco
SECRET_KEY=your_random_secret_key

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migration (first time only)
python scripts/migrate_to_postgres.py

# 5. Start server
python app.py

# 6. Open
# http://127.0.0.1:5000/       — search page
# http://127.0.0.1:5000/admin  — admin (password printed to console on first run)
```

---

## 16. AWS Deployment Notes

- The app auto-detects proxy IPs via `X-Forwarded-For` header for correct geolocation
- `geo_state` will be blank for all local/dev traffic (`127.0.0.1`) — this is expected
- State-wise map only shows data from production where users have real public IPs
- `SECRET_KEY` env var must be set persistently in AWS so sessions survive restarts
- `FLASK_DEBUG=0` must be set in production (debug defaults off unless env var is `1`/`true`)
- `ASSET_VERSION` env var controls cache busting for static files

See `docs/AWS_TROUBLESHOOTING_GUIDE.md` and `docs/GITHUB_AWS_WORKFLOW.md` for deployment details.

---

## 17. NCO Validation Rules

| Field | Rule |
|---|---|
| NCO 2015 | Required, format `XXXX.XXXX` (4 digits, dot, 4 digits) |
| NCO 2004 | Optional on add; format `XXXX.XX` (4 digits, dot, 2 digits) when provided |
| Occupation Title | Required |
| Division | Required |
| Sub Division | Required |
| Group | Required |
| Family | Required |
| Occupation Description | Required |

Duplicate NCO 2015 and duplicate NCO 2004 (when provided) are both blocked at the DB level.

---

## 18. Known Limitations

- **State map empty locally** — all searches from `127.0.0.1` store empty `geo_state`. Use the SQL snippet in the code review notes to backfill test data manually.
- **GeoJSON state name matching** — `ip-api.com` returns `regionName` which must match the GeoJSON `NAME_1` field exactly. Post-2014 state splits (e.g. Telangana) may not match on older GeoJSON versions.
- **SBERT inference latency** — ~100–500ms depending on server CPU. Cached for repeated queries. First cold query after cache expiry always pays the full cost.
- **Admin sessions not shared** — Flask sessions are in-process memory. Multi-worker Gunicorn deployments need `SESSION_TYPE=sqlalchemy` or a Redis session store for session persistence across workers.
- **No role separation** — single `admin` account only. No multi-user or role-based access.
