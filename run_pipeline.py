#
# Description:
# This is the master data pipeline script for the AI Health Coach.
# It intelligently detects new or updated data export files and runs the
# necessary parsing and loading functions to update the PostgreSQL database.
#
# This script replaces the need to run the individual loading scripts manually.
#

import os
from datetime import datetime
import re
import psycopg2

# --- Custom Modules ---
from load_daily_summary import process_and_load_daily_summary
from load_workout_details import process_and_load_workout_details

# --- Configuration ---
DATA_EXPORTS_DIR = "data_exports"
APPLE_HEALTH_DIR = os.path.join(DATA_EXPORTS_DIR, "apple_health_export")

# --- Database Connection Details ---
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"


# --- Database Connection & State Management ---

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        host=DB_HOST,
        port=DB_PORT
    )

def get_last_run_timestamp():
    """
    Retrieves the timestamp of the most recent successful pipeline run from the database.
    Returns the unix epoch (0) if no previous run is found.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT run_timestamp FROM pipeline_runs ORDER BY run_timestamp DESC LIMIT 1")
        last_run = cur.fetchone()
        cur.close()
        if last_run:
            # Convert the datetime object from the database to a float timestamp
            return last_run[0].timestamp()
        else:
            # This is the first run, so we return 0 to process all existing files.
            return 0.0
    except Exception as e:
        print(f"  - Could not retrieve last run timestamp: {e}")
        return 0.0 # Default to 0 on error to ensure we process files
    finally:
        if conn is not None:
            conn.close()

def record_successful_run():
    """Inserts the current timestamp into the pipeline_runs table."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Insert the current time, with timezone information
        cur.execute("INSERT INTO pipeline_runs (run_timestamp) VALUES (NOW())")
        conn.commit()
        cur.close()
        print("  - Successfully recorded new pipeline run in the database.")
    except Exception as e:
        print(f"  - Could not record pipeline run: {e}")
    finally:
        if conn is not None:
            conn.close()

# --- File Detection Functions ---

def find_new_files(last_run_timestamp):
    """
    Scans the data directory and finds files modified since the last pipeline run.
    Returns a dictionary of new file paths.
    """
    new_files = {
        'apple_health': None,
        'strong': None,
        'macrofactor': []
    }
    has_new_files = False

    # Define file paths
    strong_csv_path = os.path.join(DATA_EXPORTS_DIR, "strong.csv")
    apple_health_xml_path = os.path.join(APPLE_HEALTH_DIR, "export.xml")

    # Check for Strong CSV
    if os.path.exists(strong_csv_path) and os.path.getmtime(strong_csv_path) > last_run_timestamp:
        print("- New 'strong.csv' detected.")
        has_new_files = True

    # Check for Apple Health XML
    if os.path.exists(apple_health_xml_path) and os.path.getmtime(apple_health_xml_path) > last_run_timestamp:
        print("- New Apple Health 'export.xml' detected.")
        has_new_files = True

    # Check for MacroFactor XLSX files
    mf_pattern = re.compile(r"MacroFactor-.*\.(xlsx|csv)")
    for filename in os.listdir(DATA_EXPORTS_DIR):
        if mf_pattern.match(filename):
            file_path = os.path.join(DATA_EXPORTS_DIR, filename)
            if os.path.getmtime(file_path) > last_run_timestamp:
                print(f"- New MacroFactor file detected: {filename}")
                # We only need to know that at least one MF file is new
                has_new_files = True
                break # Exit loop once we find one new file
    
    # If any file is new, we need to gather the paths for all required files
    # for the processing functions.
    if has_new_files:
        new_files['apple_health'] = apple_health_xml_path
        new_files['strong'] = strong_csv_path
        
        # Get all MacroFactor files, as the summary script handles unification
        all_mf_files = [os.path.join(DATA_EXPORTS_DIR, f) for f in os.listdir(DATA_EXPORTS_DIR) if mf_pattern.match(f)]
        if all_mf_files:
            new_files['macrofactor'] = all_mf_files

    return has_new_files, new_files


# --- Main Pipeline Logic ---

def main():
    """
    Main function to run the entire data pipeline.
    It checks for new files based on the last successful run and updates the database.
    """
    print("--- Starting Health Data Pipeline ---")
    
    # 1. Get the last successful run time from the database
    last_run_ts = get_last_run_timestamp()
    print(f"Checking for files updated since: {datetime.fromtimestamp(last_run_ts)}")

    # 2. Find any new or updated files
    has_new_files, file_paths = find_new_files(last_run_ts)

    # 3. Run pipelines if new files were found
    if has_new_files:
        print("\nNew data detected. Running processing scripts...")
        
        if not all(file_paths.values()):
            print("\nWarning: Not all data files were found, but proceeding with available files.")
            print(f"  - Apple Health: {'Found' if file_paths['apple_health'] and os.path.exists(file_paths['apple_health']) else 'Missing'}")
            print(f"  - Strong: {'Found' if file_paths['strong'] and os.path.exists(file_paths['strong']) else 'Missing'}")
            print(f"  - MacroFactor: {'Found' if file_paths['macrofactor'] else 'Missing'}")

        # Run the daily summary pipeline
        process_and_load_daily_summary(
            apple_xml_path=file_paths['apple_health'],
            strong_csv_path=file_paths['strong'],
            macrofactor_files=file_paths['macrofactor']
        )

        # Run the workout details pipeline
        process_and_load_workout_details(
            apple_xml_path=file_paths['apple_health'],
            strong_csv_path=file_paths['strong']
        )
        
        # 4. Record a new successful run in the database
        record_successful_run()
        print("\n--- Pipeline finished successfully ---")

    else:
        print("\nNo new or updated data files found. Database is up-to-date.")
        print("--- Pipeline finished ---")


# --- Main execution block ---
if __name__ == "__main__":
    main()