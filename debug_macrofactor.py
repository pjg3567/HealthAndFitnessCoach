import pandas as pd
import os

# --- Configuration ---
DATA_EXPORTS_DIR = "data_exports"
MACROFACTOR_FILE_NAME = "MacroFactor-20250623221345.xlsx" # Make sure this filename is correct

# --- Main Debug Logic ---
def debug_excel_file():
    """
    This function reads the specified Excel file and prints its structure
    to help us debug the parsing issue.
    """
    file_path = os.path.join(DATA_EXPORTS_DIR, MACROFACTOR_FILE_NAME)

    if not os.path.exists(file_path):
        print(f"Error: The file was not found at {file_path}")
        return

    try:
        print(f"--- Reading file: {file_path} ---")
        
        # Read the excel file
        df = pd.read_excel(file_path)
        
        print("\n1. Column Headers Detected by Pandas:")
        print(df.columns.tolist())
        
        print("\n2. First 5 Rows of the DataFrame:")
        print(df.head())

    except Exception as e:
        print(f"\nAn error occurred while trying to read the file: {e}")


# --- Main execution block ---
if __name__ == "__main__":
    debug_excel_file()