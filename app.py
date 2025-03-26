import os
import time
import json
import base64
import logging
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-dev")

# Create required directories if they don't exist
os.makedirs('raw', exist_ok=True)
os.makedirs('response', exist_ok=True)

# Import OpenAI helper after app initialization
from utils.openai_helper import analyze_product

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_IMAGES = 5
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Render the main page of the application."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_product():
    """Handle product information and image uploads."""
    try:
        # Extract form data
        product_name = request.form.get('product_name', '')
        product_category = request.form.get('product_category', '')
        product_price = request.form.get('product_price', '')
        
        # Validate form data
        if not product_name or not product_category or not product_price:
            flash('Please fill in all product details', 'error')
            return redirect(url_for('index'))
        
        # Check if files are provided
        if 'product_images' not in request.files:
            flash('No files provided', 'error')
            return redirect(url_for('index'))
        
        files = request.files.getlist('product_images')
        
        # Validate file count
        if len(files) < 1 or len(files) > MAX_IMAGES:
            flash(f'Please upload between 1 and {MAX_IMAGES} images', 'error')
            return redirect(url_for('index'))
        
        # Process each file
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        saved_images = []
        base64_images = []
        
        for file in files:
            if file and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    flash(f'File {file.filename} is too large (max 5MB)', 'error')
                    continue
                
                # Save file
                filename = secure_filename(file.filename)
                file_path = os.path.join('raw', f"{timestamp}_{filename}")
                file.save(file_path)
                saved_images.append(file_path)
                
                # Convert to base64 for OpenAI API
                with open(file_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    base64_images.append(base64_image)
        
        if not saved_images:
            flash('No valid images uploaded', 'error')
            return redirect(url_for('index'))
        
        # Prepare product data
        product_data = {
            'name': product_name,
            'category': product_category,
            'price': product_price,
            'images': saved_images
        }
        
        # Call OpenAI API for analysis
        result = analyze_product(product_data, base64_images)
        
        # Save response to JSON file
        response_file = f"response/{timestamp}.json"
        with open(response_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Store result in session
        session['product_result'] = {
            'data': product_data,
            'result': result,
            'timestamp': timestamp
        }
        
        return redirect(url_for('result'))
    
    except Exception as e:
        logging.error(f"Error processing upload: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/result')
def result():
    """Display the result of product analysis."""
    product_result = session.get('product_result')
    if not product_result:
        flash('No product data available', 'error')
        return redirect(url_for('index'))
    
    return render_template('result.html', 
                          product_data=product_result['data'],
                          result=product_result['result'],
                          timestamp=product_result['timestamp'])

@app.route('/download/<timestamp>')
def download(timestamp):
    """Return the JSON response for download."""
    try:
        response_file = f"response/{timestamp}.json"
        if not os.path.exists(response_file):
            return jsonify({'error': 'File not found'}), 404
        
        with open(response_file, 'r') as f:
            result = json.load(f)
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error downloading result: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
