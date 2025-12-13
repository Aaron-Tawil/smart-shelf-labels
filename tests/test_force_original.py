import unittest
from unittest.mock import patch
import pandas as pd
from io import BytesIO
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import signage_lib

class TestSignageLogic(unittest.TestCase):
    
    @patch('signage_lib.clean_product_names_batch')
    def test_force_original_name(self, mock_clean):
        # Setup mock LLM response
        mock_clean.return_value = {"Bad Name": "Cleaned Name"}
        
        # Create Data
        data = {
            'ברקוד': ['123', '456'],
            'שם פריט': ['Bad Name', 'Keep Original'],
            'מכירה': [10, 20],
            'אלץ הדפסה': ['True', 'True'], # Force print to bypass Firestore check
            'אלץ שם מקורי': ['', 'Yes']
        }
        df = pd.DataFrame(data)
        
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        # Mock register_fonts to avoid issues if fonts missing
        with patch('signage_lib.register_fonts', return_value=False):
             # Mock filter_and_update_products to just return the df (bypass Firestore)
            with patch('signage_lib.filter_and_update_products', return_value=df):
                llm_pdf, orig_pdf, llm_excel = signage_lib.generate_llm_and_original_pdfs(excel_buffer)
        
        # Verify
        self.assertIsNotNone(llm_excel)
        
        # Read the generated Excel
        df_result = pd.read_excel(llm_excel)
        
        # print("Result Columns:", df_result.columns)
        # print(df_result[['שם פריט', 'Cleaned Name']])
        
        # Check Item 1: Should be cleaned
        row1 = df_result.iloc[0]
        self.assertEqual(row1['שם פריט'], 'Bad Name')
        self.assertEqual(row1['Cleaned Name'], 'Cleaned Name')
        
        # Check Item 2: Should be original
        row2 = df_result.iloc[1]
        self.assertEqual(row2['שם פריט'], 'Keep Original')
        self.assertEqual(row2['Cleaned Name'], 'Keep Original')
        
        # Verify LLM was called only for the first item
        mock_clean.assert_called_with(['Bad Name'])

if __name__ == '__main__':
    unittest.main()
