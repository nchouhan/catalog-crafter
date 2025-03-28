import os
import json
import uuid
import time
import logging
import requests
import tempfile
import subprocess
from pathlib import Path
import base64
import shutil
import random
from PIL import Image, ImageFilter, ImageEnhance
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Check if OpenAI API key is available
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None
if not OPENAI_API_KEY:
    logging.warning("OPENAI_API_KEY not found in environment variables!")
else:
    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)

def generate_video_openai(product_data, max_duration=10):
    """
    Generate a video using product images with smooth transitions and movements.
    
    Args:
        product_data (dict): Product data including images, name, description, etc.
        max_duration (int): Maximum duration of the video in seconds
        
    Returns:
        tuple: (success, video_path or error_message)
    """
    # Create temp directory if it doesn't exist
    temp_dir = os.path.abspath("temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create raw directory if it doesn't exist
    raw_dir = os.path.abspath('raw')
    os.makedirs(raw_dir, exist_ok=True)
        
    # Generate a unique filename for the video based on product_id and timestamp
    product_id = product_data.get('product_id', str(uuid.uuid4()))
    video_filename = f"{product_id}_video.mp4"
    video_path = os.path.join(raw_dir, video_filename)
    
    logging.info(f"Starting video generation for product {product_id}")
    
    try:
        # Extract image paths from product data
        # First try extracting from local paths if available
        image_paths = []
        
        # First look for local image paths
        if 'images' in product_data and product_data['images']:
            image_paths = product_data['images']
        elif 'raw_images' in product_data and product_data['raw_images']:
            image_paths = product_data['raw_images']
        
        # If no direct paths, try to extract from image_urls which contain full URL paths
        if not image_paths and 'image_urls' in product_data and product_data['image_urls']:
            for url in product_data['image_urls']:
                try:
                    # Extract filename from URL
                    filename = url.split('/')[-1]
                    local_path = os.path.join(raw_dir, filename)
                    if os.path.exists(local_path):
                        image_paths.append(local_path)
                except:
                    pass
        
        # If still no paths, look for any image in raw folder with product_id prefix
        if not image_paths:
            file_prefix = f"{product_id}_"
            raw_files = [f for f in os.listdir(raw_dir) if os.path.isfile(os.path.join(raw_dir, f))]
            for file in raw_files:
                if file.startswith(file_prefix) and file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    image_paths.append(os.path.join(raw_dir, file))
        
        # Sort paths to ensure consistent ordering
        image_paths.sort()
        
        if not image_paths:
            logging.error(f"No images found in product data for product ID: {product_id}")
            logging.error(f"Product data keys: {list(product_data.keys())}")
            return False, "No images found for video generation"
            
        # Make sure all image paths exist
        valid_image_paths = [path for path in image_paths if os.path.exists(path)]
        logging.info(f"Found {len(valid_image_paths)} valid image paths out of {len(image_paths)}")
        
        if not valid_image_paths:
            logging.error(f"No valid image paths found. Paths tried: {image_paths}")
            return False, "No valid image paths found for video generation"
        
        # Get product information for metadata
        product_name = product_data.get('product_name', product_data.get('name', 'Product'))
        description = product_data.get('detailed_description', '')
        category = product_data.get('category', '')
        price = product_data.get('price', '')
        
        logging.info(f"Generating video for {product_name} with {len(valid_image_paths)} images")
        
        # Create enhanced versions of images with different effects
        # Use original images directly without enhancement for simplicity
        logging.info("Using original images to create video (skipping enhancement to avoid potential issues)")
        
        # Generate video using FFmpeg with a simple approach
        # Limiting to max 6 seconds and 3 images for better performance
        video_duration = min(5, int(len(valid_image_paths) * 1.0))
        
        # Limit to 3 images maximum to ensure performance
        limited_image_paths = valid_image_paths[:min(3, len(valid_image_paths))]
        
        # Log the actual paths we'll be using
        logging.info(f"Using these {len(limited_image_paths)} images for video generation:")
        for idx, path in enumerate(limited_image_paths):
            logging.info(f"  Image {idx+1}: {path} (exists: {os.path.exists(path)})")
        
        success, result = generate_ffmpeg_video(
            limited_image_paths,
            video_path, 
            duration=video_duration,
            title=product_name
        )
        
        # Clean up temporary files (JPEG conversions from WebP)
        for path in limited_image_paths:
            # Only clean temp files created during conversion
            if path.startswith("temp/") and os.path.exists(path):
                try:
                    os.remove(path)
                    logging.info(f"Cleaned up temp file: {path}")
                except Exception as e:
                    logging.error(f"Error removing temp file {path}: {str(e)}")
        
        if success:
            logging.info(f"Successfully generated video at {result}")
            return True, result
        else:
            logging.error(f"Failed to generate video: {result}")
            
            # If FFmpeg video generation fails, try OpenAI DALL-E as fallback
            return generate_dalle_image_fallback(product_data, product_name, description, video_path)
            
    except Exception as e:
        logging.error(f"Error generating video: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"

def create_enhanced_image(image_path, img_index, variation, product_id):
    """
    Create an enhanced version of the image with zoom, pan, or other effects.
    
    Args:
        image_path (str): Path to the original image
        img_index (int): Index of the image in the sequence
        variation (int): Variation number for different effects
        product_id (str): Product ID for file naming
        
    Returns:
        str: Path to the enhanced image
    """
    try:
        # Open the image
        img = Image.open(image_path)
        
        # Ensure image is in RGB mode
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # Apply different effects based on variation
        if variation == 0:
            # Zoom in effect (crop a slightly smaller area)
            width, height = img.size
            crop_percentage = 0.05 + (random.random() * 0.1)  # 5-15% crop
            crop_width = int(width * crop_percentage)
            crop_height = int(height * crop_percentage)
            img = img.crop((
                crop_width,
                crop_height,
                width - crop_width,
                height - crop_height
            ))
            # Resize back to original dimensions
            img = img.resize((width, height), Image.LANCZOS)
            
        elif variation == 1:
            # Pan effect (crop one side more than the other)
            width, height = img.size
            pan_direction = random.choice(['left', 'right', 'up', 'down'])
            crop_percentage = 0.08 + (random.random() * 0.12)  # 8-20% crop
            
            if pan_direction == 'left':
                img = img.crop((
                    int(width * crop_percentage),
                    0,
                    width,
                    height
                ))
            elif pan_direction == 'right':
                img = img.crop((
                    0,
                    0,
                    width - int(width * crop_percentage),
                    height
                ))
            elif pan_direction == 'up':
                img = img.crop((
                    0,
                    int(height * crop_percentage),
                    width,
                    height
                ))
            else:  # down
                img = img.crop((
                    0,
                    0,
                    width,
                    height - int(height * crop_percentage)
                ))
            
            # Resize back to original dimensions
            img = img.resize((width, height), Image.LANCZOS)
            
        elif variation == 2:
            # Enhance brightness, contrast, or apply subtle filter
            effect_type = random.choice(['brightness', 'contrast', 'sharpen', 'none'])
            
            if effect_type == 'brightness':
                factor = 0.9 + (random.random() * 0.3)  # 0.9-1.2
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(factor)
            elif effect_type == 'contrast':
                factor = 0.9 + (random.random() * 0.4)  # 0.9-1.3
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(factor)
            elif effect_type == 'sharpen':
                img = img.filter(ImageFilter.SHARPEN)
        
        # Save the enhanced image to a temporary file - using absolute path
        temp_dir = os.path.abspath("temp")
        output_filename = os.path.join(temp_dir, f"{product_id}_img{img_index}_var{variation}.jpg")
        img.save(output_filename, quality=95)
        
        return output_filename
        
    except Exception as e:
        logging.error(f"Error creating enhanced image: {str(e)}")
        return None

def generate_ffmpeg_video(image_paths, output_path, duration=10, title=None):
    """
    Generate a video from images using FFmpeg with smooth transitions.
    
    Args:
        image_paths (list): List of image paths to include in the video
        output_path (str): Path where the output video will be saved
        duration (float): Total duration of the video in seconds
        title (str): Optional title to overlay on the video
        
    Returns:
        tuple: (success, output_path or error_message)
    """
    try:
        if not image_paths:
            return False, "No images provided for video generation"
        
        # Check if each image path exists before proceeding
        valid_images = []
        for img_path in image_paths:
            if os.path.exists(img_path) and os.path.isfile(img_path):
                # Verify it's an actual image file
                try:
                    with Image.open(img_path) as img:
                        img_format = img.format
                        if img_format in ('JPEG', 'PNG', 'GIF', 'BMP'):
                            valid_images.append(img_path)
                        elif img_format == 'WEBP':
                            # For WebP images, convert to JPEG first
                            temp_dir = os.path.abspath('temp')
                            os.makedirs(temp_dir, exist_ok=True)
                            jpeg_path = os.path.join(temp_dir, f"{os.path.basename(img_path).split('.')[0]}.jpg")
                            try:
                                img = img.convert('RGB')
                                img.save(jpeg_path, 'JPEG', quality=95)
                                valid_images.append(jpeg_path)
                                logging.info(f"Converted WebP image to JPEG: {img_path} -> {jpeg_path}")
                            except Exception as conv_err:
                                logging.error(f"Failed to convert WebP image: {img_path} - {str(conv_err)}")
                        else:
                            logging.warning(f"Skipping non-image file: {img_path} (format: {img_format})")
                except Exception as img_err:
                    logging.warning(f"Skipping invalid image file: {img_path} (error: {str(img_err)})")
            else:
                logging.warning(f"Image path does not exist or is not a file: {img_path}")
        
        if not valid_images:
            return False, "No valid image files found for video generation"
            
        image_paths = valid_images
        
        # Use a simple approach that we know works reliably
        logging.info(f"Generating video with {len(image_paths)} images for {duration} seconds total")
        
        # Limit to 5 images max for better performance
        if len(image_paths) > 5:
            logging.info(f"Using only the first 5 images of {len(image_paths)} for better video quality")
            image_paths = image_paths[:5]
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.abspath('temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Initialize input_file to None (will be set if needed in the single image case)
        input_file = None
        # Initialize filter_complex_str for title addition later
        filter_complex_str = ""
        
        # For more dynamic videos, we'll use the xfade filter instead of concat demuxer
        if len(image_paths) >= 2:
            # Create a random transition style
            transition_styles = ['fade', 'fadeblack', 'fadegrays', 'distance', 'wipeup', 'wipedown', 'wipeleft', 'wiperight', 'zoomin']
            transition = random.choice(transition_styles)
            
            # Set up a more dynamic filter chain for transitions
            # First set up the first image
            filter_complex = []
            inputs = []
            
            # Add each input
            for i, img_path in enumerate(image_paths):
                inputs.append('-loop')
                inputs.append('1')  # Loop each image
                inputs.append('-t')
                inputs.append('2')  # Each image has a 2 second duration
                inputs.append('-i')
                inputs.append(img_path)
            
            # Create dynamic transitions between images
            filter_parts = []
            for i in range(len(image_paths)-1):
                transition = random.choice(transition_styles)
                filter_parts.append(f"[{i}:v][{i+1}:v]xfade=transition={transition}:duration=0.5:offset=1.5[v{i}];")
            
            # Final command
            cmd = [
                'ffmpeg',
                '-y',
            ]
            
            # Add input arguments
            cmd.extend(inputs)
            
            # Build filter complex
            filter_complex_str = ''.join(filter_parts)
            # Remove the last semicolon and add the final output
            filter_complex_str = filter_complex_str[:-1] + f"[vout]"
            
            cmd.extend([
                '-filter_complex', filter_complex_str,
                '-map', '[vout]',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28',
                '-r', '24',
                '-t', str(min(5, duration)),
                output_path
            ])
        else:
            # Fallback to basic approach for single image
            input_file = os.path.join(temp_dir, f'input_{uuid.uuid4()}.txt')
            with open(input_file, 'w') as f:
                # Each image should display for an equal portion of the total duration
                image_duration = max(2.0, duration / len(image_paths))
                for img_path in image_paths:
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {image_duration}\n")
                
                # Add the last image again (required by FFmpeg)
                f.write(f"file '{image_paths[-1]}'\n")
            
            # Basic FFmpeg command for single image
            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', input_file,
                '-vf', f"fps=24,scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2,format=yuv420p,zoompan=z='min(zoom+0.0015,1.5)':d=125:s=960x540",
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28', 
                '-r', '24',
                '-t', str(min(5, duration)),
                output_path
            ]
        
        # Add title if provided
        if title and len(image_paths) >= 2:
            # Sanitize title for ffmpeg command (remove quotes and special characters)
            sanitized_title = title.replace("'", "").replace('"', '').replace(':', ' -')
            # For the dynamic xfade filter approach, we need to add a title in a different way
            # We'll add a text overlay to the final output
            filter_complex_str = filter_complex_str.replace("[vout]", "[vtmp]")
            filter_complex_str += f";[vtmp]drawtext=text='{sanitized_title}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-th-30:box=1:boxcolor=black@0.5:boxborderw=5[vout]"
            
            # Update the command with the new filter complex
            for i, arg in enumerate(cmd):
                if arg == '-filter_complex':
                    cmd[i+1] = filter_complex_str
                    break
                    
        elif title:
            # For the basic approach, add title differently
            sanitized_title = title.replace("'", "").replace('"', '').replace(':', ' -')
            # For the zoompan filter, we need to add drawtext at the end
            for i, arg in enumerate(cmd):
                if arg.startswith('-vf'):
                    cmd[i] = arg + f",drawtext=text='{sanitized_title}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=h-th-30:box=1:boxcolor=black@0.5:boxborderw=5"
                    break
        
        # Execute FFmpeg command with a timeout of 25 seconds to prevent worker timeouts
        logging.info(f"Executing FFmpeg command with timeout: {' '.join(cmd)}")
        try:
            # Check if output directory exists, create if needed
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logging.info(f"Created output directory: {output_dir}")
            
            # Ensure we have write permissions
            logging.info(f"Testing write permissions for output path: {output_path}")
            try:
                with open(output_path, 'w') as test_file:
                    test_file.write('test')
                os.remove(output_path)
                logging.info("Write permission test passed")
            except Exception as write_test_err:
                logging.error(f"Write permission test failed: {str(write_test_err)}")
                return False, f"Cannot write to output path: {str(write_test_err)}"
            
            # Run FFmpeg with timeout
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            
            # Log the stdout/stderr for debugging
            logging.debug(f"FFmpeg stdout: {result.stdout}")
            logging.error(f"FFmpeg stderr: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            logging.error("FFmpeg process timed out after 25 seconds")
            return False, "FFmpeg process timed out. Try with fewer or smaller images."
        
        # Clean up the temporary input file
        try:
            if input_file and os.path.exists(input_file):
                os.remove(input_file)
        except Exception as cleanup_err:
            logging.warning(f"Failed to remove temporary input file: {str(cleanup_err)}")
        
        if result.returncode != 0:
            logging.error(f"FFmpeg error: {result.stderr}")
            return False, f"FFmpeg error: {result.stderr}"
        
        # Check if video file was created and is a valid video file
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            # Verify it's a real video file by checking the file signature
            try:
                with open(output_path, 'rb') as f:
                    header = f.read(12)  # Read the first 12 bytes
                
                # MP4 files should start with 'ftyp'
                if b'ftyp' in header:
                    logging.info(f"Successfully generated valid MP4 video at {output_path}")
                    return True, output_path
                else:
                    logging.error("Generated file is not a valid MP4 video (missing 'ftyp' signature)")
                    try:
                        # Remove the invalid file
                        os.remove(output_path)
                    except Exception as remove_err:
                        logging.warning(f"Failed to remove invalid video file: {str(remove_err)}")
                    return False, "FFmpeg did not create a valid MP4 video"
            except Exception as check_err:
                logging.error(f"Error checking video file: {str(check_err)}")
                return False, "Error verifying video file format"
        else:
            logging.error("FFmpeg ran successfully but no video was created")
            return False, "FFmpeg ran successfully but no video was created"
            
    except Exception as e:
        logging.error(f"Error in FFmpeg video generation: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False, f"Error: {str(e)}"

def generate_dalle_image_fallback(product_data, product_name, description, video_path):
    """
    Generate a proper video using individual images if FFmpeg fails.
    This creates a simple slideshow style video without fancy effects.
    
    Args:
        product_data (dict): Product data
        product_name (str): Name of the product
        description (str): Product description
        video_path (str): Path where the video will be saved
        
    Returns:
        tuple: (success, output_path or error_message)
    """
    logging.info("Using basic slideshow video generation as fallback")
    
    try:
        # Create temp directory if it doesn't exist
        temp_dir = os.path.abspath('temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Extract image paths from product data
        image_paths = []
        if 'images' in product_data and product_data['images']:
            image_paths = product_data['images']
        elif 'raw_images' in product_data and product_data['raw_images']:
            image_paths = product_data['raw_images']
            
        # Validate images to ensure they can be processed
        valid_image_paths = []
        for img_path in image_paths:
            if os.path.exists(img_path) and os.path.isfile(img_path):
                try:
                    with Image.open(img_path) as img:
                        img_format = img.format
                        if img_format in ('JPEG', 'PNG', 'GIF', 'BMP'):
                            valid_image_paths.append(img_path)
                        elif img_format == 'WEBP':
                            # For WebP images, convert to JPEG first
                            temp_dir = os.path.abspath('temp')
                            os.makedirs(temp_dir, exist_ok=True)
                            jpeg_path = os.path.join(temp_dir, f"{os.path.basename(img_path).split('.')[0]}_fallback.jpg")
                            try:
                                img = img.convert('RGB')
                                img.save(jpeg_path, 'JPEG', quality=95)
                                valid_image_paths.append(jpeg_path)
                                logging.info(f"Fallback: Converted WebP image to JPEG: {img_path} -> {jpeg_path}")
                            except Exception as conv_err:
                                logging.error(f"Fallback: Failed to convert WebP image: {img_path} - {str(conv_err)}")
                        else:
                            logging.warning(f"Fallback: Skipping non-supported image file: {img_path} (format: {img_format})")
                except Exception as img_err:
                    logging.warning(f"Fallback: Skipping invalid image file: {img_path} (error: {str(img_err)})")
            else:
                logging.warning(f"Fallback: Image path does not exist or is not a file: {img_path}")
        
        image_paths = valid_image_paths
            
        # If we have images, create a very basic slideshow
        if image_paths:
            # Extremely simple approach for fallback - just create a file with all images in sequence
            # First, limit to maximum 3 images
            image_paths = image_paths[:min(3, len(image_paths))]
            
            # Create a temporary file for input
            input_file = os.path.join(temp_dir, f'fallback_{uuid.uuid4()}.txt')
            with open(input_file, 'w') as f:
                # Each image for 1.5 seconds
                for img_path in image_paths:
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration 1.5\n")
                
                # Add the last image again (required by FFmpeg)
                f.write(f"file '{image_paths[-1]}'\n")
            
            # Very basic command with minimal processing
            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', input_file,
                '-vf', f"fps=24,scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2,format=yuv420p,drawtext=text='{product_name}':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=h-th-20:box=1:boxcolor=black@0.5:boxborderw=5",
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28',
                '-t', '5',   # Limit to 5 seconds
                '-r', '24',  # 24fps is enough
                video_path
            ]
            
            # Execute command with timeout
            logging.info(f"Executing fallback FFmpeg command with timeout: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            except subprocess.TimeoutExpired:
                logging.error("Fallback FFmpeg process timed out after 20 seconds")
                return False, "Video generation timed out. Try with fewer or smaller images."
            
            if result.returncode == 0 and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                # Check if it's a real video
                with open(video_path, 'rb') as f:
                    header = f.read(12)
                if b'ftyp' in header:
                    logging.info(f"Created fallback slideshow video at {video_path}")
                    return True, video_path
        
        # If we get here, the fallback video creation failed or we had no images
        # Instead of using DALL-E image, let's return an error message
        logging.error("Could not create a valid video. Please try again with different images.")
        return False, "Video generation failed. Please try again with different images."
    
    except Exception as e:
        logging.error(f"Error in fallback video generation: {str(e)}")
        return False, f"Video generation error: {str(e)}"

def get_video_for_product(product_id):
    """
    Get video path for a product if it exists.
    
    Args:
        product_id (str): Product ID
        
    Returns:
        str or None: Path to video if it exists, None otherwise
    """
    # Use absolute path
    raw_dir = os.path.abspath('raw')
    video_filename = f"{product_id}_video.mp4"
    video_path = os.path.join(raw_dir, video_filename)
    
    if os.path.exists(video_path):
        return video_path
    
    return None