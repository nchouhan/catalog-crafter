# Product Catalog Generator

A Flask-based web application that uses OpenAI's GPT-4o API to generate professional product descriptions, specifications, and tags from product images and basic attributes.

## Features

- Upload up to 5 product images
- Enter basic product information (name, category, price)
- Generate comprehensive product descriptions using AI
- Download product data as JSON for easy integration with other systems
- Responsive and modern UI design

## Requirements

- Python 3.11 or higher
- OpenAI API key

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and add your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
SESSION_SECRET=your_random_secret_key_here
```

## Running the Application

Start the application with:

```bash
python main.py
```

Or use Gunicorn for production:

```bash
gunicorn --bind 0.0.0.0:5000 main:app
```

Then visit `http://localhost:5000` in your browser.

## Project Structure

- `app.py`: Main Flask application with routes and logic
- `main.py`: Entry point for the application
- `utils/openai_helper.py`: OpenAI API integration functions
- `templates/`: HTML templates for the web interface
- `static/`: CSS, JavaScript, and image files
- `raw/`: Directory where uploaded images are stored
- `response/`: Directory where generated JSON responses are stored

## API Response Structure

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
  "image_urls": ["url1", "url2", "..."]
}
```

## License

MIT License