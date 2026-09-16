# SETUP:
# Open your terminal or command prompt and run this command first:
# pip install pypdf

import os
from pypdf import PdfWriter

# ==========================================
# SETTINGS
# ==========================================

# 1. List the exact names of the PDFs you want to merge, in order.
# Make sure these files are in the same folder as this script (or use full paths).
pdf_files_to_merge = [
    "input_1.pdf",
    "input_2.pdf",
    "input_3.pdf",
]

# 2. Name your final combined file.
output_filename = "merged.pdf"


# ==========================================
# SCRIPT LOGIC
# ==========================================
def combine_pdfs(pdf_list, output_name):
    merger = PdfWriter()
    print("Starting the merge process...\n")

    for pdf in pdf_list:
        if os.path.exists(pdf):
            merger.append(pdf)
            print(f"Successfully added: {pdf}")
        else:
            print(f"Warning: The file '{pdf}' was not found and will be skipped.")

    with open(output_name, "wb") as output_file:
        merger.write(output_file)

    merger.close()
    print(f"\nDone! Your combined PDF is saved as: {output_name}")


if __name__ == "__main__":
    combine_pdfs(pdf_files_to_merge, output_filename)
