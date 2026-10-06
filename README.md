# Eureka Statathon — Intelligent Multilingual Search & Analytics Engine

**Eureka Statathon** is an AI-enhanced enterprise search, query expansion, and analytical knowledge platform designed for public statistical datasets, government documentation, and multi-lingual citizen inquiries. It integrates phonetic transliteration, domain-specific spelling corrections, Out-Of-Vocabulary (OOV) resolution, and comprehensive administrative analytics.

---

## 🌟 Key Architecture & Capabilities

- **Multilingual Search & Translation**:
  - Semantic and keyword search supporting multiple Indian languages with automated Indic translation pipelines (`utils/translation_service.py`).
  - Real-time phonetic transliteration and multilingual query expansion.
- **Robust Query Intelligence**:
  - **Spell Correction & Fuzzy Matching (`utils/spell_correction.py`)**: Automatic typo mitigation on statistical terms and government scheme titles.
  - **Out-of-Vocabulary Handler (`utils/oov_handler.py`)**: Contextual synonym banks (`utils/synonym_bank.py`) mapping non-standard queries to indexed records.
- **Administrative Intelligence Portal**:
  - Real-time search query logs, latency metrics, failed search diagnostics, and geographical user analytics (`utils/ip_location.py`).
  - Role-protected administrative dashboard (`templates/admin/dashboard.html`, `static/admin_dashboard.js`).
- **Benchmarking & Validation**:
  - Automated mass performance evaluation suite (`benchmark/tests/run_mass_benchmark.py`) for sub-second query latency guarantees.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Flask, SQLite / PostgreSQL
- **NLP & Search**: NLTK, Scikit-learn, Vector Similarity, Custom Synonym & OOV Graphs
- **Frontend**: Bootstrap 5, D3.js (`d3.v7.min.js`), Chart.js (`chart.umd.min.js`), FontAwesome
- **Data Migration**: `scripts/migrate_to_postgres.py` for scalable relational persistence

---

## 📁 Repository Structure

```
Eureka-statathon/
├── app.py                             # Main Flask application & routing
├── database/
│   └── db_store.py                    # Database connection, schemas, and queries
├── utils/
│   ├── searchapp.py                   # Search execution & scoring engine
│   ├── translation_service.dart/.py   # Indic translation & transliteration
│   ├── spell_correction.py            # Domain typo correction
│   ├── oov_handler.py                 # Out-Of-Vocabulary handling
│   ├── synonym_bank.py                # Synonym graphs & mappings
│   └── ip_location.py                 # Regional user analytics
├── benchmark/
│   └── tests/run_mass_benchmark.py    # Search throughput & latency benchmarks
├── templates/                         # Jinja2 views (Search UI & Admin Portal)
└── static/                            # CSS, Charts, D3 visualizations, and JS
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Download Static & Model Assets
```bash
python download_assets.py
```

### 3. Launch the Application
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) to access the search portal, or visit `/admin` for the analytics dashboard.

---

## 📄 License
Developed for Statathon by [Kabhilan VS](https://github.com/Kabhilan-VS-05) and collaborators.
