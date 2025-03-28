import os
import json
import logging
import time
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Get OpenAI API key from environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY not found in environment variables!")

# Initialize OpenAI client with error handling and a longer default timeout
try:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logging.warning("OPENAI_API_KEY environment variable is not set")
        openai = None
    else:
        openai = OpenAI(
            api_key=api_key,
            timeout=120.0  # Set a 120 second default timeout for all requests
        )
        logging.info("OpenAI client initialized successfully in openai_helper.py")
except Exception as e:
    logging.error(f"Failed to initialize OpenAI client in openai_helper.py: {str(e)}")
    openai = None

def analyze_product(product_data, base64_images, generate_personas=True):
    """
    Analyze product images and generate descriptions and tags using OpenAI API.
    
    Args:
        product_data (dict): Dict containing product name, category, and price
        base64_images (list): List of base64-encoded images
        generate_personas (bool): Whether to generate persona-based descriptions
    
    Returns:
        dict: Generated product description and tags
        
    Raises:
        Exception: If OpenAI API is not available or an error occurs during analysis
    """
    # Prepare default response for when API fails
    default_response = {
        "short_description": f"{product_data['name']} - {product_data['category']}",
        "detailed_description": f"A {product_data['category']} product named {product_data['name']} priced at {product_data['price']}.",
        "specifications": [],
        "tags": [product_data['category']],
        "seo_keywords": [product_data['name'], product_data['category']],
        "target_audience": [],
        "colors": [],
        "materials": [],
        "styles": []
    }
    
    # Add default persona descriptions if needed
    if generate_personas:
        default_response["persona_descriptions"] = {
            "athleisure_enthusiast": "N/A",
            "performance_athlete": "N/A",
            "value_conscious_buyer": "N/A"
        }
        
    # Check if OpenAI client is initialized
    if openai is None:
        logging.error("OpenAI client is not initialized")
        default_response["error"] = "OpenAI client is not initialized"
        return default_response
        
    # Check if OpenAI API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        logging.error("OPENAI_API_KEY is not set in environment variables")
        default_response["error"] = "OpenAI API key is missing"
        return default_response
        
    # Check if we have any images
    if not base64_images:
        logging.error("No images provided for analysis")
        default_response["error"] = "No images provided for analysis"
        return default_response
    
    try:
        # Define the three personas
        personas = {
            "athleisure_enthusiast": {
                "name": "Athleisure Enthusiast",
                "description": "Young professionals, college students, and trendsetters who wear sportswear for everyday fashion. Prioritize style, comfort, and brand appeal over pure performance."
            },
            "performance_athlete": {
                "name": "Performance Athlete",
                "description": "Runners, gym-goers, and sports players who need high-performance footwear and apparel. Focus on durability, cushioning, and sport-specific features."
            },
            "value_conscious_buyer": {
                "name": "Value-Conscious Buyer",
                "description": "Everyday consumers looking for reliable sportswear at an affordable price. Prefer multi-purpose shoes for walking, running, or casual use. More price-sensitive but open to promotions and value deals."
            }
        }
        
        # Prepare messages for OpenAI API
        system_content = """
            You are a professional product content writer. Analyze the provided product images 
            and information to create detailed, compelling product descriptions and relevant tags.
            """
        
        # Add persona-specific content generation requirements if needed
        if generate_personas:
            system_content += """
            Create three distinct descriptions, each tailored to a specific customer persona:
            
            1. Athleisure Enthusiast: Young professionals, college students, and trendsetters who wear sportswear for everyday fashion. Prioritize style, comfort, and brand appeal over pure performance.
            
            2. Performance Athlete: Runners, gym-goers, and sports players who need high-performance footwear and apparel. Focus on durability, cushioning, and sport-specific features.
            
            3. Value-Conscious Buyer: Everyday consumers looking for reliable sportswear at an affordable price. Prefer multi-purpose shoes for walking, running, or casual use. More price-sensitive but open to promotions and value deals.
            
            Respond with JSON in the following format:
            {
                "short_description": "Brief 1-2 sentence summary",
                "detailed_description": "Detailed paragraph(s) about the product's features, benefits, and use cases",
                "persona_descriptions": {
                    "athleisure_enthusiast": "Description tailored to Athleisure Enthusiasts highlighting style and comfort aspects",
                    "performance_athlete": "Description tailored to Performance Athletes highlighting performance and durability features",
                    "value_conscious_buyer": "Description tailored to Value-Conscious Buyers highlighting value, versatility and affordability"
                },
                "specifications": ["spec1", "spec2", ...],
                "tags": ["tag1", "tag2", ...],
                "seo_keywords": ["keyword1", "keyword2", ...],
                "target_audience": ["audience1", "audience2", ...],
                "colors": ["color1", "color2", ...],
                "materials": ["material1", "material2", ...],
                "styles": ["style1", "style2", ...]
            }
            """
        else:
            system_content += """
            Respond with JSON in the following format:
            {
                "short_description": "Brief 1-2 sentence summary",
                "detailed_description": "Detailed paragraph(s) about the product's features, benefits, and use cases",
                "specifications": ["spec1", "spec2", ...],
                "tags": ["tag1", "tag2", ...],
                "seo_keywords": ["keyword1", "keyword2", ...],
                "target_audience": ["audience1", "audience2", ...],
                "colors": ["color1", "color2", ...],
                "materials": ["material1", "material2", ...],
                "styles": ["style1", "style2", ...]
            }
            """
        
        system_content += """
            For colors, include all colors present in the product.
            For materials, include all materials used in the product construction.
            For styles, include descriptive style terms like casual, formal, sporty, etc.
            Be specific with all attributes, professional, and make the descriptions marketable.
            """
        
        messages = [
            {
                "role": "system",
                "content": system_content
            }
        ]
        
        # Add user message with product info
        user_content = [
            {
                "type": "text",
                "text": f"""
                Please generate product content for the following item:
                
                Product Name: {product_data['name']}
                Category: {product_data['category']}
                Price: {product_data['price']}
                
                Analyze the attached images and create a professional product listing.
                """
            }
        ]
        
        # Add each image to the message
        for image in base64_images:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image}"}
            })
        
        messages.append({"role": "user", "content": user_content})
        
        try:
            # Call OpenAI API
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            logging.info("Calling OpenAI API to analyze product")
            
            # Double-check that OpenAI client is initialized before making the API call
            if openai is None:
                logging.error("OpenAI client is None, cannot make API call")
                default_response["error"] = "OpenAI client is not initialized"
                return default_response
                
            # Set timeout to avoid worker timeouts in Gunicorn
            try:
                logging.debug("Making API call with timeout setting of 120.0 seconds")
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=1000,  # Reduced from 1500 to help avoid timeouts
                    timeout=120.0  # Set a longer timeout for complex image analysis
                )
                logging.debug("API call completed successfully")
            except Exception as e:
                if "timeout" in str(e).lower():
                    logging.error(f"OpenAI API request timed out: {str(e)}")
                    default_response["error"] = "API request timed out, please try again with fewer images"
                else:
                    logging.error(f"OpenAI API request failed: {str(e)}")
                    default_response["error"] = f"API request failed: {str(e)}"
                return default_response
            
            # Parse and return the response
            result = json.loads(response.choices[0].message.content)
            logging.info("Successfully received OpenAI API response")
            
            # Ensure persona_descriptions exists in the result
            if generate_personas and "persona_descriptions" not in result:
                result["persona_descriptions"] = {
                    "athleisure_enthusiast": "N/A",
                    "performance_athlete": "N/A",
                    "value_conscious_buyer": "N/A"
                }
                
            return result
            
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing OpenAI API response: {str(e)}")
            default_response["error"] = f"Error parsing API response: {str(e)}"
            return default_response
            
        except Exception as e:
            logging.error(f"Error in OpenAI API call: {str(e)}")
            default_response["error"] = f"API Error: {str(e)}"
            return default_response
    
    except Exception as e:
        logging.error(f"Error in analyze_product: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        default_response["error"] = str(e)
        return default_response

def generate_persona_descriptions(product_data):
    """
    Generate persona-specific descriptions for an existing product.
    
    Args:
        product_data (dict): Existing product data including name, category, price,
                            detailed_description, and specifications
    
    Returns:
        dict: Generated persona-based descriptions
        
    Raises:
        Exception: If OpenAI API is not available or an error occurs during generation
    """
    # Default response in case of API failure
    default_response = {
        "persona_descriptions": {
            "athleisure_enthusiast": "N/A",
            "performance_athlete": "N/A",
            "value_conscious_buyer": "N/A"
        }
    }
    
    # Check if OpenAI client is initialized
    if openai is None:
        logging.error("OpenAI client is not initialized")
        default_response["error"] = "OpenAI client is not initialized"
        return default_response
        
    # Check if OpenAI API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        logging.error("OPENAI_API_KEY is not set in environment variables")
        default_response["error"] = "OpenAI API key is missing"
        return default_response
        
    # Make sure we have required product data
    if not product_data.get('product_name') and not product_data.get('name'):
        logging.error("Missing product name in data")
        default_response["error"] = "Missing product name"
        return default_response
        
    try:
        # Prepare messages for OpenAI API
        messages = [
            {
                "role": "system",
                "content": """
                You are a professional product content writer specializing in tailoring product descriptions
                to specific customer personas. You will be provided with existing product information.
                
                Create three distinct descriptions, each tailored to a specific customer persona, or mark as "N/A"
                when the product category doesn't fit a particular persona:
                
                1. Athleisure Enthusiast: Young professionals, college students, and trendsetters who wear sportswear for everyday fashion.
                Prioritize style, comfort, and brand appeal over pure performance.
                
                2. Performance Athlete: Runners, gym-goers, and sports players who need high-performance footwear and apparel.
                Focus on durability, cushioning, and sport-specific features.
                
                3. Value-Conscious Buyer: Everyday consumers looking for reliable sportswear at an affordable price.
                Prefer multi-purpose shoes for walking, running, or casual use. More price-sensitive but open to promotions and value deals.
                
                Respond with JSON in the following format:
                {
                    "persona_descriptions": {
                        "athleisure_enthusiast": "Description tailored to Athleisure Enthusiasts highlighting style and comfort aspects OR 'N/A' if product is not relevant",
                        "performance_athlete": "Description tailored to Performance Athletes highlighting performance and durability features OR 'N/A' if product is not relevant",
                        "value_conscious_buyer": "Description tailored to Value-Conscious Buyers highlighting value, versatility and affordability OR 'N/A' if product is not relevant"
                    }
                }
                
                Each description should be 2-3 sentences and focus on the aspects most important to that persona.
                If the product category doesn't fit a particular persona (e.g., a formal business suit for Performance Athletes),
                put "N/A" instead of a description.
                
                First analyze if the product is relevant to each persona based on category, description, and tags.
                Only write descriptions for personas where there's a clear fit.
                """
            }
        ]
        
        # Get product name, using fallback if needed
        product_name = product_data.get('product_name', product_data.get('name', 'Unknown Product'))
        
        # Add user message with product info
        user_content = f"""
        Please generate persona-specific descriptions for the following product:
        
        Product Name: {product_name}
        Category: {product_data.get('category', '')}
        Price: {product_data.get('price', '')}
        Description: {product_data.get('detailed_description', '')}
        Specifications: {', '.join(product_data.get('specifications', []))}
        Materials: {', '.join(product_data.get('materials', []))}
        Tags: {', '.join(product_data.get('tags', []))}
        """
        
        messages.append({"role": "user", "content": user_content})
        
        try:
            # Call OpenAI API
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            logging.info("Calling OpenAI API to generate persona descriptions")
            
            # Double-check that OpenAI client is initialized before making the API call
            if openai is None:
                logging.error("OpenAI client is None, cannot make API call for persona descriptions")
                default_response["error"] = "OpenAI client is not initialized"
                return default_response
                
            # Set timeout to avoid worker timeouts in Gunicorn
            try:
                logging.debug("Making API call for persona descriptions with timeout setting of 60.0 seconds")
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=800,
                    timeout=60.0  # Set a 60 second timeout for text-only requests
                )
                logging.debug("API call for persona descriptions completed successfully")
            except Exception as e:
                if "timeout" in str(e).lower():
                    logging.error(f"OpenAI API request for persona descriptions timed out: {str(e)}")
                    default_response["error"] = "API request for persona descriptions timed out"
                else:
                    logging.error(f"OpenAI API request for persona descriptions failed: {str(e)}")
                    default_response["error"] = f"API request failed: {str(e)}"
                return default_response
            
            # Parse the response
            try:
                result = json.loads(response.choices[0].message.content)
                logging.info("Successfully received OpenAI API response for persona descriptions")
                
                # Ensure persona_descriptions exists in the result
                if "persona_descriptions" not in result:
                    result["persona_descriptions"] = {
                        "athleisure_enthusiast": "N/A",
                        "performance_athlete": "N/A",
                        "value_conscious_buyer": "N/A"
                    }
                    
                return result
                
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing OpenAI API response for persona descriptions: {str(e)}")
                default_response["error"] = f"Error parsing API response: {str(e)}"
                return default_response
                
        except Exception as e:
            logging.error(f"Error in OpenAI API call for persona descriptions: {str(e)}")
            default_response["error"] = f"API Error: {str(e)}"
            return default_response
    
    except Exception as e:
        logging.error(f"Error in generate_persona_descriptions: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        default_response["error"] = str(e)
        return default_response
