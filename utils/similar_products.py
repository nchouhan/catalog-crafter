import os
import json
import logging
import base64
from pathlib import Path

# Import openai for image analysis
from openai import OpenAI

# Initialize OpenAI client with error handling and timeout settings
try:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logging.warning("OPENAI_API_KEY environment variable is not set")
        openai = None
    else:
        openai = OpenAI(
            api_key=api_key,
            timeout=60.0  # Set a 60 second default timeout for all requests
        )
        logging.info("OpenAI client initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client: {str(e)}")
    openai = None

def encode_image_to_base64(image_path):
    """Convert an image file to base64 encoding."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image: {str(e)}")
        return None

def extract_image_features(image_path, product_id=None):
    """
    Extract features from an image using OpenAI's API.
    Features are cached in the product's JSON file to avoid repeated API calls.
    
    Args:
        image_path (str): Path to the image file
        product_id (str, optional): ID of the product to check for cached features
        
    Returns:
        dict: Dictionary containing extracted features
    """
    # Define default features to return on failure
    default_features = {
        "colors": ["unknown"],
        "product_type": "unspecified",
        "materials": ["unknown"],
        "style": ["unknown"],
        "distinctive_elements": ["unspecified"]
    }
    
    # First check if we have cached features
    if product_id:
        json_path = f"response/{product_id}.json"
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    product_data = json.load(f)
                
                # Check if features are cached
                if "image_features" in product_data:
                    logging.info(f"Using cached image features for product {product_id}")
                    return product_data["image_features"]
                
                logging.info(f"No cached image features found for product {product_id}")
            except Exception as e:
                logging.error(f"Error reading cached features: {str(e)}")
    
    try:
        # First check if the image file exists
        if not os.path.exists(image_path):
            logging.error(f"Image file does not exist: {image_path}")
            return default_features
            
        # Encode image to base64
        base64_image = encode_image_to_base64(image_path)
        if not base64_image:
            logging.error(f"Failed to encode image to base64: {image_path}")
            return default_features
            
        # Check if OpenAI API key is available
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logging.error("OPENAI_API_KEY is not set in environment variables")
            return default_features
        
        # Check if OpenAI client is initialized
        if openai is None:
            logging.error("OpenAI client is not initialized")
            return default_features
        
        try:
            # Call OpenAI API to analyze the image
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            logging.info(f"Calling OpenAI API to analyze image: {image_path}")
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a product image analyzer. Extract key visual features from the image in a 
                        structured format. Focus on:
                        1. Main colors (primary, secondary, accent)
                        2. Product type/category
                        3. Materials visible
                        4. Style attributes (sporty, casual, formal, etc.)
                        5. Distinctive visual elements
                        
                        Return JSON in this exact format:
                        {
                            "colors": ["color1", "color2"],
                            "product_type": "specific type",
                            "materials": ["material1", "material2"],
                            "style": ["style1", "style2"],
                            "distinctive_elements": ["element1", "element2"]
                        }
                        """
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract the key visual features from this product image."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=800
            )
            
            # Parse the response to get the features
            features = json.loads(response.choices[0].message.content)
            logging.info(f"Successfully extracted features from image: {image_path}")
            
            # Cache features if product_id is provided
            if product_id:
                try:
                    json_path = f"response/{product_id}.json"
                    if os.path.exists(json_path):
                        with open(json_path, 'r') as f:
                            product_data = json.load(f)
                        
                        # Add features to the product data
                        product_data["image_features"] = features
                        
                        # Save updated product data
                        with open(json_path, 'w') as f:
                            json.dump(product_data, f, indent=2)
                            
                        logging.info(f"Cached image features for product {product_id}")
                except Exception as e:
                    logging.error(f"Error caching features: {str(e)}")
            
            return features
            
        except Exception as e:
            logging.error(f"Error calling OpenAI API: {str(e)}")
            return default_features
        
    except Exception as e:
        logging.error(f"Error extracting image features: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return default_features

def calculate_similarity_score(features1, features2, debug=False, product_id=None):
    """
    Calculate similarity score between two feature sets.
    Also includes metadata from product JSON files when available.
    
    Args:
        features1 (dict): First feature set
        features2 (dict): Second feature set
        debug (bool): Whether to print detailed debug information
        product_id (str): ID of the product being compared (for logging)
        
    Returns:
        float: Similarity score (0.0 to 1.0)
    """
    if not features1 or not features2:
        return 0.0
    
    score = 0.0
    total_weight = 0.0
    sub_scores = {}
    
    # Load product metadata from response JSON files if available
    product1_data = None
    product2_data = None
    
    # Try to get product IDs
    product1_id = features1.get("product_id", None)
    if not product1_id and product_id:
        # The compared product might be the target product
        product1_id = product_id
    
    product2_id = features2.get("product_id", None)
    
    # Try to load product metadata
    if product1_id:
        try:
            json_path = f"response/{product1_id}.json"
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    product1_data = json.load(f)
                    if debug:
                        logging.info(f"Loaded metadata for product1 ID: {product1_id}")
        except Exception as e:
            if debug:
                logging.warning(f"Failed to load metadata for product1: {str(e)}")
    
    if product2_id:
        try:
            json_path = f"response/{product2_id}.json"
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    product2_data = json.load(f)
                    if debug:
                        logging.info(f"Loaded metadata for product2 ID: {product2_id}")
        except Exception as e:
            if debug:
                logging.warning(f"Failed to load metadata for product2: {str(e)}")
    
    # Compare product type (weight: 0.3) - Important but reduced from 0.4
    if "product_type" in features1 and "product_type" in features2:
        type_score = 0
        # Exact match gets full points
        if features1["product_type"].lower() == features2["product_type"].lower():
            type_score = 0.3
        # Similar types get partial points (e.g., t-shirt and tank top are both tops)
        elif any(word in features1["product_type"].lower() for word in ["shirt", "tee", "top"]) and \
             any(word in features2["product_type"].lower() for word in ["shirt", "tee", "top"]):
            type_score = 0.15
        # Pants/shorts/skirts are bottom wear
        elif any(word in features1["product_type"].lower() for word in ["pant", "jean", "trouser", "short", "skirt"]) and \
             any(word in features2["product_type"].lower() for word in ["pant", "jean", "trouser", "short", "skirt"]):
            type_score = 0.15
        # Jackets/hoodies/sweatshirts are outerwear
        elif any(word in features1["product_type"].lower() for word in ["jacket", "hoodie", "sweatshirt", "coat"]) and \
             any(word in features2["product_type"].lower() for word in ["jacket", "hoodie", "sweatshirt", "coat"]):
            type_score = 0.15
            
        score += type_score
        total_weight += 0.3
        
        if debug:
            sub_scores["product_type"] = {
                "score": type_score,
                "product1": features1["product_type"],
                "product2": features2["product_type"],
                "weight": 0.3
            }
    
    # Check for gender consistency in product types (e.g., men's vs women's)
    # This is a penalty factor - we'll subtract points for mismatched gender
    gender_penalty = 0
    if "product_type" in features1 and "product_type" in features2:
        # Check for gender indicators
        is_mens1 = any(term in features1["product_type"].lower() for term in ["men", "man", "men's", "man's", "masculine", "male"])
        is_womens1 = any(term in features1["product_type"].lower() for term in ["women", "woman", "women's", "woman's", "feminine", "female"])
        
        is_mens2 = any(term in features2["product_type"].lower() for term in ["men", "man", "men's", "man's", "masculine", "male"])
        is_womens2 = any(term in features2["product_type"].lower() for term in ["women", "woman", "women's", "woman's", "feminine", "female"])
        
        # If one is men's and the other is women's, apply a penalty
        if (is_mens1 and is_womens2) or (is_womens1 and is_mens2):
            gender_penalty = 0.3  # Strong penalty for gender mismatch
            score -= gender_penalty
            
        if debug and gender_penalty > 0:
            sub_scores["gender_mismatch"] = {
                "score": -gender_penalty,
                "product1": "men's" if is_mens1 else "women's" if is_womens1 else "unisex",
                "product2": "men's" if is_mens2 else "women's" if is_womens2 else "unisex",
                "weight": 0.3
            }
    
    # Compare colors (weight: 0.25)
    if "colors" in features1 and "colors" in features2:
        color_matches = len(set(features1["colors"]) & set(features2["colors"]))
        max_colors = max(len(features1["colors"]), len(features2["colors"]))
        color_score = 0
        if max_colors > 0:
            color_score = 0.25 * (color_matches / max_colors)
            score += color_score
        total_weight += 0.25
        
        if debug:
            sub_scores["colors"] = {
                "score": color_score,
                "common": list(set(features1["colors"]) & set(features2["colors"])),
                "product1": features1["colors"],
                "product2": features2["colors"],
                "weight": 0.25
            }
    
    # Compare materials (weight: 0.15) - Reduced from 0.2
    if "materials" in features1 and "materials" in features2:
        material_matches = len(set(features1["materials"]) & set(features2["materials"]))
        max_materials = max(len(features1["materials"]), len(features2["materials"]))
        material_score = 0
        if max_materials > 0:
            material_score = 0.15 * (material_matches / max_materials)
            score += material_score
        total_weight += 0.15
        
        if debug:
            sub_scores["materials"] = {
                "score": material_score,
                "common": list(set(features1["materials"]) & set(features2["materials"])),
                "product1": features1["materials"],
                "product2": features2["materials"],
                "weight": 0.15
            }
    
    # Compare style (weight: 0.1) - Reduced from 0.15
    if "style" in features1 and "style" in features2:
        style_matches = len(set(features1["style"]) & set(features2["style"]))
        max_styles = max(len(features1["style"]), len(features2["style"]))
        style_score = 0
        if max_styles > 0:
            style_score = 0.1 * (style_matches / max_styles)
            score += style_score
        total_weight += 0.1
        
        if debug:
            sub_scores["style"] = {
                "score": style_score,
                "common": list(set(features1["style"]) & set(features2["style"])),
                "product1": features1["style"],
                "product2": features2["style"],
                "weight": 0.1
            }
    
    # Compare distinctive elements (weight: 0.1)
    if "distinctive_elements" in features1 and "distinctive_elements" in features2:
        element_matches = len(set(features1["distinctive_elements"]) & set(features2["distinctive_elements"]))
        max_elements = max(len(features1["distinctive_elements"]), len(features2["distinctive_elements"]))
        element_score = 0
        if max_elements > 0:
            element_score = 0.1 * (element_matches / max_elements)
            score += element_score
        total_weight += 0.1
        
        if debug:
            sub_scores["distinctive_elements"] = {
                "score": element_score,
                "common": list(set(features1["distinctive_elements"]) & set(features2["distinctive_elements"])),
                "product1": features1["distinctive_elements"],
                "product2": features2["distinctive_elements"],
                "weight": 0.1
            }
    
    # Compare tags from product metadata (weight: 0.15)
    if product1_data and product2_data and "tags" in product1_data and "tags" in product2_data:
        tags1 = product1_data["tags"]
        tags2 = product2_data["tags"]
        
        if isinstance(tags1, list) and isinstance(tags2, list) and tags1 and tags2:
            # Convert tags to lowercase for better matching
            tags1 = [tag.lower() for tag in tags1]
            tags2 = [tag.lower() for tag in tags2]
            
            tag_matches = len(set(tags1) & set(tags2))
            max_tags = max(len(tags1), len(tags2))
            tag_score = 0
            if max_tags > 0:
                tag_score = 0.15 * (tag_matches / max_tags)
                score += tag_score
            total_weight += 0.15
            
            if debug:
                sub_scores["tags"] = {
                    "score": tag_score,
                    "common": list(set(tags1) & set(tags2)),
                    "product1": tags1,
                    "product2": tags2,
                    "weight": 0.15
                }
    
    # Compare target audience from product metadata (weight: 0.1)
    if product1_data and product2_data and "target_audience" in product1_data and "target_audience" in product2_data:
        audience1 = product1_data["target_audience"]
        audience2 = product2_data["target_audience"]
        
        if isinstance(audience1, list) and isinstance(audience2, list) and audience1 and audience2:
            # Convert audiences to lowercase for better matching
            audience1 = [a.lower() for a in audience1]
            audience2 = [a.lower() for a in audience2]
            
            audience_matches = len(set(audience1) & set(audience2))
            max_audience = max(len(audience1), len(audience2))
            audience_score = 0
            if max_audience > 0:
                audience_score = 0.1 * (audience_matches / max_audience)
                score += audience_score
            total_weight += 0.1
            
            if debug:
                sub_scores["target_audience"] = {
                    "score": audience_score,
                    "common": list(set(audience1) & set(audience2)),
                    "product1": audience1,
                    "product2": audience2,
                    "weight": 0.1
                }
    
    # Compare specifications from product metadata (weight: 0.1)
    if product1_data and product2_data and "specifications" in product1_data and "specifications" in product2_data:
        specs1 = product1_data["specifications"]
        specs2 = product2_data["specifications"]
        
        if isinstance(specs1, list) and isinstance(specs2, list) and specs1 and specs2:
            # Convert specifications to lowercase strings for comparison
            specs1_str = [str(spec).lower() for spec in specs1]
            specs2_str = [str(spec).lower() for spec in specs2]
            
            # Count how many specifications have similar words
            spec_similarity = 0
            for spec1 in specs1_str:
                for spec2 in specs2_str:
                    # If specs share at least 2 words, consider them similar
                    words1 = set(spec1.split())
                    words2 = set(spec2.split())
                    common_words = words1 & words2
                    if len(common_words) >= 2:
                        spec_similarity += 1
                        break
            
            max_specs = max(len(specs1), len(specs2))
            spec_score = 0
            if max_specs > 0:
                spec_score = 0.1 * (spec_similarity / max_specs)
                score += spec_score
            total_weight += 0.1
            
            if debug:
                sub_scores["specifications"] = {
                    "score": spec_score,
                    "product1": specs1,
                    "product2": specs2,
                    "weight": 0.1
                }
    
    # Normalize the score if we have weights
    final_score = 0.0
    if total_weight > 0:
        final_score = score / total_weight
    
    # Log detailed scores if debug is enabled
    if debug:
        logging.info(f"Similarity details for product {product_id}:")
        logging.info(f"  Total score: {final_score:.4f}")
        for feature, details in sub_scores.items():
            logging.info(f"  {feature} (weight: {details['weight']:.2f}):")
            logging.info(f"    Score: {details['score']:.4f}")
            if feature != "product_type":
                logging.info(f"    Common: {details['common']}")
            logging.info(f"    Product1: {details['product1']}")
            logging.info(f"    Product2: {details['product2']}")
    
    return final_score

def get_product_image_path(product_data, debug=False):
    """Helper function to get the first image path from a product data dictionary.
    
    This function checks multiple fields where image paths might be stored and handles
    different formats of storage (full paths, filenames only, etc.)
    """
    if debug:
        logging.info(f"Searching for image path in product data with keys: {list(product_data.keys())}")
    
    # Try to get product_id first - will be useful for fallback strategies
    product_id = product_data.get('product_id', '')
    
    # Check all possible fields where image paths might be stored - in priority order
    if "raw_images" in product_data and product_data["raw_images"]:
        if debug:
            logging.info(f"Found image in raw_images: {product_data['raw_images'][0]}")
        image_path = product_data["raw_images"][0]
    elif "images" in product_data and product_data["images"]:
        if debug:
            logging.info(f"Found image in images: {product_data['images'][0]}")
        image_path = product_data["images"][0]
    elif "image_paths" in product_data and product_data["image_paths"]:
        if debug:
            logging.info(f"Found image in image_paths: {product_data['image_paths'][0]}")
        image_path = product_data["image_paths"][0]
    elif "image_urls" in product_data and product_data["image_urls"]:
        # Handle the case where only image_urls are available
        if debug:
            logging.info(f"Found image in image_urls: {product_data['image_urls'][0]}")
        
        # Extract the filename from the URL and convert to a local path
        try:
            url = product_data["image_urls"][0]
            filename = os.path.basename(url)
            
            # Check if file exists in raw directory
            if os.path.exists(f"raw/{filename}"):
                if debug:
                    logging.info(f"Found local file for image_url: raw/{filename}")
                image_path = f"raw/{filename}"
            else:
                # Try fallback strategy with product_id
                if product_id:
                    # Try to find any file in raw directory starting with product_id
                    try:
                        raw_files = os.listdir('raw')
                        matching_files = [f for f in raw_files if f.startswith(product_id)]
                        if matching_files:
                            image_path = os.path.join('raw', matching_files[0])
                            if debug:
                                logging.info(f"Found matching file by timestamp: {image_path}")
                        else:
                            if debug:
                                logging.warning(f"No matching files found for product_id: {product_id}")
                            image_path = None
                    except Exception as e:
                        if debug:
                            logging.error(f"Error finding matching files: {str(e)}")
                        image_path = None
                else:
                    if debug:
                        logging.warning(f"Local file not found for image_url: {filename}")
                    image_path = None
        except Exception as e:
            if debug:
                logging.error(f"Error processing image_url: {str(e)}")
            image_path = None
    else:
        if debug:
            logging.warning(f"No standard image paths found in product data")
        
        # Try looking for any key that might contain image paths
        for key in product_data.keys():
            if 'image' in key.lower() and product_data[key]:
                try:
                    if isinstance(product_data[key], list) and len(product_data[key]) > 0:
                        image_path = product_data[key][0]
                        if debug:
                            logging.info(f"Found image in alternate field {key}: {image_path}")
                        break
                    elif isinstance(product_data[key], str):
                        image_path = product_data[key]
                        if debug:
                            logging.info(f"Found image in alternate field {key}: {image_path}")
                        break
                except Exception as e:
                    if debug:
                        logging.error(f"Error processing alternate field {key}: {str(e)}")
                    continue
        else:
            # Last resort: try to find any file in raw directory starting with product_id
            if product_id:
                try:
                    raw_files = os.listdir('raw')
                    matching_files = [f for f in raw_files if f.startswith(product_id)]
                    if matching_files:
                        image_path = os.path.join('raw', matching_files[0])
                        if debug:
                            logging.info(f"Fallback: Found matching file by timestamp: {image_path}")
                    else:
                        if debug:
                            logging.warning(f"No image paths or matching files found for product_id: {product_id}")
                        image_path = None
                except Exception as e:
                    if debug:
                        logging.error(f"Error finding matching files: {str(e)}")
                    image_path = None
            else:
                if debug:
                    logging.warning(f"No image paths found in product data and no product_id available")
                image_path = None
    
    # If we found an image path, make sure it's properly formatted
    if 'image_path' in locals() and image_path:
        # If image_path doesn't start with 'raw/' and doesn't include a directory
        if '/' not in image_path and not image_path.startswith('raw/'):
            image_path = os.path.join('raw', image_path)
            if debug:
                logging.info(f"Reformatted image path to: {image_path}")
        
        # Check if the file actually exists
        if not os.path.exists(image_path):
            if debug:
                logging.warning(f"Image file doesn't exist: {image_path}")
            
            # Try with just the filename in the raw directory
            basename = os.path.basename(image_path)
            alt_path = os.path.join('raw', basename)
            if os.path.exists(alt_path):
                if debug:
                    logging.info(f"Found alternate path: {alt_path}")
                image_path = alt_path
            else:
                if debug:
                    logging.warning(f"Alternate path doesn't exist either: {alt_path}")
    else:
        if debug:
            logging.warning(f"No valid image path found")
        image_path = None
    
    if debug:
        if image_path:
            logging.info(f"Returning image path: {image_path}")
        else:
            logging.warning(f"Returning None as image path")
    
    return image_path

def get_similar_products(product_id, threshold=0.3, max_results=4, debug=True):
    """
    Find products similar to the given product ID.
    
    Args:
        product_id (str): The timestamp ID of the product to find similar items for
        threshold (float): Minimum similarity score (0.0 to 1.0) to consider products similar
        max_results (int): Maximum number of similar products to return
        debug (bool): Whether to print debug information
        
    Returns:
        list: List of similar product data with similarity scores
    """
    try:
        logging.info(f"Starting similar products search for product ID: {product_id}")
        
        # First check if OpenAI is available
        if openai is None:
            logging.error("OpenAI client is not available, cannot find similar products")
            return []
            
        # Check if OpenAI API key is set
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logging.error("OPENAI_API_KEY is not set, cannot find similar products")
            return []
            
        # Get all response files
        response_dir = Path("response")
        if not os.path.exists(response_dir):
            logging.error(f"Response directory does not exist: {response_dir}")
            os.makedirs(response_dir, exist_ok=True)
            return []
            
        all_responses = list(response_dir.glob("*.json"))
        logging.info(f"Found {len(all_responses)} total product response files")
        
        if len(all_responses) < 2:
            logging.info("Not enough products to find similar items")
            return []
            
        # Get the target product data
        target_product_path = response_dir / f"{product_id}.json"
        if not target_product_path.exists():
            logging.error(f"Product ID {product_id} not found")
            return []
            
        try:
            with open(target_product_path, "r") as f:
                target_product = json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in target product file: {target_product_path}")
            return []
        except Exception as e:
            logging.error(f"Error reading target product file: {str(e)}")
            return []
            
        # Get first image of the target product
        logging.info(f"Getting image path for product ID: {product_id}")
        
        if debug:
            # Debug: Print out the product data structure
            logging.info(f"Product data keys: {list(target_product.keys())}")
            if "image_paths" in target_product:
                logging.info(f"image_paths: {target_product.get('image_paths')}")
            if "raw_images" in target_product:
                logging.info(f"raw_images: {target_product.get('raw_images')}")
            if "images" in target_product:
                logging.info(f"images: {target_product.get('images')}")
            if "image_urls" in target_product:
                logging.info(f"image_urls: {target_product.get('image_urls')}")
            
        target_image_path = get_product_image_path(target_product, debug=debug)
        if not target_image_path:
            logging.error(f"No images found for product ID {product_id}")
            return []
        
        # Check if image file exists
        if not os.path.exists(target_image_path):
            logging.error(f"Image file does not exist: {target_image_path}")
            return []
            
        logging.info(f"Using target image path: {target_image_path}")
        
        # Extract features from the target image (using product_id for caching)
        try:
            target_features = extract_image_features(target_image_path, product_id=product_id)
            if not target_features:
                logging.error(f"Could not extract features from target image: {target_image_path}")
                return []
        except Exception as e:
            logging.error(f"Error extracting features from target image: {target_image_path}, error: {str(e)}")
            return []
        
        logging.info(f"Successfully extracted features from target image")
            
        # Store results
        similar_products = []
        processed_products = 0
        
        # Find similar products
        for response_file in all_responses:
            # Skip the target product
            product_timestamp = response_file.stem
            if product_timestamp == product_id:
                continue
                
            try:
                with open(response_file, "r") as f:
                    product_data = json.load(f)
                
                processed_products += 1
                
                # Get the first image for comparison
                if debug:
                    logging.info(f"Getting comparison image for product: {product_timestamp}")
                    # Show a sample of the product data for debugging
                    logging.info(f"Product data keys for {product_timestamp}: {list(product_data.keys())}")
                
                comparison_image_path = get_product_image_path(product_data, debug=debug)
                
                # Skip products without images
                if not comparison_image_path:
                    if debug:
                        logging.warning(f"No image found for comparison product: {product_timestamp}")
                    continue
                
                # Check if comparison image exists
                if not os.path.exists(comparison_image_path):
                    if debug:
                        logging.warning(f"Comparison image does not exist: {comparison_image_path}")
                    continue
                    
                if debug:
                    logging.info(f"Using comparison image path: {comparison_image_path}")
                
                # Extract features from the comparison image
                comparison_features = extract_image_features(comparison_image_path, product_id=product_timestamp)
                if not comparison_features:
                    if debug:
                        logging.warning(f"Could not extract features from comparison image: {comparison_image_path}")
                    continue
                    
                # Calculate similarity score with detailed logging
                similarity = calculate_similarity_score(target_features, comparison_features, debug=debug, product_id=product_timestamp)
                if debug:
                    logging.info(f"Similarity score for {product_timestamp}: {similarity}")
                
                # If similarity is above threshold, add to results
                if similarity >= threshold:
                    if debug:
                        logging.info(f"Found similar product: {product_timestamp} with score {similarity}")
                    similar_products.append({
                        "product_id": product_timestamp,
                        "product_name": product_data.get("product_name", product_data.get("name", "Unknown Product")),
                        "category": product_data.get("category", ""),
                        "price": product_data.get("price", ""),
                        "thumbnail": comparison_image_path,  # Use the same path we found
                        "similarity_score": similarity
                    })
                    
            except json.JSONDecodeError:
                if debug:
                    logging.warning(f"Invalid JSON in product file: {response_file}")
                continue
            except Exception as e:
                if debug:
                    logging.error(f"Error processing product {product_timestamp}: {str(e)}")
                continue
                
        # Sort by similarity score and limit results
        similar_products.sort(key=lambda x: x["similarity_score"], reverse=True)
        logging.info(f"Processed {processed_products} products, found {len(similar_products)} similar products")
        return similar_products[:max_results]
        
    except Exception as e:
        logging.error(f"Error finding similar products: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return []
        
def check_duplicate_product(images, threshold=0.85, debug=True):
    """
    Check if uploaded images match any existing products too closely.
    
    Args:
        images (list): List of uploaded image paths
        threshold (float): Threshold above which a product is considered duplicate
        debug (bool): Whether to print debug information
        
    Returns:
        tuple: (is_duplicate, similar_products) - Boolean indicating if duplicate was found
               and list of potentially duplicate products
    """
    try:
        if debug:
            logging.info(f"Starting duplicate product check with {len(images) if images else 0} images")
            
        if not images:
            logging.warning("No images provided for duplicate check")
            return False, []
            
        # First check if OpenAI is available
        if openai is None:
            logging.error("OpenAI client is not available, cannot check for duplicate products")
            return False, []
            
        # Check if OpenAI API key is set
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logging.error("OPENAI_API_KEY is not set, cannot check for duplicate products")
            return False, []
        
        # Make sure image exists and is readable
        if not os.path.exists(images[0]):
            logging.error(f"Image file does not exist: {images[0]}")
            return False, []
            
        # Get all response files
        response_dir = Path("response")
        if not os.path.exists(response_dir):
            logging.info(f"Response directory does not exist: {response_dir}")
            os.makedirs(response_dir, exist_ok=True)
            return False, []
            
        all_responses = list(response_dir.glob("*.json"))
        
        if debug:
            logging.info(f"Found {len(all_responses)} product files to check against")
            logging.info(f"Using first image for comparison: {images[0]}")
        
        # If there are no products to compare against, we can't have duplicates
        if len(all_responses) == 0:
            logging.info("No existing products to check against")
            return False, []
            
        # Extract features from the new image
        new_image_features = extract_image_features(images[0])
        if not new_image_features:
            logging.error(f"Could not extract features from the new image: {images[0]}")
            return False, []
            
        if debug:
            logging.info("Successfully extracted features from the new image")
            
        # Store potentially duplicate products
        potential_duplicates = []
        processed_products = 0
        
        # Compare with existing products
        for response_file in all_responses:
            product_timestamp = response_file.stem
            try:
                processed_products += 1
                
                if debug:
                    logging.info(f"Checking product {product_timestamp}")
                
                try:
                    with open(response_file, "r") as f:
                        product_data = json.load(f)
                except json.JSONDecodeError:
                    if debug:
                        logging.warning(f"Invalid JSON in product file: {response_file}")
                    continue
                except Exception as e:
                    if debug:
                        logging.error(f"Error reading product file: {str(e)}")
                    continue
                
                # Get the first image for comparison
                comparison_image_path = get_product_image_path(product_data, debug=debug)
                
                # Skip products without images
                if not comparison_image_path:
                    if debug:
                        logging.warning(f"No image found for product: {product_timestamp}")
                    continue
                
                # Check if comparison image exists
                if not os.path.exists(comparison_image_path):
                    if debug:
                        logging.warning(f"Comparison image does not exist: {comparison_image_path}")
                    continue
                
                if debug:
                    logging.info(f"Using comparison image: {comparison_image_path}")
                
                # Extract features from the comparison image
                comparison_features = extract_image_features(comparison_image_path, product_id=product_timestamp)
                if not comparison_features:
                    if debug:
                        logging.warning(f"Could not extract features from comparison image: {comparison_image_path}")
                    continue
                    
                # Calculate similarity score with detailed logging
                similarity = calculate_similarity_score(new_image_features, comparison_features, debug=debug, product_id=product_timestamp)
                
                if debug:
                    logging.info(f"Similarity score for {product_timestamp}: {similarity}")
                
                # If similarity is very high, consider it a potential duplicate
                if similarity >= threshold:
                    if debug:
                        logging.info(f"Found potential duplicate: {product_timestamp} with score {similarity}")
                    
                    potential_duplicates.append({
                        "product_id": product_timestamp,
                        "product_name": product_data.get("product_name", product_data.get("name", "Unknown Product")),
                        "category": product_data.get("category", ""),
                        "thumbnail": comparison_image_path,
                        "similarity_score": similarity
                    })
                    
            except Exception as e:
                if debug:
                    logging.error(f"Error checking for duplicates with product {product_timestamp}: {str(e)}")
                continue
                
        # Sort by similarity score
        potential_duplicates.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        if debug:
            logging.info(f"Processed {processed_products} products, found {len(potential_duplicates)} potential duplicates")
            if potential_duplicates:
                for idx, dup in enumerate(potential_duplicates):
                    logging.info(f"Duplicate {idx+1}: {dup['product_name']} (ID: {dup['product_id']}) - Score: {dup['similarity_score']}")
        
        # Return True if we found any potential duplicates
        return len(potential_duplicates) > 0, potential_duplicates
        
    except Exception as e:
        logging.error(f"Error checking for duplicate products: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False, []