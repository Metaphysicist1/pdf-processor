# SETUP:
# If you haven't installed the library yet, run this in your terminal:
# pip install pypdf

import os
from pypdf import PdfWriter

# ==========================================
# SETTINGS
# ==========================================

# 1. The name of the file you want to shrink
input_pdf = "input.pdf"

# 2. The name for your new, smaller file
output_pdf = "compressed.pdf"

# 3. Image quality (1 to 100).
# Lower number = smaller file, but blurrier images.
# 60 to 80 is usually a great balance.
image_quality = 65


# ==========================================
# SCRIPT LOGIC
# ==========================================
def compress_my_pdf(input_path, output_path, quality):
    if not os.path.exists(input_path):
        print(f"Error: The file '{input_path}' was not found in this folder.")
        return

    print(f"Compressing '{input_path}'... This might take a few seconds.")

    writer = PdfWriter(clone_from=input_path)

    for page in writer.pages:
        page.compress_content_streams(level=9)
        for img in page.images:
            try:
                img.replace(img.image, quality=quality)
            except Exception:
                pass

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    original_size = os.path.getsize(input_path) / (1024 * 1024)
    new_size = os.path.getsize(output_path) / (1024 * 1024)

    print(f"\nDone! Your smaller PDF is saved as: {output_pdf}")
    print(f"Original size: {original_size:.2f} MB")
    print(f"New size:      {new_size:.2f} MB")


if __name__ == "__main__":
    compress_my_pdf(input_pdf, output_pdf, image_quality)
