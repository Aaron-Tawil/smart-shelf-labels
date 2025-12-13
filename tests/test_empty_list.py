
import os
import sys
import unittest.mock
import pandas as pd
from io import BytesIO

# Add current directory to path
sys.path.append(os.getcwd())

def test_empty_product_list():
    print("--- Testing Empty Product List Handling ---")
    
    # Mock firestore to simulate "all products already exist/filtered out"
    # We will mock 'filter_and_update_products' to return an empty DataFrame
    with unittest.mock.patch('signage_lib.filter_and_update_products') as mock_filter:
        mock_filter.return_value = pd.DataFrame() # Return empty DF
        
        try:
            from signage_lib import generate_llm_and_original_pdfs, generate_pdf_bytes
            
            # Create a dummy Excel file in memory
            df = pd.DataFrame({'מכירה': [1], 'שם פריט': ['Test'], 'ברקוד': ['123']})
            dummy_excel = BytesIO()
            df.to_excel(dummy_excel, index=False)
            dummy_excel.seek(0)
            
            print("1. Testing generate_llm_and_original_pdfs with empty filtered list...")
            llm_pdf, original_pdf, llm_excel = generate_llm_and_original_pdfs(dummy_excel)
            
            if llm_pdf is None and original_pdf is None and llm_excel is None:
                print("SUCCESS: generate_llm_and_original_pdfs returned (None, None, None) as expected.")
            else:
                print(f"FAILURE: generate_llm_and_original_pdfs returned {type(llm_pdf)}, {type(original_pdf)}, {type(llm_excel)}")

            dummy_excel.seek(0)
            print("2. Testing generate_pdf_bytes (legacy) with empty filtered list...")
            legacy_pdf = generate_pdf_bytes(dummy_excel)
            
            if legacy_pdf is None:
                print("SUCCESS: generate_pdf_bytes returned None as expected.")
            else:
                print(f"FAILURE: generate_pdf_bytes returned {type(legacy_pdf)}")
                
        except ImportError as e:
            print(f"Error importing signage_lib: {e}")
        except Exception as e:
            print(f"An error occurred during testing: {e}")

if __name__ == "__main__":
    test_empty_product_list()
