import pandas as pd
import os

# --- Configuration ---
DATA_EXPORTS_DIR = "data_exports"
MACROFACTOR_FILE_NAME = "MacroFactor-20250623221345.xlsx"

# --- Main Debug Logic ---
def debug_excel_structure():
    """
    This function reads the Excel file without assuming a header row
    to show us the raw structure of the top of the file.
    """
    file_path = os.path.join(DATA_EXPORTS_DIR, MACROFACTOR_FILE_NAME)

    if not os.path.exists(file_path):
        print(f"Error: The file was not found at {file_path}")
        return

    try:
        print(f"--- Reading file with header=None: {file_path} ---")
        
        # Read the excel file, telling pandas there is NO header row.
        # This lets us see the file's raw structure.
        df = pd.read_excel(file_path, engine='openpyxl', header=None)
        
        print("\n--- First 10 rows as seen by Pandas (raw) ---")
        # Use to_string() to prevent columns from being truncated
        print(df.head(10).to_string())

    except Exception as e:
        print(f"\nAn error occurred while trying to read the file: {e}")


# --- Main execution block ---
if __name__ == "__main__":
    debug_excel_structure()