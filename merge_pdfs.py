# SETUP: 
# Open your terminal or command prompt and run this command first:
# pip install pypdf

import os
from pypdf import PdfWriter

# ==========================================
# SETTINGS
# ==========================================

# 1. List the exact names of the PDFs you want to merge, in order.
# Make sure these files are in the same folder as this script.
pdf_files_to_merge =  [
    "docs/uni-assist-2026-docs/Erlaeuterung_Sprachstand_Edgar_Abasov.pdf",
    "docs/uni-assist-2026-docs/bachelor_de.pdf",
    "docs/uni-assist-2026-docs/German A2.2.pdf",                                                  
    "docs/uni-assist-2026-docs/German B1.1 Goethe.pdf",
    "docs/uni-assist-2026-docs/Deutsch Daf B1 FH Kiel.pdf",
    "docs/uni-assist-2026-docs/Deutsch Daf B2.1 FH Kiel.pdf",
    "docs/uni-assist-2026-docs/Studien-Immatrikulationsbescheinigung.pdf",
]

pdf_list_to_merge_2 = [
    "docs/uni-assist-2026-docs/Erlaeuterung_Master_Leistungen_Kiel_Edgar_Abasov.pdf.pdf",
    "docs/uni-assist-2026-docs/Transcript_Edgar.pdf",
]

pdf_list_to_merge_3 = [
    "docs/Zulassungen/btu.pdf",
    "docs/Zulassungen/chemnitz.pdf",
    "docs/Zulassungen/greifswald.pdf",
]


# 2. Name your final combined file.
output_filename = "docs/uni-assist-2026-docs/Zulassungsbescheide_Combined_Edgar_Abasov.pdf"


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

    # Write the combined PDF to the output file
    with open(output_name, "wb") as output_file:
        merger.write(output_file)
    
    merger.close()
    print(f"\nDone! Your combined PDF is saved as: {output_name}")

if __name__ == "__main__":
    combine_pdfs(pdf_list_to_merge_3, output_filename)