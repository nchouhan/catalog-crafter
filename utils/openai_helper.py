import os
import json
import logging
from openai import OpenAI

# Get OpenAI API key from environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY not found in environment variables!")

# Initialize OpenAI client
openai = OpenAI(api_key=OPENAI_API_KEY)

def analyze_product(product_data, base64_images):
    """
    Analyze product images and generate descriptions and tags using OpenAI API.
    
    Args:
        product_data (dict): Dict containing product name, category, and price
        base64_images (list): List of base64-encoded images
    
    Returns:
        dict: Generated product description and tags
    """
    try:
        # Prepare messages for OpenAI API
        messages = [
            {
                "role": "system",
                "content": """
                You are a professional product content writer. Analyze the provided product images 
                and information to create detailed, compelling product descriptions and relevant tags.
                Respond with JSON in the following format:
                {
                    "short_description": "Brief 1-2 sentence summary",
                    "detailed_description": "Detailed paragraph(s) about the product's features, benefits, and use cases",
                    "specifications": ["spec1", "spec2", ...],
                    "tags": ["tag1", "tag2", ...],
                    "seo_keywords": ["keyword1", "keyword2", ...],
                    "target_audience": ["audience1", "audience2", ...]
                }
                Be professional, specific, and make the descriptions marketable.
                """
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
        
        # Call OpenAI API
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=1000
        )
        
        # Parse and return the response
        result = json.loads(response.choices[0].message.content)
        logging.debug(f"OpenAI API Response: {result}")
        return result
    
    except Exception as e:
        logging.error(f"Error in OpenAI API call: {str(e)}")
        return {
            "error": str(e),
            "short_description": "Could not generate description",
            "detailed_description": "An error occurred while processing your request.",
            "specifications": [],
            "tags": [],
            "seo_keywords": [],
            "target_audience": []
        }
