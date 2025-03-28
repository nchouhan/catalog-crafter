import os
import time
import json
import base64
import logging
import subprocess
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
os.makedirs('temp', exist_ok=True)

# Import OpenAI helpers after app initialization
from utils.openai_helper import analyze_product, generate_persona_descriptions
from utils.similar_products import get_similar_products, check_duplicate_product
from utils.video_generator import generate_video_openai, get_video_for_product

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_IMAGES = 5
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Render the main page of the application."""
    # Clear any stale flash messages when first loading the page
    session.pop('_flashes', None)
    
    # Check if OpenAI API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        flash('OpenAI API key is not set. Please add your API key to the .env file as OPENAI_API_KEY=your_key_here', 'error')
    else:
        # Show performance tip
        flash('Performance tip: For best results, upload 1-6 images per product. Additional images will be saved but only the first 6 will be used for AI analysis.', 'info')
    
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
                
                # Convert to base64 for OpenAI API (limit to first 6 images)
                if len(base64_images) < 6:  # Process up to 6 images for OpenAI API
                    with open(file_path, "rb") as image_file:
                        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                        base64_images.append(base64_image)
        
        if not saved_images:
            flash('No valid images uploaded', 'error')
            return redirect(url_for('index'))
            
        # Check for potential duplicate products (unless explicitly ignored)
        ignore_duplicates = request.form.get('ignore_duplicates') == 'true'
        if not ignore_duplicates:
            # Check if OpenAI API key is set
            if not os.environ.get("OPENAI_API_KEY"):
                logging.warning("OPENAI_API_KEY is not set, skipping duplicate product check")
                # Continue without duplicate check
                is_duplicate = False
                potential_duplicates = []
            else:
                try:
                    # Check for duplicate products with debug enabled
                    logging.info("Checking for duplicate products")
                    is_duplicate, potential_duplicates = check_duplicate_product(saved_images, threshold=0.85, debug=True)
                    
                    if is_duplicate and potential_duplicates:
                        logging.info(f"Found {len(potential_duplicates)} potential duplicate products")
                        
                        # Process thumbnail URLs for display
                        for i, dup in enumerate(potential_duplicates):
                            logging.info(f"Processing potential duplicate {i+1}/{len(potential_duplicates)}: {dup.get('product_id')} - {dup.get('product_name')}")
                            
                            # Get thumbnail for display
                            if 'thumbnail' in dup:
                                logging.info(f"Found thumbnail: {dup['thumbnail']}")
                                # Create URL from the thumbnail path
                                filename = os.path.basename(dup['thumbnail'])
                                dup['thumbnail_url'] = url_for('serve_raw_file', filename=filename)
                                logging.info(f"Set thumbnail_url to: {dup['thumbnail_url']}")
                            else:
                                logging.warning(f"No thumbnail found for duplicate product: {dup.get('product_id')}")
                                
                                # Try to find an image as fallback
                                try:
                                    product_path = f"response/{dup.get('product_id')}.json"
                                    if os.path.exists(product_path):
                                        with open(product_path, 'r') as f:
                                            product_data = json.load(f)
                                            
                                        # Try to get an image path
                                        from utils.similar_products import get_product_image_path
                                        img_path = get_product_image_path(product_data, debug=True)
                                        if img_path and os.path.exists(img_path):
                                            filename = os.path.basename(img_path)
                                            dup['thumbnail_url'] = url_for('serve_raw_file', filename=filename)
                                            logging.info(f"Found fallback image: {dup['thumbnail_url']}")
                                except Exception as e:
                                    logging.error(f"Error finding fallback image: {str(e)}")
                        
                        # Save potential duplicates in session for display
                        session['potential_duplicates'] = potential_duplicates
                        # Pass the form data back to allow re-submission
                        flash('We found potentially similar products in the catalog. Please check if your product already exists.', 'warning')
                        return render_template('index.html', 
                                             potential_duplicates=potential_duplicates,
                                             form_data={
                                                 'product_name': product_name,
                                                 'product_category': product_category,
                                                 'product_price': product_price
                                             })
                except Exception as e:
                    logging.error(f"Error in duplicate product check: {str(e)}")
                    import traceback
                    logging.error(traceback.format_exc())
                    # Continue with product creation even if duplicate check fails
                    flash('An error occurred while checking for similar products. Proceeding with product creation.', 'info')
        
        # Prepare product data
        product_data = {
            'name': product_name,
            'category': product_category,
            'price': product_price,
            'images': saved_images
        }
        
        # Check if OpenAI API key is available
        if not os.environ.get("OPENAI_API_KEY"):
            logging.warning("OPENAI_API_KEY is not set, skipping product analysis")
            flash("OpenAI API key is missing. Please set OPENAI_API_KEY in your .env file to enable AI features.", 'error')
            # Create a minimal result without AI enhancements
            result = {
                "short_description": f"{product_data['name']} - {product_data['category']}",
                "detailed_description": f"A {product_data['category']} product named {product_data['name']} priced at {product_data['price']}.",
                "specifications": [],
                "tags": [product_data['category']],
                "seo_keywords": [product_data['name'], product_data['category']],
                "target_audience": [],
                "colors": [],
                "materials": [],
                "styles": [],
                "persona_descriptions": {
                    "athleisure_enthusiast": "N/A",
                    "performance_athlete": "N/A",
                    "value_conscious_buyer": "N/A"
                },
                "error": "OpenAI API key is missing"
            }
        else:
            # Call OpenAI API for analysis
            try:
                # Double-check the OpenAI API key again before making the API call
                if not os.environ.get("OPENAI_API_KEY"):
                    raise ValueError("OpenAI API key is missing")
                
                logging.info("Calling OpenAI API to analyze product")
                
                # Set a timeout for the analyze_product function
                start_time = time.time()
                result = analyze_product(product_data, base64_images)
                end_time = time.time()
                
                logging.info(f"OpenAI API call completed in {end_time - start_time:.2f} seconds")
                
                # Check if there was an API error
                if 'error' in result:
                    logging.warning(f"OpenAI API returned an error: {result['error']}")
                    
                    if "API request timed out" in str(result['error']):
                        flash("The request timed out. Please try again with fewer or smaller images.", 'error')
                    elif "API key" in str(result['error']).lower():
                        flash("OpenAI API key validation failed. Please check your API key.", 'error')
                    else:
                        flash(f"Note: Some AI-generated content may be limited due to an API issue: {result['error']}", 'warning')
                else:
                    logging.info("Successfully analyzed product with OpenAI API")
            except ValueError as e:
                logging.error(f"API key error: {str(e)}")
                result = {
                    "short_description": f"{product_data['name']} - {product_data['category']}",
                    "detailed_description": f"A {product_data['category']} product named {product_data['name']} priced at {product_data['price']}.",
                    "specifications": [],
                    "tags": [product_data['category']],
                    "seo_keywords": [product_data['name'], product_data['category']],
                    "target_audience": [],
                    "colors": [],
                    "materials": [],
                    "styles": [],
                    "persona_descriptions": {
                        "athleisure_enthusiast": "N/A",
                        "performance_athlete": "N/A",
                        "value_conscious_buyer": "N/A"
                    },
                    "error": str(e)
                }
                flash("OpenAI API key is missing or invalid. Please add a valid key to your .env file.", 'error')
            except Exception as e:
                logging.error(f"Failed to analyze product: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
                # Create a minimal result to continue
                result = {
                    "short_description": f"{product_data['name']} - {product_data['category']}",
                    "detailed_description": f"A {product_data['category']} product named {product_data['name']} priced at {product_data['price']}.",
                    "specifications": [],
                    "tags": [product_data['category']],
                    "seo_keywords": [product_data['name'], product_data['category']],
                    "target_audience": [],
                    "colors": [],
                    "materials": [],
                    "styles": [],
                    "persona_descriptions": {
                        "athleisure_enthusiast": "N/A",
                        "performance_athlete": "N/A",
                        "value_conscious_buyer": "N/A"
                    },
                    "error": str(e)
                }
                flash("Unable to generate AI descriptions. Basic product information has been saved.", 'error')
        
        # Add image URLs to the result
        image_urls = []
        for image_path in saved_images:
            filename = image_path.replace('raw/', '')
            image_url = url_for('serve_raw_file', filename=filename)
            image_urls.append(image_url)
            
        # Add product details to the result
        result['product_id'] = timestamp  # Use timestamp as a unique identifier
        result['product_name'] = product_data['name']
        result['category'] = product_data['category']
        result['price'] = product_data['price']
        result['image_urls'] = image_urls
        result['creation_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Store the raw image paths for similar product detection
        result['images'] = saved_images
        result['raw_images'] = saved_images  # Store in both formats for compatibility
        
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
    
    # Format product data to match the view_product structure
    product = product_result['result'].copy()
    
    # Clear any stale flash messages to avoid duplicates
    session.pop('_flashes', None)
    
    # Add success message for product creation
    flash('Product created successfully!', 'success')
    
    # Find similar products for the newly created product
    similar_products = []
    try:
        # Check if OpenAI API key is set
        if not os.environ.get("OPENAI_API_KEY"):
            logging.warning("OPENAI_API_KEY is not set, skipping similar products")
            # No need to flash an error, just don't show similar products
        else:
            # Get similar products with debug mode enabled
            logging.info(f"Finding similar products for new product: {product['product_id']}")
            similar_products = get_similar_products(product['product_id'], threshold=0.3, max_results=4, debug=True)
            
            # Convert raw image paths to URLs
            valid_similar_products = []
            for similar in similar_products:
                has_valid_image = False
                if 'thumbnail' in similar:
                    thumbnail_path = similar['thumbnail']
                    if os.path.exists(thumbnail_path):
                        filename = os.path.basename(thumbnail_path)
                        similar['thumbnail_url'] = url_for('serve_raw_file', filename=filename)
                        has_valid_image = True
                    else:
                        # Try to find an alternate image
                        try:
                            product_path = f"response/{similar.get('product_id')}.json"
                            if os.path.exists(product_path):
                                with open(product_path, 'r') as f:
                                    product_data = json.load(f)
                                
                                from utils.similar_products import get_product_image_path
                                img_path = get_product_image_path(product_data, debug=False)
                                if img_path and os.path.exists(img_path):
                                    filename = os.path.basename(img_path)
                                    similar['thumbnail_url'] = url_for('serve_raw_file', filename=filename)
                                    has_valid_image = True
                        except Exception as e:
                            logging.error(f"Error finding alternate image: {str(e)}")
                if has_valid_image:
                    valid_similar_products.append(similar)
                    
            # Replace similar_products with only valid ones
            similar_products = valid_similar_products
    except Exception as e:
        logging.error(f"Error finding similar products: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        # Continue even if similar products fail
    
    # Redirect to the view_product page with the product ID
    return redirect(url_for('view_product', product_id=product['product_id']))

@app.route('/download/<timestamp>')
def download(timestamp):
    """Return the JSON response as a downloadable file."""
    try:
        if not os.path.exists("response") or not os.path.isfile(f"response/{timestamp}.json"):
            logging.error(f"File not found: response/{timestamp}.json")
            return jsonify({'error': 'File not found'}), 404
        
        # Use send_from_directory to force file download with attachment header
        return send_from_directory(
            directory="response",
            path=f"{timestamp}.json",
            as_attachment=True,
            download_name=f"product_{timestamp}.json"
        )
    except Exception as e:
        logging.error(f"Error downloading result: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/raw/<path:filename>')
def serve_raw_file(filename):
    """Serve files from the raw directory."""
    logging.info(f"Serving raw file: {filename}")
    
    # Log the full file path for debugging
    full_path = os.path.join('raw', filename)
    logging.info(f"Full file path: {full_path}")
    logging.info(f"File exists: {os.path.exists(full_path)}")
    
    # Add debug info to check all files in raw directory
    all_raw_files = os.listdir('raw')
    logging.info(f"Raw directory files (sample): {all_raw_files[:5]}")
    
    # Check if file exists, if not try to find a match with a different case
    if not os.path.exists(full_path):
        possible_match = next((f for f in all_raw_files if f.lower() == filename.lower()), None)
        if possible_match:
            logging.info(f"Found case-insensitive match: {possible_match}")
            filename = possible_match
    
    try:
        # Set CORS headers to allow the image to be loaded from any origin
        response = send_from_directory('raw', filename)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        logging.info(f"Successfully served raw file: {filename}")
        return response
    except Exception as e:
        logging.error(f"Error serving raw file {filename}: {str(e)}")
        # Return a 404 error with more information
        return f"File not found: {filename}. Error: {str(e)}", 404

@app.route('/generate_video/<product_id>', methods=['POST'])
def generate_video(product_id):
    """Generate a product video from images."""
    try:
        # Load product data from JSON file
        response_file = f"response/{product_id}.json"
        if not os.path.exists(response_file):
            return jsonify({"success": False, "error": "Product not found"}), 404

        with open(response_file, 'r') as f:
            product_data = json.load(f)
            
        # Check for existing video
        video_filename = f"{product_id}_video.mp4"
        video_path = os.path.join('raw', video_filename)
        
        # If there's an existing video, remove it so we can regenerate
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
                logging.info(f"Removed existing video: {video_path}")
            except Exception as remove_err:
                logging.error(f"Error removing existing video: {str(remove_err)}")
        
        # Generate video
        logging.info(f"Generating video for product: {product_id}")
        
        try:
            # Call the video generation function with a timeout
            success, result = generate_video_openai(product_data)
            
            if success:
                # Verify the file is a real video
                try:
                    with open(result, 'rb') as f:
                        header = f.read(12)
                    
                    # Check for MP4 signature ('ftyp')
                    if b'ftyp' in header:
                        # Get just the filename from the video path
                        video_filename = os.path.basename(result)
                        video_url = url_for('serve_raw_file', filename=video_filename)
                        
                        # Return success response with video URL
                        return jsonify({
                            "success": True,
                            "video_url": video_url,
                            "message": "Video generated successfully"
                        })
                    else:
                        # Not a valid MP4 file
                        logging.error(f"Generated file is not a valid MP4: {result}")
                        return jsonify({
                            "success": False,
                            "error": "Failed to generate a valid video. Please try again."
                        }), 500
                except Exception as check_err:
                    logging.error(f"Error checking video file: {str(check_err)}")
                    return jsonify({
                        "success": False,
                        "error": "Error verifying the generated video."
                    }), 500
            else:
                # Return error message
                return jsonify({
                    "success": False,
                    "error": result
                }), 500
        except subprocess.TimeoutExpired:
            logging.error("Video generation process timed out")
            return jsonify({
                "success": False,
                "error": "Video generation took too long. Try with fewer or smaller images."
            }), 500
            
    except Exception as e:
        logging.error(f"Error generating video: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

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
        
        # Debug: Log the product data keys
        logging.info(f"Product data keys for {product_id}: {list(product.keys())}")
        
        # Update image URLs if available - DIRECTLY use /raw/filename format
        if 'image_paths' in product:
            logging.info(f"Found image_paths: {product.get('image_paths')}")
            # Instead of using url_for, directly construct the URL with /raw/ prefix
            product['image_urls'] = []
            for img_path in product.get('image_paths', []):
                filename = os.path.basename(img_path)
                url = f"/raw/{filename}"
                logging.info(f"Converting image path to URL: {img_path} -> {url}")
                product['image_urls'].append(url)
            logging.info(f"Created image_urls: {product['image_urls']}")
        elif 'raw_images' in product:
            logging.info(f"Found raw_images: {product.get('raw_images')}")
            # If raw_images exists but not image_paths, use those instead
            product['image_urls'] = []
            for img_path in product.get('raw_images', []):
                # Make sure we have the right format - should be raw/filename.ext
                if img_path.startswith('raw/'):
                    url = f"/{img_path}"  # Add leading slash
                else:
                    filename = os.path.basename(img_path)
                    url = f"/raw/{filename}"
                logging.info(f"Converting raw image to URL: {img_path} -> {url}")
                product['image_urls'].append(url)
            logging.info(f"Created image_urls from raw_images: {product['image_urls']}")
        elif 'images' in product:
            logging.info(f"Found images: {product.get('images')}")
            # If only the images field exists
            product['image_urls'] = []
            for img_path in product.get('images', []):
                filename = os.path.basename(img_path)
                url = f"/raw/{filename}"
                logging.info(f"Converting image to URL: {img_path} -> {url}")
                product['image_urls'].append(url)
            logging.info(f"Created image_urls from images: {product['image_urls']}")
        
        # Let's check and fix the image URLs to ensure they're properly formatted
        if 'image_urls' in product:
            logging.info(f"Original image URLs for product {product_id}: {product['image_urls']}")
            
            # Make sure the image URLs start with "/raw/" - this is critical
            fixed_image_urls = []
            for img_url in product['image_urls']:
                # If the URL doesn't start with "/raw/", add it
                if not img_url.startswith('/raw/'):
                    filename = os.path.basename(img_url)
                    fixed_url = f"/raw/{filename}"
                    fixed_image_urls.append(fixed_url)
                    logging.info(f"Fixed image URL: {img_url} -> {fixed_url}")
                else:
                    fixed_image_urls.append(img_url)
            
            product['image_urls'] = fixed_image_urls
            logging.info(f"Updated image URLs for product {product_id}: {product['image_urls']}")
        elif 'image_paths' in product:
            logging.info(f"No image_urls found, but found image_paths for product {product_id}: {product['image_paths']}")
            # Convert image_paths to image_urls with absolute URLs
            product['image_urls'] = []
            for img_path in product['image_paths']:
                filename = os.path.basename(img_path)
                url = f"/raw/{filename}"
                product['image_urls'].append(url)
                logging.info(f"Added image URL from path: {img_path} -> {url}")
        else:
            logging.warning(f"No image URLs or paths found for product {product_id}")
        
        # Find similar products
        similar_products = []
        try:
            # Check if OpenAI API key is set
            if not os.environ.get("OPENAI_API_KEY"):
                logging.warning("OPENAI_API_KEY is not set, skipping similar products")
                # No need to flash an error, just don't show similar products
            else:
                # Debug: Print product data before finding similar products
                logging.info(f"Searching for similar products for product ID: {product_id}")
                
                # Get similar products with debug=True to log more information
                similar_products = get_similar_products(product_id, threshold=0.3, max_results=4, debug=True)
                
                if similar_products:
                    logging.info(f"Found {len(similar_products)} similar products")
                    
                    # Convert raw image paths to URLs
                    valid_similar_products = []
                    for i, similar in enumerate(similar_products):
                        logging.info(f"Processing similar product {i+1}/{len(similar_products)}: {similar.get('product_id')} - {similar.get('product_name', 'Unknown')}")
                        
                        has_valid_image = False
                        if 'thumbnail' in similar:
                            # Make sure the thumbnail path exists
                            thumbnail_path = similar['thumbnail']
                            if os.path.exists(thumbnail_path):
                                logging.info(f"Thumbnail file exists: {thumbnail_path}")
                                # Get just the filename for the URL
                                # This is the raw path, we need to keep the /raw/ prefix
                                filename = os.path.basename(thumbnail_path)
                                similar['thumbnail_url'] = f"/raw/{filename}"
                                logging.info(f"Setting thumbnail URL for similar product: {similar['thumbnail_url']}")
                                has_valid_image = True
                            else:
                                logging.warning(f"Thumbnail file doesn't exist: {thumbnail_path}")
                        
                        # If no valid thumbnail, try to find a fallback
                        if not has_valid_image:
                            logging.warning(f"No valid thumbnail found for similar product: {similar.get('product_id')}")
                            
                            try:
                                # Load the product data to find images
                                product_path = f"response/{similar.get('product_id')}.json"
                                if os.path.exists(product_path):
                                    with open(product_path, 'r') as f:
                                        product_data = json.load(f)
                                        
                                    # Try to get an image path
                                    from utils.similar_products import get_product_image_path
                                    img_path = get_product_image_path(product_data, debug=False)
                                    if img_path and os.path.exists(img_path):
                                        # Using the same direct raw path format
                                        filename = os.path.basename(img_path)
                                        similar['thumbnail_url'] = f"/raw/{filename}"
                                        logging.info(f"Found fallback image: {similar['thumbnail_url']}")
                                        has_valid_image = True
                                    else:
                                        logging.warning(f"No fallback image found for product: {similar.get('product_id')}")
                            except Exception as e:
                                logging.error(f"Error finding fallback image: {str(e)}")
                        
                        # Only add products with valid images
                        if has_valid_image:
                            valid_similar_products.append(similar)
                    
                    # Replace similar_products with only valid ones
                    similar_products = valid_similar_products
                else:
                    logging.info("No similar products found")
        except Exception as e:
            logging.error(f"Error finding similar products: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            # Continue even if similar products fail - just don't show them
        
        # Check if we have a persona success message to display
        persona_success = session.pop('persona_success', None)
        if persona_success:
            flash('Persona descriptions generated successfully.', 'success')
            
        return render_template('view_product.html', product=product, similar_products=similar_products)
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
        
        # Update persona descriptions if provided
        if 'persona_descriptions' in request.form:
            # This would be a JSON string in the form
            try:
                persona_descriptions = json.loads(request.form.get('persona_descriptions', '{}'))
                if persona_descriptions:
                    product_data['persona_descriptions'] = persona_descriptions
            except json.JSONDecodeError:
                pass
                
        # Save the updated product data back to the file
        with open(response_file, 'w') as f:
            json.dump(product_data, f, indent=4)
        
        flash('Product information updated successfully.', 'success')
        return redirect(url_for('view_product', product_id=product_id))
    
    except Exception as e:
        logging.error(f"Error updating product {product_id}: {str(e)}")
        flash(f'Error updating product: {str(e)}', 'error')
        return redirect(url_for('view_product', product_id=product_id))

@app.route('/generate_personas/<product_id>', methods=['POST'])
def generate_product_personas(product_id):
    """Generate persona-based descriptions for an existing product."""
    try:
        # Clear any stale flash messages 
        session.pop('_flashes', None)
        
        # Load product data from JSON file
        response_file = f"response/{product_id}.json"
        if not os.path.exists(response_file):
            flash('Product not found', 'error')
            return redirect(url_for('catalog'))
        
        with open(response_file, 'r') as f:
            product_data = json.load(f)
        
        # Check if OpenAI API key is available
        if not os.environ.get("OPENAI_API_KEY"):
            flash('Cannot generate persona descriptions: OpenAI API key is missing', 'error')
            return redirect(url_for('view_product', product_id=product_id))
            
        try:
            # Generate persona descriptions
            logging.info(f"Generating persona descriptions for product ID: {product_id}")
            
            # Set a timeout for the generate_persona_descriptions function
            start_time = time.time()
            result = generate_persona_descriptions(product_data)
            end_time = time.time()
            
            logging.info(f"Persona descriptions generation completed in {end_time - start_time:.2f} seconds")
            
            if 'error' in result:
                logging.error(f"Error generating persona descriptions: {result['error']}")
                
                if "API request timed out" in str(result['error']):
                    flash("The request timed out. Please try again later.", 'error')
                elif "API key" in str(result['error']).lower():
                    flash("OpenAI API key validation failed. Please check your API key.", 'error')
                else:
                    flash(f'Error generating persona descriptions: {result["error"]}', 'error')
                    
                return redirect(url_for('view_product', product_id=product_id))
        except ValueError as e:
            logging.error(f"API key error: {str(e)}")
            flash("OpenAI API key is missing or invalid. Please add a valid key to your .env file.", 'error')
            return redirect(url_for('view_product', product_id=product_id))
        except Exception as e:
            logging.error(f"Exception generating persona descriptions: {str(e)}")
            flash(f'Error generating persona descriptions: {str(e)}', 'error')
            return redirect(url_for('view_product', product_id=product_id))
        
        # Update product data with new persona descriptions
        product_data['persona_descriptions'] = result['persona_descriptions']
        
        # Save the updated product data back to the file
        with open(response_file, 'w') as f:
            json.dump(product_data, f, indent=4)
        
        # Add a success message to the session for display
        session['persona_success'] = True
        return redirect(url_for('view_product', product_id=product_id))
    
    except Exception as e:
        logging.error(f"Error generating personas for product {product_id}: {str(e)}")
        flash(f'Error generating persona descriptions: {str(e)}', 'error')
        return redirect(url_for('view_product', product_id=product_id))

@app.route('/search')
def search_page():
    """Dedicated search page for finding products."""
    query = request.args.get('q', '')
    results = []
    
    # Only search if query is provided
    if query and len(query) >= 2:
        try:
            # Get all JSON files in the response directory
            response_files = os.listdir('response')
            response_files = [f for f in response_files if f.endswith('.json')]
            
            for filename in response_files:
                file_path = os.path.join('response', filename)
                try:
                    with open(file_path, 'r') as f:
                        product_data = json.load(f)
                        product_id = filename.replace('.json', '')
                        
                        # Extract product information
                        name = product_data.get('product_name', '')
                        category = product_data.get('category', '')
                        price = product_data.get('price', '')
                        tags = product_data.get('tags', [])
                        description = product_data.get('short_description', '')
                        
                        # If no dedicated description field, use first part of AI-generated description
                        if not description and 'description' in product_data.get('ai_response', {}):
                            description = product_data['ai_response']['description'][:100] + '...'
                        
                        # Get first image if available
                        image = ''
                        if 'image_urls' in product_data and product_data['image_urls']:
                            # Use the image URL as is - should be in format /raw/filename
                            image = product_data['image_urls'][0]
                        elif 'image_paths' in product_data and product_data['image_paths']:
                            image_path = os.path.basename(product_data['image_paths'][0])
                            image = url_for('serve_raw_file', filename=image_path)
                        
                        # Create searchable text from all product fields
                        searchable_text = f"{name} {category} {price} {' '.join(tags)} {description}".lower()
                        
                        # Add to results if query is found in searchable text
                        if query.lower() in searchable_text:
                            results.append({
                                'product_id': product_id,
                                'product_name': name,
                                'category': category,
                                'price': price,
                                'tags': tags,
                                'image_urls': [image] if image else [],
                                'short_description': description
                            })
                except Exception as e:
                    logging.error(f"Error loading {file_path}: {str(e)}")
                    continue
            
            # Sort results by name
            results.sort(key=lambda x: x['product_name'])
            
        except Exception as e:
            logging.error(f"Error in search: {str(e)}")
    
    return render_template('search.html', query=query, results=results)

@app.route('/api/spotlight-search')
def spotlight_search():
    """API endpoint for the spotlight search feature."""
    query = request.args.get('q', '').lower()
    if not query or len(query) < 2:
        return jsonify([])
    
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
                    
                    # Get first image URL if available
                    image_url = ''
                    if 'image_urls' in product_data and product_data['image_urls']:
                        # Make sure the image URLs start with "/raw/"
                        img_url = product_data['image_urls'][0]
                        if not img_url.startswith('/raw/'):
                            filename = os.path.basename(img_url)
                            image_url = f"/raw/{filename}"
                            logging.info(f"Spotlight search: fixed image URL {img_url} -> {image_url}")
                        else:
                            image_url = img_url
                    
                    # Simplified product object for search results
                    simplified_product = {
                        'product_id': product_data.get('product_id', ''),
                        'product_name': product_data.get('product_name', ''),
                        'category': product_data.get('category', ''),
                        'price': product_data.get('price', ''),
                        'short_description': product_data.get('short_description', '')[:100] + '...' if product_data.get('short_description') else '',
                        'image_urls': [image_url] if image_url else [],
                        'tags': product_data.get('tags', [])[:6]  # Limit tags to first 6
                    }
                    products.append(simplified_product)
            except Exception as e:
                logging.error(f"Error loading {file_path}: {str(e)}")
                continue
    except Exception as e:
        logging.error(f"Error listing response directory: {str(e)}")
        return jsonify([])
    
    # Filter products based on search query
    search_results = []
    for product in products:
        product_json = json.dumps(product).lower()
        if query in product_json:
            # Calculate a simple relevance score (more matches = higher score)
            relevance = product_json.count(query)
            # Boost score if query matches beginning of name
            if product['product_name'].lower().startswith(query):
                relevance += 10
            # Boost score if query matches category exactly
            if product['category'].lower() == query:
                relevance += 5
            # Boost score if query matches tag exactly
            for tag in product.get('tags', []):
                if tag.lower() == query:
                    relevance += 3
            
            product['relevance'] = relevance
            search_results.append(product)
    
    # Sort by relevance
    search_results.sort(key=lambda x: x['relevance'], reverse=True)
    
    # Limit to top 5 results
    return jsonify(search_results[:5])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
