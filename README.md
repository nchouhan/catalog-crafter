# Product Catalog Generator with AI-Powered Descriptions

A Flask-based web application that leverages OpenAI's GPT-4o API to automatically generate rich, descriptive product content from images and basic attributes. The application provides an AI-enhanced product discovery platform with dynamic content generation and persona-based descriptions.

![Product Catalog Generator](attached_assets/image_1743151240102.png)

## Features

- **AI-Powered Content Generation**:
  - Upload up to 5 product images
  - Enter basic product information (name, category, price)
  - Generate comprehensive product descriptions, tags, and specifications using OpenAI
  - Automatically identify colors, materials, and target audience
  
- **Persona-Based Descriptions**:
  - Generate tailored descriptions for three customer personas:
    - Athleisure Enthusiasts
    - Performance Athletes
    - Value-Conscious Buyers
  - Intelligently identifies when a product doesn't apply to a persona
  
- **Smart Similar Product Detection**:
  - Prevent duplicate product uploads
  - Find and recommend complementary products
  - Display visual similarity scores
  
- **Search & Discovery**:
  - Full-text search across all product attributes
  - macOS Spotlight-inspired search interface (press `/` to activate)
  - Adaptive catalog filter layout

- **User Interface**:
  - Apple-inspired design with dark mode
  - Responsive layout for all devices
  - Intuitive drag-and-drop image upload

## Requirements

- Python 3.11 or higher
- OpenAI API key (GPT-4o)
- Modern web browser

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip/pip3 install -r requirements.txt
```

3. Set up environment variables by copying and editing the example file:

```bash
cp .env.example .env
```

4. Edit the `.env` file and add your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
SESSION_SECRET=your_random_secret_key_here
```

## Running the Application

Start the application in development mode:

```bash
python/python3 main.py
```

Or use Gunicorn for production:

```bash
gunicorn --bind 0.0.0.0:5000 main:app
```

Then visit `http://localhost:5000` in your browser.

## Project Structure

- `app.py`: Main Flask application with routes and logic
- `main.py`: Entry point for the application
- `utils/`: Helper modules
  - `openai_helper.py`: OpenAI API integration functions
  - `similar_products.py`: Product similarity detection functions
- `templates/`: HTML templates for the web interface
- `static/`: CSS, JavaScript, and image files
- `raw/`: Directory where uploaded images are stored
- `response/`: Directory where generated JSON responses are stored

## JSON Response Structure

The application generates a JSON response with the following structure:

```json
{
  "product_id": "unique_timestamp_identifier",
  "product_name": "Product Name",
  "category": "Product Category",
  "price": "Product Price",
  "short_description": "Brief summary of the product",
  "detailed_description": "Comprehensive product description",
  "specifications": ["spec1", "spec2", "..."],
  "tags": ["tag1", "tag2", "..."],
  "seo_keywords": ["keyword1", "keyword2", "..."],
  "target_audience": ["audience1", "audience2", "..."],
  "colors": ["color1", "color2", "..."],
  "materials": ["material1", "material2", "..."],
  "styles": ["style1", "style2", "..."],
  "persona_descriptions": {
    "athleisure_enthusiast": "Description for athleisure enthusiasts or N/A",
    "performance_athlete": "Description for performance athletes or N/A",
    "value_conscious_buyer": "Description for value-conscious buyers or N/A"
  },
  "image_urls": ["url1", "url2", "..."]
}
```

## Troubleshooting

- **Missing Product Descriptions**: If you see "N/A" or basic descriptions instead of AI-generated content, check that your OpenAI API key is valid and set correctly in the `.env` file.
- **Slow Response Times**: When uploading large images or multiple images, the AI processing may take longer. Consider using smaller images for faster results.
- **API Timeouts**: If you encounter API timeout errors, try again with fewer or smaller images.

## License

MIT License