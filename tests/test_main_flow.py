import os
import sys
import unittest.mock
from io import BytesIO

# Add current directory to path
sys.path.append(os.getcwd())

def test_email_logic():
    print("--- Testing Email Reply Logic (Dual PDF Generation) ---")
    
    input_path = os.path.join("example", "example.xlsx")
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    # We need to mock firestore so it fails to connect. 
    # This triggers the 'except' block in 'filter_and_update_products', 
    # which returns the full dataframe (skipping the "already printed" check).
    with unittest.mock.patch('signage_lib.firestore.Client') as mock_firestore:
        mock_firestore.side_effect = Exception("Mocked Firestore Connection Failure")
        
        try:
            from signage_lib import generate_llm_and_original_pdfs
            
            print(f"Reading {input_path}...")
            with open(input_path, 'rb') as f:
                excel_content = f.read()
            
            excel_file = BytesIO(excel_content)
            
            print("Generating PDFs (LLM & Original) & Excel...")
            # This is the core function called by the email handler in main.py
            llm_pdf, original_pdf, llm_excel = generate_llm_and_original_pdfs(excel_file)
            
            # Save results
            with open("test_llm_signs.pdf", "wb") as f:
                f.write(llm_pdf.getvalue())
            
            with open("test_original_signs.pdf", "wb") as f:
                f.write(original_pdf.getvalue())

            with open("test_generated_names.xlsx", "wb") as f:
                f.write(llm_excel.getvalue())
                
            print(f"\nSuccess!")
            print(f"1. test_llm_signs.pdf ({len(llm_pdf.getvalue())} bytes) - Names cleaned by AI")
            print(f"2. test_original_signs.pdf ({len(original_pdf.getvalue())} bytes) - Original names")
            print(f"3. test_generated_names.xlsx ({len(llm_excel.getvalue())} bytes) - Generated Names Excel")
            
        except ImportError as e:
            print(f"Error importing signage_lib: {e}")
        except Exception as e:
            print(f"An error occurred during generation: {e}")

if __name__ == "__main__":
    test_email_logic()
