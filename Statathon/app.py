from flask import Flask, render_template, request, jsonify
from process import search_jobs # Import our modified function
import json

app = Flask(__name__)

# Route to serve the main HTML page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle search queries from the frontend
@app.route('/search', methods=['POST'])
def search():
    try:
        # Get the query from the request
        data = request.get_json()
        query = data.get('query', '')

        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400

        # Use our search function to get results
        # The function now returns a dictionary, which we pass directly to the frontend
        search_data = search_jobs(query, top_k=10) 

        # Return the results as JSON
        return jsonify(search_data)
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)