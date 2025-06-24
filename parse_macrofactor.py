#
# Description:
# This script reads the nutrition and weight data exported from the MacroFactor app.
# It uses the pandas library to load a specific .xlsx file into a DataFrame
# and then displays the first 10 rows to give an overview of the data structure.
#
# This is the first step in processing our nutrition data.
#

import pandas as pd
import os

def analyze_macrofactor_data():
    """
    Reads and displays the first few rows of the MacroFactor app's Excel export.
    """
    try:
        # --- 1. Define the file path ---
        # Updated to use the specific Excel filename you provided.
        file_name = 'MacroFactor-20250620192508.xlsx'
        file_path = os.path.join('data_exports', file_name)

        print(f"Attempting to read Excel file from: {file_path}")

        # --- 2. Read the file into a pandas DataFrame ---
        # Changed to pd.read_excel() to handle .xlsx files.
        # The 'openpyxl' engine will be used automatically.
        df = pd.read_excel(file_path)

        print("File read successfully.")
        
        # --- 3. Display the first 10 rows of the DataFrame ---
        print(f"\n--- MacroFactor Data from '{file_name}' (First 10 Rows) ---")
        # pd.set_option is used to make sure we can see all columns if the table is wide
        pd.set_option('display.max_columns', None) 
        print(df.head(10))
        print("\n" + "-" * 40)


    except FileNotFoundError:
        print(f"\nERROR: The file '{file_name}' was not found at '{file_path}'.")
        print("Please make sure the file exists in the 'data_exports' folder.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Main execution block ---
if __name__ == "__main__":
    analyze_macrofactor_data()