"""
generate_oov_dictionary.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 2 — small curated Out-Of-Vocabulary dictionary.

Handles ONLY terms that will never naturally appear in the NCO hierarchy and
that SBERT cannot resolve on its own:

  • Brands / platforms       (rapido, swiggy, amazon, paytm, byjus …)
  • Indian vernacular terms  (vakil, darzi, dhobi, kisan, chaiwala, anganwadi …)
  • Common abbreviations     (ca, ias, ips, hr, qa, sde …)

Design rules (enforced by this script):
  1. The SEED below is intentionally small (~90 entries).
  2. Any single-word key that ALREADY exists in the NCO dataset vocabulary is
     DROPPED automatically — the dataset (Layer 1 + SBERT) already covers it.
     This guarantees the OOV file never duplicates dataset knowledge and stays
     small even as the seed is edited.
  3. Multi-word phrases (e.g. "asha worker") are kept — they cannot be a single
     dataset token.

Output: data/processed/oov_dictionary.json

Run:
    python scripts/generate_oov_dictionary.py
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()  # load DATABASE_URL from .env before db_store reads it

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)
CSV_PATH    = os.path.join(PROJECT_DIR, "data", "raw",       "nco_dataset_v6_final.csv")
OUT_JSON    = os.path.join(PROJECT_DIR, "data", "processed", "oov_dictionary.json")

MIN_WORD_LENGTH = 3

# Fields used to build the dataset vocabulary gate (same surface as Layer 1)
VOCAB_FIELDS = ["Occupational Title", "Family", "Group", "Sub Division",
                "Division", "Occupation Description"]

# ─────────────────────────────────────────────────────────────────────────────────
#  CURATED SEED — brands, Indian vernacular, abbreviations, and modern roles that
#  real users type but that are NOT NCO terminology.  Concept lists map each term
#  to standard English words the search engine (dataset + SBERT) understands.
#
#  Add liberally: the generator AUTOMATICALLY drops any single-word key that is
#  already present in the NCO dataset vocabulary, so the final dictionary never
#  duplicates dataset knowledge and stays clean.  Keep concepts to ~3–5 words.
# ─────────────────────────────────────────────────────────────────────────────────
SEED = {

    # ══ BRANDS / PLATFORMS ════════════════════════════════════════════════════════
    # ── Ride-hailing & bike taxi ─────────────────────────────────────────────────
    "rapido":       ["driver", "rider", "taxi", "transportation"],
    "ola":          ["driver", "taxi", "cab", "chauffeur"],
    "uber":         ["driver", "taxi", "cab", "chauffeur"],
    "meru":         ["driver", "taxi", "cab", "chauffeur"],
    "jugnoo":       ["auto", "rickshaw", "driver", "transportation"],
    "namma yatri":  ["auto", "driver", "cab", "transportation"],
    "indrive":      ["driver", "taxi", "cab", "chauffeur"],
    "bluesmart":    ["driver", "taxi", "electric", "chauffeur"],
    "yulu":         ["rider", "electric", "bicycle", "delivery"],
    "bounce":       ["rider", "motorcycle", "scooter", "delivery"],
    "vogo":         ["rider", "scooter", "rental", "transportation"],

    # ── Food & grocery delivery ──────────────────────────────────────────────────
    "swiggy":       ["delivery", "courier", "food", "rider"],
    "zomato":       ["delivery", "courier", "food", "rider"],
    "zepto":        ["delivery", "courier", "groceries", "rider"],
    "blinkit":      ["delivery", "courier", "groceries", "rider"],
    "dunzo":        ["delivery", "courier", "groceries", "rider"],
    "instamart":    ["delivery", "courier", "groceries", "rider"],
    "bigbasket":    ["delivery", "grocery", "rider", "courier"],
    "grofers":      ["delivery", "grocery", "rider", "courier"],
    "milkbasket":   ["delivery", "milk", "dairy", "rider"],
    "countrydelight":["delivery", "milk", "dairy", "rider"],
    "eatfit":       ["cook", "food", "kitchen", "delivery"],
    "faasos":       ["cook", "food", "kitchen", "delivery"],
    "behrouz":      ["cook", "food", "kitchen", "delivery"],

    # ── Logistics / courier ──────────────────────────────────────────────────────
    "porter":       ["delivery", "logistics", "driver", "courier"],
    "shadowfax":    ["delivery", "courier", "logistics", "rider"],
    "delhivery":    ["delivery", "courier", "logistics", "dispatcher"],
    "xpressbees":   ["delivery", "courier", "logistics", "dispatcher"],
    "bluedart":     ["courier", "delivery", "logistics", "dispatcher"],
    "dtdc":         ["courier", "delivery", "logistics", "dispatcher"],
    "ekart":        ["delivery", "courier", "logistics", "rider"],
    "ecomexpress":  ["delivery", "courier", "logistics", "dispatcher"],
    "lalamove":     ["delivery", "logistics", "driver", "courier"],

    # ── E-commerce / retail ──────────────────────────────────────────────────────
    "flipkart":     ["delivery", "logistics", "warehouse", "courier"],
    "amazon":       ["delivery", "logistics", "warehouse", "courier"],
    "meesho":       ["seller", "reseller", "merchant", "sales"],
    "myntra":       ["delivery", "fashion", "logistics", "courier"],
    "ajio":         ["delivery", "fashion", "logistics", "courier"],
    "snapdeal":     ["delivery", "logistics", "courier", "seller"],
    "jiomart":      ["delivery", "grocery", "retail", "courier"],
    "tatacliq":     ["delivery", "retail", "logistics", "courier"],
    "firstcry":     ["delivery", "retail", "logistics", "courier"],
    "pepperfry":    ["delivery", "furniture", "logistics", "carpenter"],
    "urbanladder":  ["delivery", "furniture", "logistics", "carpenter"],
    "nykaa":        ["beauty", "beautician", "cosmetician", "salon"],

    # ── Home & personal services ─────────────────────────────────────────────────
    "urbancompany": ["cleaner", "beautician", "plumber", "electrician"],
    "housejoy":     ["cleaner", "technician", "plumber", "electrician"],
    "nobroker":     ["property", "broker", "real", "estate"],
    "nestaway":     ["property", "caretaker", "real", "estate"],
    "zolo":         ["hospitality", "warden", "caretaker", "manager"],
    "stanza":       ["hospitality", "warden", "caretaker", "manager"],

    # ── Fintech / payments / insurance ───────────────────────────────────────────
    "paytm":        ["payment", "financial", "agent", "cashier"],
    "phonepe":      ["payment", "financial", "agent", "cashier"],
    "gpay":         ["payment", "financial", "agent", "cashier"],
    "bhim":         ["payment", "financial", "agent", "cashier"],
    "cred":         ["payment", "financial", "credit", "banking"],
    "razorpay":     ["payment", "financial", "gateway", "banking"],
    "mobikwik":     ["payment", "financial", "agent", "cashier"],
    "freecharge":   ["payment", "financial", "agent", "cashier"],
    "lic":          ["insurance", "agent", "sales", "financial"],
    "policybazaar": ["insurance", "agent", "advisor", "financial"],
    "groww":        ["investment", "advisor", "financial", "broker"],
    "zerodha":      ["stockbroker", "trader", "financial", "securities"],
    "upstox":       ["stockbroker", "trader", "financial", "securities"],
    "angelone":     ["stockbroker", "trader", "financial", "securities"],

    # ── Edtech ───────────────────────────────────────────────────────────────────
    "byjus":        ["teacher", "tutor", "educator", "instructor"],
    "unacademy":    ["teacher", "tutor", "educator", "instructor"],
    "vedantu":      ["teacher", "tutor", "educator", "instructor"],
    "upgrad":       ["trainer", "educator", "instructor", "counselor"],
    "simplilearn":  ["trainer", "educator", "instructor", "counselor"],
    "toppr":        ["teacher", "tutor", "educator", "instructor"],
    "whitehatjr":   ["teacher", "coding", "instructor", "educator"],
    "physicswallah":["teacher", "tutor", "educator", "instructor"],
    "cuemath":      ["teacher", "tutor", "educator", "instructor"],

    # ── Healthtech ───────────────────────────────────────────────────────────────
    "practo":       ["doctor", "physician", "healthcare", "medical"],
    "1mg":          ["pharmacist", "delivery", "healthcare", "medical"],
    "netmeds":      ["pharmacist", "delivery", "healthcare", "medical"],
    "pharmeasy":    ["pharmacist", "delivery", "healthcare", "medical"],
    "apollo247":    ["doctor", "pharmacist", "healthcare", "medical"],
    "medlife":      ["pharmacist", "delivery", "healthcare", "medical"],
    "healthkart":   ["pharmacist", "nutritionist", "healthcare", "retail"],
    "curefit":      ["fitness", "trainer", "gym", "instructor"],
    "cultfit":      ["fitness", "trainer", "gym", "instructor"],

    # ── Travel / hospitality ─────────────────────────────────────────────────────
    "oyo":          ["hotel", "hospitality", "housekeeping", "manager"],
    "redbus":       ["bus", "booking", "travel", "agent"],
    "makemytrip":   ["travel", "agent", "booking", "tourism"],
    "goibibo":      ["travel", "agent", "booking", "tourism"],
    "ixigo":        ["travel", "agent", "booking", "tourism"],
    "treebo":       ["hotel", "hospitality", "housekeeping", "manager"],
    "fabhotels":    ["hotel", "hospitality", "housekeeping", "manager"],
    "zostel":       ["hotel", "hospitality", "housekeeping", "warden"],

    # ── Jobs / classifieds / eyewear ─────────────────────────────────────────────
    "naukri":       ["recruiter", "placement", "consultant", "hiring"],
    "apna":         ["recruiter", "placement", "consultant", "hiring"],
    "olx":          ["seller", "dealer", "classifieds", "agent"],
    "quikr":        ["seller", "dealer", "classifieds", "agent"],
    "justdial":     ["telecaller", "customer", "service", "sales"],
    "sulekha":      ["telecaller", "customer", "service", "sales"],
    "workindia":    ["recruiter", "placement", "consultant", "hiring"],
    "lenskart":     ["optician", "optometrist", "eyewear", "retail"],
    "magicbricks":  ["property", "broker", "real", "estate"],
    "99acres":      ["property", "broker", "real", "estate"],

    # ══ INDIAN VERNACULAR OCCUPATION TERMS ════════════════════════════════════════
    # ── Hindi / Hindustani — general trades & services ───────────────────────────
    "vakil":        ["lawyer", "advocate", "legal", "attorney"],
    "wakeel":       ["lawyer", "advocate", "legal", "attorney"],
    "darzi":        ["tailor", "garment", "stitching", "sewing"],
    "dhobi":        ["launderer", "washer", "laundry", "ironing"],
    "nai":          ["barber", "hairdresser", "salon", "grooming"],
    "hajaam":       ["barber", "hairdresser", "salon", "grooming"],
    "mistri":       ["carpenter", "mason", "handyman", "artisan"],
    "mistry":       ["carpenter", "mason", "handyman", "artisan"],
    "karigar":      ["artisan", "craftsman", "skilled", "worker"],
    "mazdoor":      ["laborer", "construction", "manual", "worker"],
    "majdoor":      ["laborer", "construction", "manual", "worker"],
    "kisan":        ["farmer", "agricultural", "cultivator", "grower"],
    "kisaan":       ["farmer", "agricultural", "cultivator", "grower"],
    "annadata":     ["farmer", "agricultural", "cultivator", "grower"],
    "chaiwala":     ["tea", "vendor", "street", "seller"],
    "autowala":     ["auto", "rickshaw", "driver", "transportation"],
    "rickshawwala": ["rickshaw", "driver", "transportation", "cycle"],
    "thelawala":    ["cart", "vendor", "street", "hawker"],
    "sabziwala":    ["vegetable", "vendor", "seller", "market"],
    "doodhwala":    ["milk", "delivery", "dairy", "vendor"],
    "paanwala":     ["betel", "vendor", "shopkeeper", "seller"],
    "kabadiwala":   ["scrap", "recycling", "collector", "junk"],
    "raddiwala":    ["scrap", "paper", "recycling", "collector"],
    "feriwala":     ["hawker", "street", "vendor", "peddler"],
    "pheriwala":    ["hawker", "street", "vendor", "peddler"],
    "kaamwali":     ["domestic", "maid", "cleaner", "housekeeping"],
    "kamwali":      ["domestic", "maid", "cleaner", "housekeeping"],
    "bai":          ["domestic", "maid", "cleaner", "housekeeping"],
    "naukar":       ["domestic", "servant", "helper", "attendant"],
    "mochi":        ["cobbler", "shoemaker", "leather", "footwear"],
    "kumhar":       ["potter", "pottery", "ceramic", "clay"],
    "lohar":        ["blacksmith", "metalwork", "iron", "forging"],
    "sonar":        ["goldsmith", "jeweller", "jewelry", "ornaments"],
    "sunar":        ["goldsmith", "jeweller", "jewelry", "ornaments"],
    "julaha":       ["weaver", "weaving", "textile", "loom"],
    "bunkar":       ["weaver", "weaving", "textile", "handloom"],
    "rangrez":      ["dyer", "dyeing", "textile", "fabric"],
    "teli":         ["oil", "presser", "extraction", "vendor"],
    "halwai":       ["confectioner", "sweet", "cook", "baker"],
    "naanbai":      ["baker", "bread", "tandoor", "cook"],
    "tandoorwala":  ["cook", "baker", "tandoor", "food"],
    "mithaiwala":   ["confectioner", "sweet", "vendor", "baker"],
    "chowkidar":    ["security", "guard", "watchman", "caretaker"],
    "durwan":       ["security", "guard", "watchman", "gatekeeper"],
    "mali":         ["gardener", "horticulture", "nursery", "landscaping"],
    "maali":        ["gardener", "horticulture", "nursery", "landscaping"],
    "gwala":        ["milkman", "dairy", "cowherd", "cattle"],
    "ahir":         ["cowherd", "dairy", "cattle", "livestock"],
    "gadariya":     ["shepherd", "herder", "livestock", "grazing"],
    "kasai":        ["butcher", "meat", "slaughter", "abattoir"],
    "qasai":        ["butcher", "meat", "slaughter", "abattoir"],
    "machhua":      ["fisherman", "fisher", "fishing", "marine"],
    "beldar":       ["laborer", "digger", "construction", "worker"],
    "coolie":       ["porter", "laborer", "loader", "carrier"],
    "thekedar":     ["contractor", "supervisor", "foreman", "construction"],
    "rajmistri":    ["mason", "bricklayer", "construction", "builder"],
    "khansama":     ["cook", "chef", "kitchen", "domestic"],
    "bawarchi":     ["cook", "chef", "kitchen", "food"],
    "manihar":      ["bangle", "seller", "vendor", "ornaments"],
    "tokriwala":    ["basket", "maker", "weaver", "artisan"],
    "chabiwala":    ["locksmith", "key", "maker", "repair"],
    "istriwala":    ["ironing", "presser", "laundry", "launderer"],
    "zamindar":     ["landowner", "farmer", "estate", "agricultural"],

    # ── Religious / ritual / traditional roles ───────────────────────────────────
    "pujari":       ["priest", "temple", "religious", "ritual"],
    "pandit":       ["priest", "scholar", "religious", "ritual"],
    "purohit":      ["priest", "religious", "ritual", "ceremony"],
    "maulvi":       ["cleric", "religious", "islamic", "scholar"],
    "imam":         ["cleric", "religious", "islamic", "prayer"],
    "granthi":      ["priest", "sikh", "religious", "gurudwara"],
    "jyotish":      ["astrologer", "horoscope", "fortune", "priest"],
    "jyotishi":     ["astrologer", "horoscope", "fortune", "priest"],
    "tantrik":      ["occult", "ritual", "religious", "healer"],
    "vaidya":       ["ayurvedic", "doctor", "traditional", "medicine"],
    "hakim":        ["doctor", "physician", "traditional", "medical"],
    "mahout":       ["elephant", "handler", "animal", "keeper"],

    # ── Government / revenue / village roles (transliterated) ─────────────────────
    "patwari":      ["revenue", "official", "land", "record"],
    "lekhpal":      ["revenue", "official", "clerk", "record"],
    "tehsildar":    ["revenue", "officer", "administrator", "government"],
    "sarpanch":     ["village", "head", "panchayat", "administrator"],
    "pradhan":      ["village", "head", "panchayat", "administrator"],
    "mukhiya":      ["village", "head", "panchayat", "administrator"],
    "chaprasi":     ["office", "peon", "messenger", "attendant"],
    "daftari":      ["office", "clerk", "stationery", "attendant"],
    "kotwal":       ["police", "constable", "officer", "law"],
    "havildar":     ["police", "constable", "sergeant", "officer"],
    "sepoy":        ["soldier", "military", "army", "constable"],

    # ── Tamil ────────────────────────────────────────────────────────────────────
    "vivasayi":     ["farmer", "agricultural", "cultivator", "grower"],
    "meenavar":     ["fisherman", "fisher", "fishing", "marine"],
    "thacchan":     ["carpenter", "woodwork", "joinery", "furniture"],
    "kollan":       ["blacksmith", "metalwork", "iron", "forging"],
    "aasiriyar":    ["teacher", "educator", "instructor", "school"],
    "maruthuvar":   ["doctor", "physician", "medical", "healthcare"],
    "thozhilali":   ["laborer", "worker", "manual", "helper"],

    # ── Telugu ───────────────────────────────────────────────────────────────────
    "raithu":       ["farmer", "agricultural", "cultivator", "grower"],
    "raitha":       ["farmer", "agricultural", "cultivator", "grower"],
    "vadrangi":     ["carpenter", "woodwork", "joinery", "furniture"],
    "kammari":      ["blacksmith", "metalwork", "iron", "forging"],
    "mangali":      ["barber", "hairdresser", "salon", "grooming"],
    "chakali":      ["launderer", "washer", "laundry", "ironing"],

    # ── Kannada ──────────────────────────────────────────────────────────────────
    "raitha kannada":["farmer", "agricultural", "cultivator", "grower"],
    "badagi":       ["carpenter", "woodwork", "joinery", "furniture"],
    "kammara":      ["blacksmith", "metalwork", "iron", "forging"],
    "shikshaka":    ["teacher", "educator", "instructor", "school"],

    # ── Malayalam ────────────────────────────────────────────────────────────────
    "karshakan":    ["farmer", "agricultural", "cultivator", "grower"],
    "aashari":      ["carpenter", "woodwork", "joinery", "furniture"],
    "adhyapakan":   ["teacher", "educator", "instructor", "school"],
    "thozhilaali":  ["laborer", "worker", "manual", "helper"],

    # ── Bengali ──────────────────────────────────────────────────────────────────
    "krishok":      ["farmer", "agricultural", "cultivator", "grower"],
    "chashi":       ["farmer", "agricultural", "cultivator", "grower"],
    "kamar":        ["blacksmith", "metalwork", "iron", "forging"],
    "napit":        ["barber", "hairdresser", "salon", "grooming"],
    "dhopa":        ["launderer", "washer", "laundry", "ironing"],
    "kumor":        ["potter", "pottery", "ceramic", "clay"],
    "jele":         ["fisherman", "fisher", "fishing", "marine"],
    "majhi":        ["boatman", "ferry", "sailor", "fisherman"],
    "mudi":         ["grocer", "shopkeeper", "retail", "vendor"],
    "shikkhok":     ["teacher", "educator", "instructor", "school"],
    "daktar":       ["doctor", "physician", "medical", "healthcare"],

    # ── Marathi ──────────────────────────────────────────────────────────────────
    "shetkari":     ["farmer", "agricultural", "cultivator", "grower"],
    "sutar":        ["carpenter", "woodwork", "joinery", "furniture"],
    "nhavi":        ["barber", "hairdresser", "salon", "grooming"],
    "parit":        ["launderer", "washer", "laundry", "ironing"],
    "kumbhar":      ["potter", "pottery", "ceramic", "clay"],
    "koli":         ["fisherman", "fisher", "fishing", "marine"],
    "kamgar":       ["laborer", "worker", "manual", "helper"],

    # ── Gujarati ─────────────────────────────────────────────────────────────────
    "khedut":       ["farmer", "agricultural", "cultivator", "grower"],
    "suthar":       ["carpenter", "woodwork", "joinery", "furniture"],
    "luhar":        ["blacksmith", "metalwork", "iron", "forging"],
    "vepari":       ["trader", "merchant", "businessman", "shopkeeper"],
    "dukandar":     ["shopkeeper", "retailer", "vendor", "merchant"],
    "majoor":       ["laborer", "worker", "manual", "helper"],

    # ── Punjabi ──────────────────────────────────────────────────────────────────
    "tarkhan":      ["carpenter", "woodwork", "joinery", "furniture"],
    "lohaar":       ["blacksmith", "metalwork", "iron", "forging"],
    "penter":       ["painter", "painting", "decorating", "coating"],

    # ══ COMMUNITY HEALTH & CARE WORKERS ═══════════════════════════════════════════
    "anganwadi":    ["childcare", "social", "community", "health"],
    "asha":         ["health", "community", "social", "worker"],
    "dai":          ["midwife", "birth", "attendant", "traditional"],
    "compounder":   ["pharmacist", "medical", "dispenser", "attendant"],
    "ayah":         ["nurse", "aide", "childcare", "attendant"],
    "aaya":         ["nurse", "aide", "childcare", "attendant"],
    "wardboy":      ["hospital", "attendant", "orderly", "healthcare"],
    "physiotherapist":["physical", "therapy", "rehabilitation", "healthcare"],
    "dietician":    ["nutritionist", "food", "health", "clinical"],
    "caregiver":    ["caretaker", "attendant", "nurse", "aide"],
    "babysitter":   ["childcare", "nanny", "domestic", "helper"],
    "nanny":        ["childcare", "nanny", "domestic", "helper"],

    # ══ ABBREVIATIONS ═════════════════════════════════════════════════════════════
    # ── Professional / civil services ────────────────────────────────────────────
    "ca":           ["chartered", "accountant", "auditor", "financial"],
    "cs":           ["company", "secretary", "administrator", "compliance"],
    "cma":          ["cost", "accountant", "management", "financial"],
    "icwa":         ["cost", "accountant", "management", "financial"],
    "mba":          ["manager", "executive", "business", "administrator"],
    "ias":          ["civil", "servant", "administrator", "officer"],
    "ips":          ["police", "officer", "superintendent", "inspector"],
    "ifs":          ["diplomat", "foreign", "service", "officer"],
    "irs":          ["revenue", "tax", "officer", "inspector"],
    "pcs":          ["civil", "servant", "government", "officer"],
    "llb":          ["lawyer", "advocate", "legal", "attorney"],
    "llm":          ["lawyer", "advocate", "legal", "attorney"],
    # ── Medical degrees / roles ──────────────────────────────────────────────────
    "mbbs":         ["doctor", "physician", "medical", "healthcare"],
    "bds":          ["dentist", "dental", "oral", "healthcare"],
    "bams":         ["ayurvedic", "doctor", "medicine", "healthcare"],
    "bhms":         ["homeopathy", "doctor", "medicine", "healthcare"],
    "anm":          ["nurse", "midwife", "auxiliary", "health"],
    "gnm":          ["nurse", "midwife", "general", "health"],
    # ── IT / BPO / engineering ───────────────────────────────────────────────────
    "hr":           ["human", "resources", "recruiter", "personnel"],
    "qa":           ["quality", "tester", "inspector", "assurance"],
    "qc":           ["quality", "control", "inspector", "tester"],
    "bpo":          ["call", "center", "customer", "service"],
    "kpo":          ["research", "analyst", "knowledge", "services"],
    "sde":          ["software", "developer", "engineer", "programmer"],
    "swe":          ["software", "engineer", "developer", "programmer"],
    "dba":          ["database", "administrator", "developer", "engineer"],
    "devops":       ["system", "administrator", "software", "engineer"],
    "sap":          ["software", "consultant", "developer", "analyst"],
    "bba":          ["manager", "executive", "business", "administrator"],
    "bca":          ["software", "developer", "programmer", "computer"],
    "mca":          ["software", "developer", "programmer", "computer"],
    "btech":        ["engineer", "technical", "technology", "graduate"],
    # ── Police / defence ranks ───────────────────────────────────────────────────
    "sho":          ["police", "officer", "inspector", "station"],
    "asi":          ["police", "assistant", "inspector", "officer"],
    "dsp":          ["police", "superintendent", "officer", "deputy"],
    "constable":    ["police", "officer", "law", "enforcement"],

    # ══ MODERN / DIGITAL / GIG ROLES ══════════════════════════════════════════════
    "youtuber":     ["content", "creator", "video", "broadcaster"],
    "influencer":   ["social", "media", "content", "marketer"],
    "blogger":      ["content", "writer", "journalist", "editor"],
    "vlogger":      ["video", "content", "creator", "broadcaster"],
    "podcaster":    ["broadcaster", "content", "creator", "media"],
    "streamer":     ["broadcaster", "content", "creator", "media"],
    "freelancer":   ["self-employed", "consultant", "independent", "contractor"],
    "gigworker":    ["delivery", "driver", "freelancer", "self-employed"],
    "dropshipper":  ["seller", "reseller", "merchant", "ecommerce"],
    "reseller":     ["seller", "merchant", "sales", "trader"],
    "daytrader":    ["trader", "financial", "securities", "stocks"],

    # ══ MULTI-WORD VERNACULAR / ROLES ═════════════════════════════════════════════
    "asha worker":  ["health", "community", "social", "worker"],
    "anganwadi worker":["childcare", "social", "community", "health"],
    "ward boy":     ["hospital", "attendant", "orderly", "healthcare"],
    "mid day meal": ["cook", "school", "food", "worker"],
    "gram sevak":   ["village", "development", "officer", "rural"],
    "gram panchayat":["village", "administration", "officer", "rural"],
    "block development officer":["block", "development", "officer", "government"],
    "revenue inspector":["revenue", "inspector", "land", "official"],
    "forest guard": ["forest", "guard", "ranger", "wildlife"],
    "recovery agent":["debt", "collector", "financial", "officer"],
    "business correspondent":["banking", "financial", "agent", "correspondent"],
    "bank mitra":   ["banking", "financial", "agent", "correspondent"],
    "data entry operator":["data", "entry", "clerk", "computer"],
    "computer operator":["computer", "operator", "clerk", "data"],
    "field officer":["field", "officer", "survey", "marketing"],
    "delivery boy": ["delivery", "courier", "rider", "logistics"],
    "delivery partner":["delivery", "courier", "rider", "logistics"],
    "food delivery":["delivery", "courier", "food", "rider"],
    "bike taxi":    ["driver", "rider", "motorcycle", "transportation"],
    "auto driver":  ["auto", "rickshaw", "driver", "transportation"],
    "cab driver":   ["driver", "taxi", "cab", "chauffeur"],
    "truck driver": ["driver", "heavy", "transportation", "goods"],
    "lorry driver": ["driver", "heavy", "transportation", "goods"],
    "tractor driver":["driver", "agricultural", "tractor", "farm"],
    "bus conductor":["conductor", "ticket", "transportation", "bus"],
    "jcb operator": ["construction", "equipment", "operator", "excavator"],
    "crane operator":["lifting", "equipment", "operator", "construction"],
    "forklift operator":["warehouse", "operator", "logistics", "driver"],
    "ac mechanic":  ["refrigeration", "air", "conditioning", "technician"],
    "bike mechanic":["motorcycle", "mechanic", "vehicle", "repair"],
    "mobile repair":["electronics", "repair", "technician", "mobile"],
    "home guard":   ["security", "guard", "auxiliary", "police"],
    "security guard":["security", "guard", "watchman", "protection"],
    "house keeping":["housekeeping", "cleaner", "domestic", "attendant"],
    "beauty parlour":["beautician", "salon", "cosmetician", "grooming"],
    "mehndi artist":["henna", "artist", "beautician", "decorator"],
    "makeup artist":["makeup", "beautician", "cosmetician", "salon"],
    "event manager":["event", "manager", "coordinator", "planner"],
    "wedding planner":["event", "planner", "coordinator", "manager"],
    "gym trainer":  ["fitness", "trainer", "instructor", "physical"],
    "yoga instructor":["yoga", "instructor", "trainer", "wellness"],
    "personal trainer":["fitness", "trainer", "instructor", "physical"],
    "call center":  ["call", "center", "customer", "service"],
    "customer care":["customer", "service", "support", "telecaller"],
    "tele caller":  ["telecaller", "customer", "service", "sales"],
    "lab technician":["laboratory", "technician", "medical", "pathology"],
    "x ray technician":["radiographer", "technician", "radiology", "medical"],
    "data scientist":["data", "analyst", "statistician", "researcher"],
    "digital marketer":["marketing", "digital", "advertising", "promoter"],
    "content creator":["content", "creator", "video", "media"],
    "graphic designer":["graphic", "designer", "visual", "creative"],

    # ══ GAP-FILL: everyday Indian terms found missing in coverage audit ════════════
    # ── Street-food & small vendors ──────────────────────────────────────────────
    "panipuri wala":["snack", "vendor", "street", "food"],
    "panipuriwala": ["snack", "vendor", "street", "food"],
    "chaat wala":   ["snack", "vendor", "street", "food"],
    "chaatwala":    ["snack", "vendor", "street", "food"],
    "vadapav":      ["snack", "vendor", "street", "food"],
    "momos seller": ["snack", "vendor", "street", "food"],
    "juice wala":   ["juice", "vendor", "street", "beverage"],
    "juicewala":    ["juice", "vendor", "street", "beverage"],
    "icecream wala":["icecream", "vendor", "street", "food"],
    "golawala":     ["icecream", "vendor", "street", "food"],
    "kulfiwala":    ["icecream", "vendor", "street", "food"],
    "bhelwala":     ["snack", "vendor", "street", "food"],
    "phoolwala":    ["flower", "vendor", "florist", "seller"],
    "phalwala":     ["fruit", "vendor", "seller", "market"],
    "machliwala":   ["fish", "vendor", "seller", "market"],
    "dhabawala":    ["restaurant", "cook", "food", "vendor"],
    "tiffinwala":   ["food", "delivery", "cook", "caterer"],
    "dabbawala":    ["food", "delivery", "courier", "tiffin"],

    # ── Transport variants ───────────────────────────────────────────────────────
    "rickshaw puller":["rickshaw", "puller", "transportation", "cycle"],
    "erickshaw":    ["rickshaw", "electric", "driver", "transportation"],
    "e rickshaw":   ["rickshaw", "electric", "driver", "transportation"],
    "tempo driver": ["driver", "goods", "transportation", "vehicle"],
    "tempowala":    ["driver", "goods", "transportation", "vehicle"],
    "tangawala":    ["cart", "horse", "driver", "transportation"],
    "bullock cart": ["cart", "driver", "transportation", "rural"],
    "boatman":      ["boatman", "ferry", "sailor", "fisherman"],
    "khalasi":      ["helper", "loader", "transportation", "assistant"],
    "cleaner truck":["helper", "loader", "transportation", "assistant"],

    # ── Informal / waste / sanitation ────────────────────────────────────────────
    "ragpicker":    ["waste", "scrap", "recycling", "collector"],
    "rag picker":   ["waste", "scrap", "recycling", "collector"],
    "scrap dealer": ["scrap", "recycling", "dealer", "collector"],
    "kabadi":       ["scrap", "recycling", "collector", "junk"],
    "safai karamchari":["sanitation", "cleaner", "sweeper", "worker"],
    "safaiwala":    ["sanitation", "cleaner", "sweeper", "worker"],
    "sanitation worker":["sanitation", "cleaner", "sweeper", "worker"],
    "manual scavenger":["sanitation", "cleaner", "sweeper", "worker"],
    "mehtar":       ["sanitation", "cleaner", "sweeper", "worker"],
    "sweeper":      ["sanitation", "cleaner", "janitor", "worker"],

    # ── Domestic / care variants ─────────────────────────────────────────────────
    "maid":         ["domestic", "maid", "cleaner", "housekeeping"],
    "housemaid":    ["domestic", "maid", "cleaner", "housekeeping"],
    "servant":      ["domestic", "servant", "helper", "attendant"],
    "watchman":     ["security", "guard", "watchman", "caretaker"],
    "caretaker":    ["caretaker", "attendant", "custodian", "watchman"],

    # ── Animal husbandry / rural ─────────────────────────────────────────────────
    "shepherd":     ["shepherd", "herder", "livestock", "grazing"],
    "goat herder":  ["goat", "herder", "livestock", "grazing"],
    "cattle herder":["cattle", "herder", "livestock", "grazing"],
    "pig farmer":   ["pig", "farmer", "livestock", "piggery"],
    "poultry farmer":["poultry", "farmer", "livestock", "chicken"],
    "beekeeper":    ["bee", "keeper", "apiculture", "honey"],
    "snake catcher":["snake", "catcher", "wildlife", "handler"],
    "dog trainer":  ["dog", "trainer", "animal", "handler"],
    "cowherd":      ["cowherd", "dairy", "cattle", "livestock"],

    # ── Informal / traditional healthcare ────────────────────────────────────────
    "quack":        ["unlicensed", "doctor", "medical", "practitioner"],
    "jhola chaap":  ["unlicensed", "doctor", "medical", "practitioner"],
    "jholachaap":   ["unlicensed", "doctor", "medical", "practitioner"],
    "rmp doctor":   ["rural", "medical", "practitioner", "doctor"],
    "medical representative":["medical", "sales", "representative", "pharmaceutical"],

    # ── Government scheme variants ───────────────────────────────────────────────
    "mgnrega":      ["rural", "laborer", "construction", "worker"],
    "mgnrega worker":["rural", "laborer", "construction", "worker"],
    "nrega":        ["rural", "laborer", "construction", "worker"],
    "nrega worker": ["rural", "laborer", "construction", "worker"],
    "aanganwadi":   ["childcare", "social", "community", "health"],
    "aanganwadi worker":["childcare", "social", "community", "health"],
    "homeguard":    ["security", "guard", "auxiliary", "police"],
    "linesman":     ["electrical", "lineman", "power", "technician"],
    "lineman":      ["electrical", "power", "maintenance", "technician"],
    "meter reader": ["meter", "reader", "utility", "field"],
    "panchayat secretary":["village", "administrative", "clerk", "officer"],
    "talati":       ["revenue", "clerk", "village", "official"],

    # ── Education variants ───────────────────────────────────────────────────────
    "tuition teacher":["tutor", "teacher", "coaching", "educator"],
    "tution teacher": ["tutor", "teacher", "coaching", "educator"],
    "coaching teacher":["tutor", "teacher", "coaching", "educator"],
    "private tutor":  ["tutor", "teacher", "coaching", "educator"],
    "home tutor":     ["tutor", "teacher", "coaching", "educator"],

    # ── Security / defence ───────────────────────────────────────────────────────
    "bouncer":      ["security", "guard", "doorman", "protection"],
    "gunman":       ["security", "guard", "armed", "protection"],
    "watchman guard":["security", "guard", "watchman", "caretaker"],

    # ── Wellness / personal services ─────────────────────────────────────────────
    "yoga teacher": ["yoga", "instructor", "trainer", "wellness"],
    "spa therapist":["spa", "masseur", "therapist", "wellness"],
    "masseur":      ["massage", "therapist", "spa", "wellness"],
    "masseuse":     ["massage", "therapist", "spa", "wellness"],
    "zumba instructor":["fitness", "instructor", "trainer", "dance"],
    "salon staff":  ["salon", "beautician", "hairdresser", "grooming"],

    # ══ GOVERNMENT / REVENUE / POLICE ABBREVIATIONS & ROLES (expanded) ════════════
    "kanungo":      ["revenue", "land", "records", "officer"],
    "naib tehsildar":["revenue", "officer", "administrator", "government"],
    "vao":          ["village", "administrative", "officer", "revenue"],
    "karnam":       ["village", "accountant", "revenue", "clerk"],
    "kulkarni":     ["village", "accountant", "revenue", "clerk"],
    "patil":        ["village", "head", "administrator", "rural"],
    "munsif":       ["judicial", "officer", "court", "magistrate"],
    "amin":         ["revenue", "surveyor", "official", "measurement"],
    "mro":          ["mandal", "revenue", "officer", "government"],
    "sdm":          ["sub", "divisional", "magistrate", "administrator"],
    "sdo":          ["sub", "divisional", "officer", "government"],
    "si":           ["sub", "inspector", "police", "officer"],
    "psi":          ["police", "sub", "inspector", "officer"],
    "sp":           ["superintendent", "police", "officer", "law"],
    "hc":           ["head", "constable", "police", "officer"],
    "ldc":          ["lower", "division", "clerk", "government"],
    "udc":          ["upper", "division", "clerk", "government"],
    "steno":        ["stenographer", "typist", "clerk", "office"],
    "stenographer": ["steno", "typist", "secretary", "clerk"],
    "je":           ["junior", "engineer", "technical", "government"],
    "ae":           ["assistant", "engineer", "technical", "government"],
    "vdo":          ["village", "development", "officer", "rural"],
    "aeo":          ["agricultural", "extension", "officer", "government"],
    "tte":          ["ticket", "examiner", "railway", "collector"],
    "rpf":          ["railway", "protection", "force", "security"],
    "grp":          ["government", "railway", "police", "security"],
    "loco pilot":   ["locomotive", "pilot", "railway", "driver"],
    "train driver": ["driver", "locomotive", "railway", "train"],
    "fire officer": ["fire", "officer", "firefighter", "safety"],
    "jailor":       ["prison", "warden", "correctional", "officer"],
    "prison warden":["prison", "warden", "correctional", "officer"],
    "process server":["legal", "server", "court", "official"],

    # ══ AGRICULTURE & RURAL (expanded) ═══════════════════════════════════════════
    "khet mazdoor": ["farm", "laborer", "agricultural", "worker"],
    "halwaha":      ["ploughman", "farmer", "agricultural", "laborer"],
    "batai":        ["sharecropper", "tenant", "farmer", "agricultural"],
    "goala":        ["milkman", "dairy", "cattle", "cowherd"],
    "tea garden worker":["tea", "plantation", "laborer", "garden"],
    "tea picker":   ["tea", "picker", "plantation", "agricultural"],
    "toddy tapper": ["toddy", "palm", "tapper", "agricultural"],
    "coconut climber":["coconut", "climber", "tree", "harvester"],
    "tree climber": ["tree", "climber", "harvester", "agricultural"],
    "headload worker":["headload", "porter", "laborer", "carrier"],
    "head load worker":["headload", "porter", "laborer", "carrier"],
    "papad maker":  ["papad", "food", "maker", "artisan"],
    "pappad maker": ["pappad", "food", "maker", "artisan"],
    "achar maker":  ["pickle", "food", "maker", "artisan"],

    # ══ CONSTRUCTION & INFRASTRUCTURE (expanded) ═════════════════════════════════
    "bhatta mazdoor":["brick", "kiln", "laborer", "worker"],
    "stone cutter": ["stone", "mason", "quarry", "worker"],
    "stone mason":  ["stone", "mason", "construction", "builder"],
    "quarry worker":["quarry", "stone", "mining", "laborer"],
    "bore well operator":["bore", "well", "drilling", "operator"],
    "well digger":  ["well", "digger", "excavation", "laborer"],
    "tile fixer":   ["tile", "layer", "construction", "worker"],
    "marble worker":["marble", "stone", "construction", "worker"],
    "scaffolding worker":["scaffolding", "construction", "laborer", "helper"],
    "waterproofing worker":["waterproofing", "construction", "technician", "worker"],
    "roof thatcher":["thatcher", "roof", "construction", "traditional"],
    "bamboo worker":["bamboo", "craftsman", "artisan", "construction"],
    "shuttering carpenter":["shuttering", "carpenter", "construction", "formwork"],
    "toll collector":["toll", "collector", "booth", "worker"],
    "loading worker":["loader", "warehouse", "laborer", "worker"],
    "unloading worker":["unloader", "warehouse", "laborer", "worker"],
    "packing worker":["packing", "warehouse", "laborer", "worker"],
    "weighman":     ["weigher", "weighbridge", "operator", "worker"],

    # ══ TRADITIONAL ARTISANS & CRAFTS (expanded) ═════════════════════════════════
    "zari worker":  ["embroidery", "gold", "thread", "artisan"],
    "chikan karigar":["embroidery", "artisan", "textile", "craft"],
    "chikankari":   ["embroidery", "artisan", "textile", "craft"],
    "block printer":["block", "print", "textile", "artisan"],
    "kalamkari":    ["textile", "painting", "artisan", "craft"],
    "dhokra artisan":["metal", "craft", "artisan", "tribal"],
    "bamboo artisan":["bamboo", "craft", "artisan", "weaver"],
    "cane worker":  ["cane", "basket", "artisan", "weaver"],
    "mat weaver":   ["mat", "weaver", "artisan", "handcraft"],
    "bidi worker":  ["bidi", "tobacco", "maker", "worker"],
    "bidi maker":   ["bidi", "roller", "tobacco", "worker"],
    "agarbatti worker":["agarbatti", "incense", "maker", "worker"],
    "kite maker":   ["kite", "maker", "artisan", "craft"],
    "toy maker":    ["toy", "maker", "artisan", "craft"],
    "wood carver":  ["wood", "carving", "artisan", "sculptor"],
    "stone carver": ["stone", "carving", "sculptor", "artisan"],
    "brass worker": ["brass", "metal", "artisan", "craftsman"],
    "leather worker":["leather", "artisan", "craft", "tanner"],
    "tanner":       ["leather", "tanning", "artisan", "craftsman"],
    "chhipa":       ["block", "printer", "textile", "dyer"],
    "rangwala":     ["painter", "color", "decorator", "artist"],
    "rope maker":   ["rope", "maker", "artisan", "fiber"],

    # ══ RELIGIOUS ROLES (expanded) ════════════════════════════════════════════════
    "padre":        ["priest", "christian", "religious", "clergy"],
    "pastor":       ["priest", "christian", "religious", "minister"],
    "archak":       ["priest", "temple", "religious", "ritual"],
    "panda":        ["priest", "temple", "guide", "pilgrim"],
    "mahant":       ["head", "priest", "monastery", "religious"],
    "sadhu":        ["monk", "ascetic", "religious", "spiritual"],
    "swami":        ["monk", "religious", "spiritual", "teacher"],
    "acharya":      ["religious", "teacher", "scholar", "priest"],
    "maulana":      ["islamic", "teacher", "scholar", "religious"],
    "qari":         ["quran", "teacher", "religious", "islamic"],
    "hafiz":        ["quran", "memorizer", "religious", "islamic"],
    "dhadi":        ["devotional", "singer", "sikh", "musician"],
    "bhagavatar":   ["temple", "musician", "devotional", "singer"],
    "bhajan singer":["devotional", "singer", "music", "religious"],
    "qawwali singer":["devotional", "singer", "music", "performer"],

    # ══ PERFORMING ARTS & FOLK CULTURE ═══════════════════════════════════════════
    "kathputli":    ["puppet", "puppeteer", "folk", "artist"],
    "puppeteer":    ["puppet", "performer", "folk", "artist"],
    "manganiyar":   ["folk", "musician", "singer", "rajasthani"],
    "langa":        ["folk", "musician", "singer", "rajasthani"],
    "bahurupi":     ["folk", "performer", "actor", "impersonator"],
    "theyyam performer":["ritual", "performer", "kerala", "artist"],
    "yakshagana performer":["folk", "performer", "karnataka", "artist"],
    "lavani dancer":["folk", "dancer", "maharashtra", "performer"],
    "chhau dancer": ["folk", "dancer", "martial", "performer"],
    "madaari":      ["street", "performer", "monkey", "entertainer"],
    "naqqal":       ["folk", "comedian", "performer", "imitator"],
    "bhand":        ["folk", "performer", "comedian", "entertainer"],
    "spot boy":     ["spot", "boy", "film", "helper"],
    "junior artist":["junior", "artist", "extra", "film"],
    "stuntman":     ["stunt", "performer", "film", "actor"],
    "choreographer":["choreographer", "dancer", "trainer", "instructor"],

    # ══ MEDIA, DIGITAL & GIG ECONOMY (expanded) ══════════════════════════════════
    "rj":           ["radio", "jockey", "broadcaster", "media"],
    "radio jockey": ["radio", "jockey", "broadcaster", "media"],
    "vj":           ["video", "jockey", "presenter", "media"],
    "news anchor":  ["anchor", "presenter", "journalist", "media"],
    "news reader":  ["news", "reader", "journalist", "broadcaster"],
    "emcee":        ["emcee", "host", "event", "presenter"],
    "standup comedian":["comedian", "entertainer", "performer", "stage"],
    "stand up comedian":["comedian", "entertainer", "performer", "stage"],
    "voice artist": ["voice", "artist", "dubbing", "media"],
    "dubbing artist":["dubbing", "artist", "voice", "media"],
    "drone operator":["drone", "pilot", "aerial", "photography"],
    "drone pilot":  ["drone", "aerial", "operator", "photographer"],
    "vfx artist":   ["visual", "effects", "animator", "designer"],
    "3d animator":  ["animator", "3d", "visual", "designer"],
    "2d animator":  ["animator", "2d", "visual", "designer"],
    "motion designer":["motion", "graphic", "designer", "animator"],
    "reels editor": ["video", "editor", "content", "social"],
    "thumbnail designer":["graphic", "designer", "youtube", "content"],
    "android developer":["android", "mobile", "developer", "programmer"],
    "ios developer":["ios", "mobile", "developer", "programmer"],
    "ml engineer":  ["machine", "learning", "engineer", "data"],
    "ai engineer":  ["artificial", "intelligence", "engineer", "developer"],
    "blockchain developer":["blockchain", "developer", "cryptocurrency", "programmer"],
    "cloud engineer":["cloud", "infrastructure", "engineer", "devops"],
    "ethical hacker":["cybersecurity", "ethical", "hacker", "penetration"],
    "pen tester":   ["penetration", "testing", "security", "cybersecurity"],
    "sap consultant":["sap", "erp", "consultant", "technology"],
    "erp consultant":["erp", "consultant", "technology", "system"],
    "seo specialist":["seo", "digital", "marketing", "website"],
    "email marketer":["email", "marketing", "digital", "campaign"],
    "network marketer":["sales", "mlm", "marketing", "distributor"],
    "mlm agent":    ["sales", "direct", "marketing", "distributor"],
    "brand promoter":["brand", "promoter", "sales", "marketing"],
    "merchandiser": ["merchandiser", "retail", "display", "marketing"],
    "community manager":["community", "manager", "social", "media"],
    "copywriter":   ["copywriter", "content", "writer", "advertising"],
    "scriptwriter": ["scriptwriter", "content", "writer", "media"],
    "nail technician":["nail", "technician", "beautician", "salon"],
    "tattoo artist":["tattoo", "artist", "body", "art"],
    "fashion stylist":["stylist", "fashion", "image", "consultant"],

    # ══ HEALTHCARE & TRADITIONAL MEDICINE (expanded) ══════════════════════════════
    "siddha doctor":["siddha", "traditional", "doctor", "medicine"],
    "unani doctor": ["unani", "traditional", "doctor", "medicine"],
    "rmp":          ["rural", "medical", "practitioner", "doctor"],
    "panchakarma therapist":["ayurvedic", "therapist", "panchakarma", "wellness"],
    "acupuncturist":["acupuncture", "therapist", "traditional", "medicine"],
    "naturopath":   ["naturopathy", "therapist", "traditional", "medicine"],
    "pranic healer":["pranic", "healing", "therapist", "wellness"],
    "reiki healer": ["reiki", "healing", "therapist", "wellness"],

    # ══ EDUCATION (expanded) ══════════════════════════════════════════════════════
    "shiksha mitra":["teacher", "government", "school", "educator"],
    "para teacher": ["teacher", "contractual", "school", "educator"],
    "anganwadi helper":["anganwadi", "helper", "childcare", "worker"],
    "balwadi worker":["childcare", "preschool", "worker", "educator"],

    # ══ FINTECH / BANKING CORRESPONDENTS (expanded) ═══════════════════════════════
    "paynearby":    ["banking", "payment", "agent", "correspondent"],
    "spice money":  ["banking", "payment", "agent", "rural"],
    "fino":         ["banking", "payment", "agent", "correspondent"],
    "cashfree":     ["payment", "financial", "gateway", "banking"],
    "chit fund agent":["chit", "fund", "financial", "agent"],
    "microfinance agent":["microfinance", "loan", "agent", "financial"],
    "pigmy agent":  ["savings", "collector", "bank", "agent"],
    "shg coordinator":["self", "help", "group", "coordinator"],

    # ══ DELIVERY / SERVICES PLATFORMS (expanded) ══════════════════════════════════
    "licious":      ["delivery", "meat", "food", "rider"],
    "freshtohome":  ["delivery", "fish", "meat", "rider"],
    "ninjacart":    ["delivery", "agriculture", "grocery", "logistics"],
    "dealshare":    ["delivery", "grocery", "retail", "rider"],
    "swiggy genie": ["delivery", "courier", "errand", "rider"],
    "amazon fresh": ["delivery", "grocery", "rider", "courier"],
    "jiofiber":     ["technician", "cable", "internet", "installer"],

    # ══ RETAIL & GROCERY ══════════════════════════════════════════════════════════
    "kirana":       ["grocery", "shopkeeper", "retail", "store"],
    "kiryana":      ["grocery", "shopkeeper", "retail", "store"],
    "kirana wala":  ["grocery", "shopkeeper", "retail", "store"],
    "kiryana wala": ["grocery", "shopkeeper", "retail", "store"],
    "chemist":      ["pharmacist", "medicine", "healthcare", "retail"],
    "druggist":     ["pharmacist", "medicine", "dispenser", "healthcare"],
    "stock boy":    ["warehouse", "helper", "retail", "store"],
    "ngo worker":   ["social", "worker", "nonprofit", "community"],
    "field worker": ["field", "worker", "survey", "community"],
}


def load_dataset_vocab(path: str) -> set:
    """Build the set of single-word tokens present anywhere in the NCO dataset."""
    vocab: set = set()
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            for field in VOCAB_FIELDS:
                for w in re.findall(r"[a-z]+", (row.get(field) or "").lower()):
                    if len(w) >= MIN_WORD_LENGTH:
                        vocab.add(w)
    return vocab


def build_oov(seed: dict, vocab: set):
    """
    Filter the seed: drop any SINGLE-WORD key already in the dataset vocabulary.
    Multi-word keys are always kept (they cannot be a single dataset token).
    Returns (kept_dict, dropped_list).
    """
    kept: dict = {}
    dropped: list = []
    for key, concepts in seed.items():
        k = key.lower().strip()
        is_phrase = " " in k
        if not is_phrase and k in vocab:
            dropped.append(k)        # redundant — dataset already knows it
            continue
        kept[k] = concepts
    return kept, dropped


def main():
    print(f"[INFO] Reading dataset vocabulary: {CSV_PATH}")
    vocab = load_dataset_vocab(CSV_PATH)
    print(f"[INFO] Dataset vocabulary size: {len(vocab)} tokens")

    print(f"[INFO] Seed entries: {len(SEED)}")
    oov, dropped = build_oov(SEED, vocab)

    print(f"[INFO] Kept (true OOV)     : {len(oov)}")
    print(f"[INFO] Dropped (redundant) : {len(dropped)}")
    if dropped:
        print(f"        already in dataset: {sorted(dropped)}")

    # ── Write JSON (editable / auditable artifact) ───────────────────────────────────
    import json
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(oov, f, indent=2)

    print(f"[INFO] OOV dictionary JSON saved: {OUT_JSON}")
    print(f"[INFO] Please run scripts/migrate_to_postgres.py to load this into the database.")


if __name__ == "__main__":
    main()
