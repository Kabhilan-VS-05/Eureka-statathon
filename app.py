from flask import Flask, render_template, request, jsonify
import sys
import os
import json
from datetime import datetime, timezone

# Add scripts directory to path to import searchapp
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))
# Add utils directory to path to import prompt system
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Load search module once at startup for performance
import importlib.util
spec = importlib.util.spec_from_file_location("searchapp", os.path.join(os.path.dirname(__file__), 'scripts', '06_searchapp.py'))
if spec and spec.loader:
    search_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(search_module)
else:
    raise RuntimeError("Failed to load search module")

# Import dynamic prompt generation system
from dynamic_prompts import generate_dynamic_prompts
# Import translation service
from translation_service import translation_service

app = Flask(__name__)

PROMPT_HISTORY_PATH = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')


def _ensure_prompt_history_file():
    os.makedirs(os.path.dirname(PROMPT_HISTORY_PATH), exist_ok=True)
    if not os.path.exists(PROMPT_HISTORY_PATH):
        with open(PROMPT_HISTORY_PATH, 'w', encoding='utf-8') as f:
            f.write('[]')


def _read_prompt_history():
    _ensure_prompt_history_file()
    try:
        with open(PROMPT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_prompt_history(history):
    os.makedirs(os.path.dirname(PROMPT_HISTORY_PATH), exist_ok=True)
    tmp_path = PROMPT_HISTORY_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, PROMPT_HISTORY_PATH)


def _append_prompt_history_entry(entry):
    history = _read_prompt_history()
    history.append(entry)
    if len(history) > 5000:
        history = history[-5000:]
    _write_prompt_history(history)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_jobs():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400
    query = data.get('query', '').strip()
    user_language = data.get('user_language', None)  # User's confirmed language
    
    try:
        if query:
            # Check for language ambiguity
            detected_lang, is_ambiguous, alternative_lang = translation_service.detect_language_with_confidence(query)
            language_ambiguity = None
            
            if is_ambiguous and not user_language:
                # If ambiguous and user hasn't confirmed, ask user to select
                language_ambiguity = {
                    "is_ambiguous": True,
                    "primary_lang": detected_lang,
                    "alternative_lang": alternative_lang,
                    "message": f"Is this {detected_lang.upper()} or {alternative_lang.upper()}?"
                }
                # Return search with English results first as preview
                translated_query = translation_service.translate_with_lingua(query, source_lang="auto", target_lang="en")
            elif user_language:
                # User confirmed language, use it
                detected_lang = user_language
                translated_query = translation_service.translate_with_lingua(query, source_lang=user_language, target_lang="en")
            else:
                # No ambiguity, proceed normally
                translated_query = translation_service.translate_with_lingua(query, source_lang="auto", target_lang="en")
            
            # Check if translation occurred
            translation_notice = None
            if translated_query.lower() != query.lower():
                translation_notice = {
                    "original": query,
                    "translated": translated_query,
                    "message": f"Query translated from original text"
                }
            
            # Use the search function for specific queries
            results = search_module.search(translated_query)

            try:
                top = results[0] if results else {}
                _append_prompt_history_entry({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "query": query,
                    "translated_query": translated_query,
                    "was_translated": translated_query.lower() != query.lower(),
                    "occupation_title": top.get('occupation_title', ''),
                    "nco_code": top.get('nco_2015', top.get('nco_code', '')),
                    "client_ip": request.remote_addr
                })
            except Exception:
                pass

            # Generate contextual suggestion examples
            suggestion = None
            if len(results) >= 2:
                top_score = results[0].get('final_score', 0)
                next_score = results[1].get('final_score', 0)
                q_lower = translated_query.lower()
                # Check if query directly mentions a job title from top results
                top_title = results[0].get('occupation_title', '').lower()
                is_direct_job_mention = any(word in top_title for word in q_lower.split()) if top_title else False
                
                # Skip suggestions if query directly mentions a job title
                if not is_direct_job_mention:
                    # For any ambiguous or low-confidence query, use dynamic prompt generation
                    if (top_score < 0.6 and abs(top_score - next_score) < 0.05) or top_score < 0.5:
                        occupation_title = results[0].get('occupation_title', 'professional')
                        prompts = generate_dynamic_prompts(occupation_title)
                        suggestion = "Well-defined prompt examples:<br>" + "<br>".join([f"· \"{prompt}\"" for prompt in prompts])
            return jsonify({
                "results": results, 
                "suggestion": suggestion, 
                "translation_notice": translation_notice,
                "language_ambiguity": language_ambiguity
            })
        else:
            # Use the get_all_jobs function for empty queries
            results = search_module.get_all_jobs()
            return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/translate', methods=['POST'])
def translate_text():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400
    
    text = data.get('text', '').strip()
    source_lang = data.get('source_lang', 'auto')
    target_lang = data.get('target_lang', 'en')
    preferred_service = data.get('preferred_service', 'lingua')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        translated_text = translation_service.translate(
            text, source_lang, target_lang, preferred_service
        )
        return jsonify({
            "original_text": text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "service_used": preferred_service
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/languages', methods=['GET'])
def get_supported_languages():
    try:
        languages = translation_service.get_supported_languages()
        return jsonify({"languages": languages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Admin Dashboard Routes
@app.route('/admin')
@app.route('/admin/')
def admin_dashboard():
    try:
        return render_template('admin/dashboard.html')
    except Exception as e:
        return f"Template error: {str(e)}", 500

@app.route('/admin/test')
def admin_test():
    return "Admin route working!"


@app.route('/admin/api/prompt-history', methods=['GET'])
def get_prompt_history():
    try:
        occupation_title = request.args.get('occupation_title', '').strip()
        try:
            limit = int(request.args.get('limit', '100'))
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 500))

        history = _read_prompt_history()
        history = list(reversed(history))
        if occupation_title:
            history = [h for h in history if h.get('occupation_title') == occupation_title]
        return jsonify(history[:limit])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/occupations', methods=['GET'])
def get_occupations():
    try:
        # Load metadata
        metadata_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_metadata.json')
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Load documents for additional info
        documents_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_documents.json')
        with open(documents_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        
        # Combine data
        occupations = []
        for i, meta in enumerate(metadata):
            if i < len(documents):
                doc = documents[i]
                # Parse document to extract hierarchy info
                lines = doc.split('\n')
                division = ''
                family = ''
                description = ''
                
                for line in lines:
                    if line.startswith('Division:'):
                        division = line.replace('Division:', '').strip()
                    elif line.startswith('Family:'):
                        family = line.replace('Family:', '').strip()
                    elif line.startswith('Occupation Description:'):
                        description = line.replace('Occupation Description:', '').strip()
                
                occupations.append({
                    'row_id': meta['row_id'],
                    'nco_code': meta['nco_2015'],
                    'occupation_title': meta['occupation_title'],
                    'division': division,
                    'family': family,
                    'description': description
                })
        
        return jsonify(occupations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/occupations/<int:row_id>', methods=['PUT'])
def update_occupation(row_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Load current metadata
        metadata_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_metadata.json')
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Load current documents
        documents_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_documents.json')
        with open(documents_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        
        # Find and update the occupation
        occupation_found = False
        for i, meta in enumerate(metadata):
            if meta['row_id'] == row_id:
                # Update metadata
                meta['nco_2015'] = data['nco_code']
                meta['occupation_title'] = data['occupation_title']
                
                # Update document if exists
                if i < len(documents):
                    doc = documents[i]
                    lines = doc.split('\n')
                    
                    # Update specific lines
                    for j, line in enumerate(lines):
                        if line.startswith('Occupation Title:'):
                            lines[j] = f"Occupation Title: {data['occupation_title']}"
                        elif line.startswith('NCO 2015 Code:'):
                            lines[j] = f"NCO 2015 Code: {data['nco_code']}"
                        elif line.startswith('Division:'):
                            lines[j] = f"Division: {data['division']}"
                        elif line.startswith('Family:'):
                            lines[j] = f"Family: {data['family']}"
                        elif line.startswith('Occupation Description:'):
                            lines[j] = f"Occupation Description:\n{data['description']}"
                    
                    documents[i] = '\n'.join(lines)
                
                occupation_found = True
                break
        
        if not occupation_found:
            return jsonify({"success": False, "error": "Occupation not found"}), 404
        
        # Save updated files
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        with open(documents_path, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "message": "Occupation updated successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/occupations', methods=['POST'])
def add_occupation():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Load current metadata
        metadata_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_metadata.json')
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Load current documents
        documents_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_documents.json')
        with open(documents_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        
        # Generate new row_id
        new_row_id = max([meta['row_id'] for meta in metadata]) + 1 if metadata else 0
        
        # Create new metadata entry
        new_meta = {
            "row_id": new_row_id,
            "nco_2015": data['nco_code'],
            "occupation_title": data['occupation_title']
        }
        metadata.append(new_meta)
        
        # Create new document entry
        new_doc = f"""Occupation Title: {data['occupation_title']}
NCO 2015 Code: {data['nco_code']}

Hierarchy:
Division: {data['division']}
Sub Division: 
Group: 
Family: {data['family']}

Occupation Description:
{data['description']}

Family Description:
This family includes closely related job roles centered around {data['family']}, with shared responsibilities, tools, and work objectives.

Group Description:
This group consists of related occupations that perform similar tasks, share common skill sets, and contribute to organizational functions."""
        
        documents.append(new_doc)
        
        # Save updated files
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        with open(documents_path, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "message": "Occupation added successfully", "row_id": new_row_id})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/occupations/<int:row_id>', methods=['DELETE'])
def delete_occupation(row_id):
    try:
        # Load current metadata
        metadata_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_metadata.json')
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Load current documents
        documents_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_documents.json')
        with open(documents_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        
        # Find and remove the occupation
        occupation_found = False
        new_metadata = []
        new_documents = []
        
        for i, meta in enumerate(metadata):
            if meta['row_id'] != row_id:
                new_metadata.append(meta)
                if i < len(documents):
                    new_documents.append(documents[i])
            else:
                occupation_found = True
        
        if not occupation_found:
            return jsonify({"success": False, "error": "Occupation not found"}), 404
        
        # Save updated files
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(new_metadata, f, indent=2, ensure_ascii=False)
        
        with open(documents_path, 'w', encoding='utf-8') as f:
            json.dump(new_documents, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "message": "Occupation deleted successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
