import requests
from PIL import Image
import os
from io import BytesIO

def download_and_optimize_image(url, output_path, max_width=800, quality=85):
    """Download image from URL, optimize it, and save locally."""
    try:
        response = requests.get(url)
        response.raise_for_status()

        # Open image with PIL
        img = Image.open(BytesIO(response.content))

        # Convert to RGB if necessary (for JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if larger than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save optimized image
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        print(f"Optimized and saved: {output_path}")

    except Exception as e:
        print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    # Optimize logo
    logo_url = "https://res.cloudinary.com/dks3wmj5e/image/upload/v1758458435/Logo1_mrhhfw.png"
    download_and_optimize_image(logo_url, "static/images/logo_optimized.jpg", max_width=200, quality=90)

    # Optimize hero image
    hero_url = "https://images.unsplash.com/photo-1517336714731-489689fd1ca8"
    download_and_optimize_image(hero_url, "static/images/hero_optimized.jpg", max_width=1200, quality=85)
