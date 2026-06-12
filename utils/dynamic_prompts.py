import json
import re
import os
import sys
from collections import Counter

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from database import db_store

# Load the metadata to analyze occupation titles from PostgreSQL.
_, metadata = db_store.load_search_documents()

occupation_titles = [item['occupation_title'] for item in metadata]

# Dynamic prompt generation templates based on occupation patterns
PROMPT_TEMPLATES = {
    # Leadership roles
    'leadership': [
        "The person who leads and directs {domain} operations.",
        "I oversee {domain} activities and make strategic decisions.",
        "I manage teams and ensure success in {domain}."
    ],
    
    # Technical/Engineering roles
    'technical': [
        "The person who works with {technical_domain} and technical systems.",
        "I apply technical expertise in {technical_domain}.",
        "I ensure proper operation and maintenance of {technical_domain}."
    ],
    
    # Service/Support roles
    'service': [
        "The person who provides {service_type} and support services.",
        "I assist with {service_type} and customer needs.",
        "I ensure quality {service_type} and client satisfaction."
    ],
    
    # Creative/Design roles
    'creative': [
        "The person who creates and designs {creative_domain}.",
        "I work with {creative_domain} and creative solutions.",
        "I develop innovative {creative_domain} and artistic content."
    ],
    
    # Educational roles
    'education': [
        "The person who teaches and educates in {education_domain}.",
        "I provide instruction and guidance in {education_domain}.",
        "I help students learn and develop in {education_domain}."
    ],
    
    # Healthcare roles
    'healthcare': [
        "The person who provides {healthcare_type} and medical care.",
        "I work with patients and deliver {healthcare_type}.",
        "I ensure health and wellbeing through {healthcare_type}."
    ],
    
    # Financial roles
    'financial': [
        "The person who manages {financial_domain} and financial operations.",
        "I handle {financial_domain} and financial transactions.",
        "I ensure proper {financial_domain} and financial management."
    ],
    
    # Production/Manufacturing roles
    'production': [
        "The person who produces and manufactures {product_type}.",
        "I work with {product_type} production processes.",
        "I ensure quality {product_type} and manufacturing efficiency."
    ],
    
    # Transportation roles
    'transportation': [
        "I drive or operate {transport_type}.",
        "My job is related to {transport_type}.",
        "I help transport people or goods using {transport_type}."
    ],
    
    # Administrative roles
    'administrative': [
        "The person who handles {admin_type} and administrative tasks.",
        "I manage {admin_type} and office operations.",
        "I ensure proper {admin_type} and organizational support."
    ],
    
    # Sales/Marketing roles
    'sales': [
        "The person who sells and promotes {product_service}.",
        "I work with {product_service} sales and marketing.",
        "I drive revenue through {product_service}."
    ],
    
    # Legal roles
    'legal': [
        "The person who provides {legal_type} and legal services.",
        "I handle {legal_type} and legal matters.",
        "I ensure compliance and proper {legal_type}."
    ],
    
    # Agricultural roles
    'agricultural': [
        "The person who works with {agri_type} and agricultural operations.",
        "I manage {agri_type} and farming activities.",
        "I ensure productive {agri_type} and agricultural success."
    ],
    
    # Research/Science roles
    'research': [
        "I study {research_domain}.",
        "I observe and record information about {research_domain}.",
        "My work is related to research on {research_domain}."
    ],
    
    # General worker roles
    'worker': [
        "I work as a {work_type}.",
        "My job is related to {work_type}.",
        "I do daily work connected with {work_type}."
    ]
}

def extract_domain_from_title(occupation_title):
    """Extract the main domain/area from occupation title"""
    title_lower = re.sub(r"[^a-z0-9\s]", " ", occupation_title.lower())
    
    # Remove common prefixes and suffixes
    prefixes = ['general', 'senior', 'junior', 'assistant', 'associate', 'chief', 'head', 'lead']
    suffixes = ['others', 'assistant', 'helper', 'worker', 'operator', 'attendant']
    
    words = title_lower.split()
    # Filter out common prefixes/suffixes
    filtered_words = [w for w in words if w not in prefixes + suffixes]
    
    # Extract key domain words
    domain_words = []
    for i, word in enumerate(filtered_words):
        # Skip very common words
        if word in ['and', 'of', 'in', 'for', 'with', 'or', 'the', 'a', 'an']:
            continue
        
        # Look for domain indicators
        if word in ['bank', 'financial', 'account', 'finance']:
            domain_words.append('banking and financial services')
        elif word in ['engineer', 'engineering', 'technical', 'mechanical']:
            domain_words.append('engineering and technical systems')
        elif word in ['medical', 'health', 'nurse', 'doctor']:
            domain_words.append('healthcare and medical services')
        elif word in ['teacher', 'education', 'professor', 'school']:
            domain_words.append('education and teaching')
        elif word in ['sales', 'marketing', 'promotion']:
            domain_words.append('sales and marketing')
        elif word in ['construction', 'building', 'infrastructure']:
            domain_words.append('construction and infrastructure')
        elif word in ['transport', 'driver', 'operator', 'vehicle']:
            domain_words.append('transportation and logistics')
        elif word in ['legal', 'law', 'court', 'advocate']:
            domain_words.append('legal services and compliance')
        elif word in ['farm', 'agricultural', 'crop', 'livestock']:
            domain_words.append('agricultural and farming operations')
        elif word in ['astronomer', 'astronomy', 'planet', 'star']:
            domain_words.append('stars, planets, and space')
        elif word in ['research', 'science', 'scientist', 'laboratory']:
            domain_words.append('research and scientific analysis')
        elif word in ['computer', 'software', 'system', 'it', 'network']:
            domain_words.append('information technology and systems')
        elif word in ['manufacturing', 'production', 'factory']:
            domain_words.append('manufacturing and production')
        elif word in ['hotel', 'restaurant', 'food', 'catering']:
            domain_words.append('hospitality and food services')
        elif len(word) > 3:  # Include meaningful words
            domain_words.append(word)
    
    # Return the most relevant domain
    if domain_words:
        return domain_words[0] if len(domain_words) == 1 else f"{' and '.join(domain_words[:2])}"
    return 'professional operations'

def determine_category(occupation_title):
    """Determine the category of occupation based on title patterns"""
    title_lower = occupation_title.lower()
    
    # Leadership indicators
    if any(word in title_lower for word in ['manager', 'director', 'executive', 'chief', 'head', 'lead', 'supervisor']):
        return 'leadership'
    
    # Technical/Engineering indicators
    elif any(word in title_lower for word in ['engineer', 'technician', 'mechanic', 'electrician', 'maintenance', 'technical']):
        return 'technical'
    
    # Healthcare indicators
    elif any(word in title_lower for word in ['doctor', 'nurse', 'medical', 'physician', 'surgeon', 'pharmacist', 'health']):
        return 'healthcare'
    
    # Education indicators
    elif any(word in title_lower for word in ['teacher', 'professor', 'education', 'lecturer', 'tutor']):
        return 'education'
    
    # Financial indicators
    elif any(word in title_lower for word in ['accountant', 'financial', 'bank', 'cashier', 'auditor']):
        return 'financial'
    
    # Sales/Marketing indicators
    elif any(word in title_lower for word in ['sales', 'marketing', 'agent', 'representative', 'promoter']):
        return 'sales'
    
    # Creative/Design indicators
    elif any(word in title_lower for word in ['designer', 'artist', 'creative', 'writer', 'photographer']):
        return 'creative'
    
    # Production/Manufacturing indicators
    elif any(word in title_lower for word in ['production', 'manufacturing', 'factory', 'maker', 'machine']):
        return 'production'
    
    # Transportation indicators
    elif any(word in title_lower for word in ['driver', 'operator', 'pilot', 'captain', 'transport']):
        return 'transportation'
    
    # Administrative indicators
    elif any(word in title_lower for word in ['assistant', 'clerk', 'secretary', 'administrative', 'official']):
        return 'administrative'
    
    # Legal indicators
    elif any(word in title_lower for word in ['lawyer', 'attorney', 'legal', 'advocate', 'judge']):
        return 'legal'
    
    # Agricultural indicators
    elif any(word in title_lower for word in ['farmer', 'agricultural', 'farm', 'livestock', 'crop']):
        return 'agricultural'
    
    # Research/Science indicators
    elif any(word in title_lower for word in ['scientist', 'researcher', 'physicist', 'chemist', 'biologist', 'astronomer', 'astronomy']):
        return 'research'
    
    # Service indicators
    elif any(word in title_lower for word in ['worker', 'helper', 'attendant', 'guard', 'service']):
        return 'service'
    
    # Default to worker category
    else:
        return 'worker'

def generate_dynamic_prompts(occupation_title):
    """Generate dynamic well-defined prompts for any occupation"""
    category = determine_category(occupation_title)
    domain = extract_domain_from_title(occupation_title)
    
    templates = PROMPT_TEMPLATES.get(category, PROMPT_TEMPLATES['worker'])
    
    # Generate prompts by filling templates
    prompts = []
    for template in templates:
        # Replace placeholders with actual domain
        if '{domain}' in template:
            prompt = template.format(domain=domain)
        elif '{technical_domain}' in template:
            prompt = template.format(technical_domain=domain)
        elif '{service_type}' in template:
            prompt = template.format(service_type=domain)
        elif '{creative_domain}' in template:
            prompt = template.format(creative_domain=domain)
        elif '{education_domain}' in template:
            prompt = template.format(education_domain=domain)
        elif '{healthcare_type}' in template:
            prompt = template.format(healthcare_type=domain)
        elif '{financial_domain}' in template:
            prompt = template.format(financial_domain=domain)
        elif '{product_type}' in template:
            prompt = template.format(product_type=domain)
        elif '{transport_type}' in template:
            prompt = template.format(transport_type=domain)
        elif '{admin_type}' in template:
            prompt = template.format(admin_type=domain)
        elif '{product_service}' in template:
            prompt = template.format(product_service=domain)
        elif '{legal_type}' in template:
            prompt = template.format(legal_type=domain)
        elif '{agri_type}' in template:
            prompt = template.format(agri_type=domain)
        elif '{research_domain}' in template:
            prompt = template.format(research_domain=domain)
        elif '{work_type}' in template:
            prompt = template.format(work_type=domain)
        else:
            prompt = template
        
        prompts.append(prompt)
    
    return prompts

# ── P.I.G.S. v3 — Query Specificity + Result Diversity ──────────────────────────

# Stop words for specificity scoring
_PIGS_STOP_WORDS = {
    'i','me','my','we','us','you','he','she','it','they',
    'am','is','are','was','were','be','been','being',
    'have','has','had','do','does','did','will','would',
    'shall','should','can','could','may','might','must',
    'a','an','the','and','but','or','nor','so','yet',
    'of','at','by','for','with','about','to','from',
    'in','on','up','out','over','into','that','this',
    'who','what','where','when','how','which','as','if',
    'then','than','no','not','also','just','very','too',
    'own','same','such','both','each','some','any','all',
    'type','kind','sort','related','person','people',
    'one','two','three','make','made','get','got',
}

# Action verbs that signal a focused occupational description
_ACTION_VERBS = {
    'repair','repairs','fix','fixes','maintain','maintains','service','services','restore','restores',
    'teach','teaches','train','trains','educate','educates','instruct','instructs','tutor','tutors',
    'build','builds','construct','constructs','design','designs','create','creates',
    'develop','develops','install','installs','manufacture','manufactures','assemble','assembles',
    'manage','manages','supervise','supervises','lead','leads','direct','directs',
    'coordinate','coordinates','oversee','oversees','administer','administers',
    'drive','drives','operate','operates','pilot','pilots','run','runs','control','controls',
    'treat','treats','diagnose','diagnoses','prescribe','prescribes','nurse','nurses','care','cares',
    'sell','sells','market','markets','promote','promotes','advise','advises',
    'research','researches','analyze','analyzes','analyse','analyses',
    'study','studies','investigate','investigates','test','tests','inspect','inspects',
    'cook','cooks','prepare','prepares','bake','bakes',
    'guard','guards','protect','protects','secure','secures','monitor','monitors',
    'audit','audits','review','reviews','survey','surveys',
    'farm','farms','grow','grows','harvest','harvests','cultivate','cultivates',
    'write','writes','translate','translates','draft','drafts','edit','edits',
    'program','programs','code','codes','debug','debugs',
    'plan','plans','schedule','schedules','organize','organizes',
}

# Broad single-word concepts that are never occupation-specific
_BROAD_SINGLE_CONCEPTS = {
    'star','stars','space','water','fire','earth','air','light','energy','power',
    'science','nature','environment','climate','weather','sun','moon','planet',
    'machine','machines','computer','computers','software','hardware','internet',
    'data','information','network','system','systems','technology','digital',
    'car','cars','vehicle','vehicles','engine','engines','robot','robots',
    'food','foods','plant','plants','animal','animals','fish','bird','birds',
    'hospital','hospitals','school','schools','bank','banks','office','offices',
    'government','military','police','court','law','legal',
    'money','finance','economy','market','business','trade','commerce',
    'art','music','film','media','sport','sports','game','games',
    'oil','gas','mine','mining','chemical','chemicals','metal','metals',
    'work','field','industry','sector','area','department',
    'service','services','support','management','administration',
    'help','hire','need','find','search','looking',
}

def _score_query_specificity(query):
    """
    Returns a specificity score 0.0–1.0 based on pure content analysis.
    """
    words = re.sub(r"[^a-z0-9\s]", "", query.lower()).split()
    meaningful = [w for w in words if w not in _PIGS_STOP_WORDS and len(w) > 2]

    score = 0.0

    if len(meaningful) >= 4:
        score += 0.50
    elif len(meaningful) >= 3:
        score += 0.32
    elif len(meaningful) >= 2:
        score += 0.18

    if any(w in _ACTION_VERBS for w in words):
        score += 0.30

    if len(meaningful) <= 1 and meaningful and meaningful[0] in _BROAD_SINGLE_CONCEPTS:
        score -= 0.20

    return max(0.0, min(score, 1.0))

def _compute_result_diversity(top_results):
    """
    Returns diversity score 0.0–1.0 based on NCO division spread.
    """
    divisions = []
    for r in top_results[:5]:
        d = r.get("details", {}) or {}
        div = str(d.get("division", "")).strip()
        if div:
            divisions.append(div)

    if not divisions:
        return 0.5

    unique_divs = len(set(divisions))
    total = len(divisions)
    return min(unique_divs / max(total, 1), 1.0)

def _build_dynamic_suggestions(top_results):
    """
    Generates diverse, human-readable occupation title suggestions.
    """
    suggestions = []
    seen_groups = set()
    for r in top_results[:6]:
        d = r.get("details", {}) or {}
        group = str(d.get("group", "")).strip()
        title = str(r.get("occupation_title", "")).strip()
        if not title:
            continue
        if group and group not in seen_groups:
            suggestions.append(title)
            seen_groups.add(group)
        elif not group and title not in suggestions:
            suggestions.append(title)
        if len(suggestions) >= 4:
            break

    if not suggestions:
        suggestions = [
            r.get("occupation_title", "")
            for r in top_results[:4]
            if r.get("occupation_title")
        ]

    return suggestions[:4]

def pigs_v2_analyze(query, top_results):
    """
    PIGS v3 — Query Specificity + Result Diversity.
    """
    query = (query or "").strip()
    if not query or not top_results:
        return None

    specificity = _score_query_specificity(query)
    diversity   = _compute_result_diversity(top_results)
    word_count  = len(query.split())

    if specificity >= 0.45:
        return None

    suggestions = _build_dynamic_suggestions(top_results)

    root = query.lower().strip()
    is_broad = (word_count == 1 and root in _BROAD_SINGLE_CONCEPTS)

    if not is_broad and specificity >= 0.15 and diversity <= 0.40:
        return {
            "state": "FOCUSED",
            "examples": suggestions
        }

    if is_broad or diversity >= 0.55 or specificity < 0.15:
        return {
            "state": "NEEDS_GUIDANCE",
            "tip": "Your search could match many different occupations.",
            "sub_tip": "Try describing what the person does, where they work, or the type of work.",
            "examples": suggestions
        }

    return {
        "state": "FOCUSED",
        "examples": suggestions
    }

def pigs_analyze_prompt(query, top_results):
    """Legacy alias — delegates to pigs_v2_analyze."""
    result = pigs_v2_analyze(query, top_results)
    if result is None:
        return {}, []
    return {}, []

# Test the system with some examples
if __name__ == "__main__":
    test_occupations = [
        "Finance Managers, Others",
        "General Manager, Bank", 
        "Physicist, Mechanics",
        "Automated Optical Inspection Machine Operator",
        "University and College Teacher, Law",
        "Executive Chef",
        "Working Proprietor, Construction",
        "Attorney at Law",
        "Solar Energy System Designer",
        "Agricultural and Forestry Production Managers, Others"
    ]
    
    print("Testing Dynamic Prompt Generation:")
    print("=" * 50)
    
    for occupation in test_occupations:
        print(f"\nOccupation: {occupation}")
        print(f"Category: {determine_category(occupation)}")
        print(f"Domain: {extract_domain_from_title(occupation)}")
        prompts = generate_dynamic_prompts(occupation)
        for i, prompt in enumerate(prompts, 1):
            print(f"  {i}. {prompt}")
        print()
