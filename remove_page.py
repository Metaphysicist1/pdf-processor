import os
from pypdf import PdfReader, PdfWriter

# ==========================================
# SETTINGS
# ==========================================

# 1. The document you want to edit
input_pdf = "Abasov_Edgar_Application_Documents_2026.pdf"

# 2. The name for the new document with the page removed
output_pdf = "Abasov_Edgar_Application_Documents_2026_without_page.pdf"

# 3. The exact page number you want to remove (e.g., 3 means the 3rd page)
page_to_remove = 12


# ==========================================
# SCRIPT LOGIC
# ==========================================
def remove_pdf_page(input_path, output_path, page_num):
    # Safety check: Does the file exist?
    if not os.path.exists(input_path):
        print(f"Error: The file '{input_path}' was not found.")
        return

    reader = PdfReader(input_path)
    writer = PdfWriter()

    total_pages = len(reader.pages)
    
    # Python starts counting at 0, but humans start at 1. 
    # We subtract 1 so you can just type the normal page number in the settings.
    target_index = page_num - 1

    # Safety check: Is the page number valid?
    if target_index < 0 or target_index >= total_pages:
        print(f"Error: You asked to remove page {page_num}, but the document only has {total_pages} pages.")
        return

    print(f"Opening '{input_path}' (Total pages: {total_pages})")
    print(f"Removing page {page_num}...")

    # Loop through all the pages
    for index, page in enumerate(reader.pages):
        # If it is NOT the page we want to remove, keep it
        if index != target_index:
            writer.add_page(page)

    # Save the new PDF
    with open(output_path, "wb") as output_file:
        writer.write(output_file)

    print(f"\nDone! Your new PDF is saved as: {output_path}")

if __name__ == "__main__":
    remove_pdf_page(input_pdf, output_pdf, page_to_remove)