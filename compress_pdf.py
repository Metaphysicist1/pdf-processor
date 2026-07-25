# SETUP: 
# If you haven't installed the library yet, run this in your terminal:
# pip install pypdf

import os
from pypdf import PdfWriter

# ==========================================
# SETTINGS
# ==========================================

# 1. The name of the file you want to shrink
input_pdf = "Dein biometrisches Passbild.pdf"       

# 2. The name for your new, smaller file
output_pdf = "compressed_biometrisches_Passbild.pdf" 

# 3. Image quality (1 to 100). 
# Lower number = smaller file size, but blurrier images.
# 60 to 80 is usually a great balance.
image_quality = 65                     


# ==========================================
# SCRIPT LOGIC
# ==========================================
def compress_my_pdf(input_path, output_path, quality):
    # Check if the file actually exists before starting
    if not os.path.exists(input_path):
        print(f"Error: The file '{input_path}' was not found in this folder.")
        return

    print(f"Compressing '{input_path}'... This might take a few seconds.")
    
    # Load the PDF into the writer
    writer = PdfWriter(clone_from=input_path)

    # Loop through every page to apply compression
    for page in writer.pages:
        # Method 1: Compress the text and vector drawings (lossless)
        page.compress_content_streams(level=9)
        
        # Method 2: Compress the images (lossy)
        for img in page.images:
            try:
                img.replace(img.image, quality=quality)
            except Exception:
                # If a specific image format is unsupported, just skip it safely
                pass 

    # Save the final compressed PDF
    with open(output_path, "wb") as output_file:
        writer.write(output_file)
        
    # Calculate and print the space saved
    original_size = os.path.getsize(input_path) / (1024 * 1024)
    new_size = os.path.getsize(output_path) / (1024 * 1024)
    
    print(f"\nDone! Your smaller PDF is saved as: {output_path}")
    print(f"Original size: {original_size:.2f} MB")
    print(f"New size:      {new_size:.2f} MB")

if __name__ == "__main__":
    for file in os.listdir("docs/dsh"):
        if file.endswith(".pdf"):
            input_pdf = f"docs/dsh/{file}"
            output_pdf = file.replace(".pdf", "_compressed.pdf")
            image_quality = 65
            compress_my_pdf(input_pdf, output_pdf, image_quality)
            print(f"Compressed {input_pdf} to {output_pdf}")