# 2024-05-31
import runpod
import io
import base64
import os 
from rembg import remove, new_session
from dotenv import load_dotenv
import requests
from PIL import Image
import boto3
import logging
import time

load_dotenv()  # Load API key
#boto3.set_stream_logger('botocore', level=logging.DEBUG)

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION")

#print('++++++++, AWS_ACCESS_KEY',AWS_ACCESS_KEY,'AWS_SECRET_KEY',AWS_SECRET_KEY,'AWS_REGION',AWS_REGION)

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

def remove_background_and_create_mask(
    input_image_path,
    model_type='u2net',  # Default model type
    use_gpu=True,  # Option to use GPU
    alpha_matting=True,
    alpha_matting_foreground_threshold=240,
    alpha_matting_background_threshold=10,
    alpha_matting_erode_size=10,
    post_process_mask=True,
    always_return_png=True
):
    # Cast to string (must be path for Replicate to download images from URL)
    input_image_path = str(input_image_path)

    if input_image_path is None:
        raise ValueError("Input image path cannot be None.")
    if not os.path.isfile(input_image_path):
        raise FileNotFoundError(f"No file found at {input_image_path}")

    if model_type not in ['u2net', 'u2netp', 'u2net_human_seg', 'u2net_cloth_seg', 'silueta', 'isnet-general-use']:
        raise ValueError(f"Invalid model type: {model_type}")

    input_image = Image.open(input_image_path).convert("RGB")

    # Create a session for the specified model type, enabling GPU if available
    session = new_session(model_type, use_gpu=use_gpu)

    remove_options = {
        'alpha_matting': alpha_matting,
        'alpha_matting_foreground_threshold': alpha_matting_foreground_threshold,
        'alpha_matting_background_threshold': alpha_matting_background_threshold,
        'alpha_matting_erode_size': alpha_matting_erode_size,
        'session': session,
        'post_process_mask': post_process_mask
    }

    output_image = remove(input_image, **remove_options)
    output_image = output_image.convert("RGBA")

    base_path, ext = os.path.splitext(input_image_path)
    if always_return_png or ext.lower() in ['.png']:  # Save as png if png or we want to always return png
        no_bg_image_path = base_path + "_nobg.png"
    else:  # i.e., ext.lower() in ['.jpg', '.jpeg']:
        no_bg_image_path = base_path + "_nobg.jpg"

    output_image.save(no_bg_image_path)

    return no_bg_image_path

def handler(event):
    input_image_url = event['input']['image']
    
    # Download the image and save it locally
    local_image_path = "downloaded_image.jpg"
    try:
        local_image_path = download_image(input_image_url, local_image_path)
    except Exception as e:
        return {
            'status': 500,
            'message': f'Error downloading image: {str(e)}'
        }

   # print('Image URL:', input_image_url)
    
    try:
        no_bg_image_path = remove_background_and_create_mask(local_image_path)
    except Exception as e:
        return {
            'status': 500,
            'message': f'Error processing image: {str(e)}'
        }

    #print('No background image path:', no_bg_image_path)
    try:
        output = upload_to_s3(no_bg_image_path)
    except Exception as e:
        return {
            'status': 500,
            'message': f'Error uploading image: {str(e)}'
        }

    return {
        'status': 200,
        'message': 'Success',
        'output':output
    }

def upload_to_s3(img_path):

    print('++++++++ UPL S3')
    
    current_time = int(time.time())
    file_name = f"{current_time}.png"
    
    s3.upload_file(img_path, 'deggie2-storage-51e396f8bd59f-main', f'rembg-runpod-out/{file_name}')

    return f'https://d33jynxyjhnjq1.cloudfront.net/rembg-runpod-out/{file_name}'
    
def download_image(image_url, save_path):
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return save_path
    else:
        raise Exception(f"Failed to download image. Status code: {response.status_code}")

# Example event to test the handler function
'''
test_event = {
    "input": {
        "image": "https://d1plw52kc43y11.cloudfront.net/public/generations/Remyx_00001_.png"
    }
}
'''

runpod.serverless.start({"handler": handler})  # "return_aggregate_stream": True makes the creation streamable; /stream

#runpod.serverless.start({"handler": handler,"return_aggregate_stream": True})  # "return_aggregate_stream": True makes the creation streamable; /stream