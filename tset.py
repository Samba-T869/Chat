import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

# Debug: Check if environment variables are loaded
cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
api_key = os.getenv('CLOUDINARY_API_KEY')
api_secret = os.getenv('CLOUDINARY_API_SECRET')

print(f"Cloud Name: {cloud_name}")
print(f"API Key: {api_key}")
print(f"API Secret: {api_secret}")

if not all([cloud_name, api_key, api_secret]):
    print("ERROR: One or more Cloudinary environment variables are missing!")
else:
    print("All Cloudinary environment variables loaded successfully.")

cloudinary.config(
    cloud_name=cloud_name,
    api_key=api_key,
    api_secret=api_secret,
    secure=True
)