import os
import time
import json
import base64
import logging
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory

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
        
        # Add image URLs to the result
        image_urls = []
        for image_path in saved_images:
            filename = image_path.replace('raw/', '')
            image_url = url_for('serve_raw_file', filename=filename, _external=True)
            image_urls.append(image_url)
            
        # Add product details to the result
        result['product_id'] = timestamp  # Use timestamp as a unique identifier
        result['product_name'] = product_data['name']
        result['category'] = product_data['category']
        result['price'] = product_data['price']
        result['image_urls'] = image_urls
        
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
        
@app.route('/raw/<path:filename>')
def serve_raw_file(filename):
    """Serve files from the raw directory."""
    return send_from_directory('raw', filename)

@app.route('/response/<path:filename>')
def serve_response_file(filename):
    """Serve files from the response directory."""
    return send_from_directory('response', filename)

@app.route('/catalog')
def catalog():
    """Display the catalog of all products."""
    # Get search/filter parameters
    query = request.args.get('q', '')
    category_filter = request.args.get('category')
    color_filter = request.args.get('color')
    material_filter = request.args.get('material')
    style_filter = request.args.get('style')
    audience_filter = request.args.get('audience')
    sort_by = request.args.get('sort', 'newest')
    
    # Load all products from response files
    products = []
    try:
        # Get all JSON files in the response directory
        response_files = os.listdir('response')
        response_files = [f for f in response_files if f.endswith('.json')]
        
        for filename in response_files:
            file_path = os.path.join('response', filename)
            try:
                with open(file_path, 'r') as f:
                    product_data = json.load(f)
                    if 'product_id' not in product_data:
                        # Add product_id if not present (for backward compatibility)
                        product_id = filename.replace('.json', '')
                        product_data['product_id'] = product_id
                    products.append(product_data)
            except Exception as e:
                logging.error(f"Error loading {file_path}: {str(e)}")
                continue
    except Exception as e:
        logging.error(f"Error listing response directory: {str(e)}")
    
    # Extract filter options from all products
    all_categories = set()
    all_colors = set()
    all_materials = set()
    all_styles = set()
    all_audiences = set()
    
    for product in products:
        # Categories
        if 'category' in product:
            all_categories.add(product['category'])
        
        # Extract keywords from tags, specifications, and descriptions
        all_tags = (product.get('tags', []) + 
                   product.get('specifications', []) + 
                   product.get('seo_keywords', []))
        
        # Colors
        color_keywords = ['red', 'blue', 'green', 'yellow', 'black', 'white', 
                         'orange', 'purple', 'pink', 'brown', 'gray', 'grey', 
                         'silver', 'gold', 'beige', 'navy', 'teal']
        for tag in all_tags:
            for color in color_keywords:
                if color.lower() in tag.lower():
                    all_colors.add(color.title())
        
        # Materials
        material_keywords = ['cotton', 'polyester', 'wool', 'leather', 'silk', 
                           'nylon', 'linen', 'plastic', 'metal', 'wood', 
                           'glass', 'ceramic', 'rubber', 'carbon fiber', 'canvas']
        for tag in all_tags:
            for material in material_keywords:
                if material.lower() in tag.lower():
                    all_materials.add(material.title())
        
        # Styles
        style_keywords = ['casual', 'formal', 'sporty', 'vintage', 'modern', 
                         'classic', 'elegant', 'bohemian', 'minimalist', 
                         'retro', 'contemporary', 'urban', 'luxury']
        for tag in all_tags:
            for style in style_keywords:
                if style.lower() in tag.lower():
                    all_styles.add(style.title())
        
        # Target Audiences
        if 'target_audience' in product:
            for audience in product.get('target_audience', []):
                all_audiences.add(audience)
    
    # Apply filters
    filtered_products = []
    for product in products:
        # Skip products that don't match the search query
        if query and query.lower() not in json.dumps(product).lower():
            continue
        
        # Skip products that don't match the category filter
        if category_filter and product.get('category') != category_filter:
            continue
        
        # Skip products that don't match the color filter
        if color_filter:
            color_match = False
            for tag in (product.get('tags', []) + product.get('specifications', []) + product.get('seo_keywords', [])):
                if color_filter.lower() in tag.lower():
                    color_match = True
                    break
            if not color_match:
                continue
        
        # Skip products that don't match the material filter
        if material_filter:
            material_match = False
            for tag in (product.get('tags', []) + product.get('specifications', []) + product.get('seo_keywords', [])):
                if material_filter.lower() in tag.lower():
                    material_match = True
                    break
            if not material_match:
                continue
        
        # Skip products that don't match the style filter
        if style_filter:
            style_match = False
            for tag in (product.get('tags', []) + product.get('specifications', []) + product.get('seo_keywords', [])):
                if style_filter.lower() in tag.lower():
                    style_match = True
                    break
            if not style_match:
                continue
        
        # Skip products that don't match the audience filter
        if audience_filter:
            audience_match = False
            for audience in product.get('target_audience', []):
                if audience_filter.lower() in audience.lower():
                    audience_match = True
                    break
            if not audience_match:
                continue
        
        # Add product to filtered list
        filtered_products.append(product)
    
    # Sort products
    if sort_by == 'name_asc':
        filtered_products.sort(key=lambda p: p.get('product_name', '').lower())
    elif sort_by == 'name_desc':
        filtered_products.sort(key=lambda p: p.get('product_name', '').lower(), reverse=True)
    else:  # Default to newest
        filtered_products.sort(key=lambda p: p.get('product_id', ''), reverse=True)
    
    # Prepare active filters display
    active_filters = {}
    if category_filter:
        active_filters['Category'] = category_filter
    if color_filter:
        active_filters['Color'] = color_filter
    if material_filter:
        active_filters['Material'] = material_filter
    if style_filter:
        active_filters['Style'] = style_filter
    if audience_filter:
        active_filters['Audience'] = audience_filter
    
    # Check if any filters are active
    any_filters_active = bool(query or active_filters)
    
    # Prepare filter options for display
    filters = {
        'categories': sorted(list(all_categories)),
        'colors': sorted(list(all_colors)),
        'materials': sorted(list(all_materials)),
        'styles': sorted(list(all_styles)),
        'audiences': sorted(list(all_audiences))
    }
    
    return render_template('catalog.html', 
                          products=filtered_products,
                          filters=filters,
                          active_filters=active_filters,
                          any_filters_active=any_filters_active,
                          request=request)

@app.route('/product/<product_id>')
def view_product(product_id):
    """View a specific product."""
    try:
        # Load product data from JSON file
        response_file = f"response/{product_id}.json"
        if not os.path.exists(response_file):
            flash('Product not found', 'error')
            return redirect(url_for('catalog'))
        
        with open(response_file, 'r') as f:
            product = json.load(f)
        
        # Add product_id if not present
        if 'product_id' not in product:
            product['product_id'] = product_id
        
        # Update image URLs if available
        if 'image_paths' in product:
            product['image_urls'] = [url_for('serve_raw_file', filename=os.path.basename(img_path)) 
                                   for img_path in product.get('image_paths', [])]
        
        return render_template('view_product.html', product=product)
    except Exception as e:
        logging.error(f"Error loading product {product_id}: {str(e)}")
        flash(f'Error loading product: {str(e)}', 'error')
        return redirect(url_for('catalog'))


@app.route('/update_product/<product_id>', methods=['POST'])
def update_product(product_id):
    """Update a product's information and save changes back to JSON file."""
    try:
        # Load product data from JSON file
        response_file = f"response/{product_id}.json"
        if not os.path.exists(response_file):
            flash('Product not found', 'error')
            return redirect(url_for('catalog'))
        
        with open(response_file, 'r') as f:
            product_data = json.load(f)
        
        # Update fields from the form
        product_data['product_name'] = request.form.get('product_name', product_data.get('product_name', ''))
        product_data['category'] = request.form.get('category', product_data.get('category', ''))
        product_data['price'] = request.form.get('price', product_data.get('price', ''))
        product_data['short_description'] = request.form.get('short_description', product_data.get('short_description', ''))
        
        # Handle tags - these come as a list from the form
        tags = request.form.getlist('tags')
        if tags:
            product_data['tags'] = tags
        
        # Handle target audience - these come as a list from the form
        target_audience = request.form.getlist('target_audience')
        if target_audience:
            product_data['target_audience'] = target_audience
        
        # Save the updated product data back to the file
        with open(response_file, 'w') as f:
            json.dump(product_data, f, indent=4)
        
        flash('Product information updated successfully.', 'success')
        return redirect(url_for('view_product', product_id=product_id))
    
    except Exception as e:
        logging.error(f"Error updating product {product_id}: {str(e)}")
        flash(f'Error updating product: {str(e)}', 'error')
        return redirect(url_for('view_product', product_id=product_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
