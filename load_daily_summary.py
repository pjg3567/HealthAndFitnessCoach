#
# Description:
# This script is the first part of our data pipeline. It performs the full
# unification of daily data from Apple Health, Strong, and MacroFactor, and
# then loads the final summary into the 'daily_summaries' table in our
# PostgreSQL database.
#
# VERSION 2 - REFACTORED:
# - All logic is now contained within a main function to allow this script
#   to be imported and called by a master pipeline script.
# - The function now accepts file paths as arguments for better control.
#

import pandas as pd
import xml.etree.ElementTree as ET
import os
import psycopg2
from psycopg2.extras import execute_values
import re

# --- Database Connection Details ---
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"

# --- Data Parsing and Unification Functions ---

def deduplicate_apple_health_steps(records):
    """De-duplicates step count records from multiple Apple devices."""
    if not records: return []
    df = pd.DataFrame(records)
    df['startDate'] = pd.to_datetime(df['startDate'])
    df['endDate'] = pd.to_datetime(df['endDate'])
    df['priority'] = df['sourceName'].apply(lambda x: 1 if 'Apple Watch' in x else 2)
    df.sort_values(by=['startDate', 'priority'], inplace=True)
    clean_records = []
    last_end_time = pd.Timestamp.min.tz_localize('UTC')
    for _, row in df.iterrows():
        if row['startDate'] >= last_end_time:
            clean_records.append(row.to_dict())
            last_end_time = row['endDate']
    return clean_records

def parse_apple_health_summary(file_path):
    """Parses Apple Health XML for steps and energy."""
    try:
        context = ET.iterparse(file_path, events=('start', 'end'))
        steps_records, energy_records = [], []
        for event, elem in context:
            if event == 'end' and elem.tag == 'Record':
                record_type = elem.get('type')
                if record_type == 'HKQuantityTypeIdentifierStepCount':
                    steps_records.append({'startDate': elem.get('startDate'),'endDate': elem.get('endDate'),'value': elem.get('value'),'sourceName': elem.get('sourceName')})
                elif record_type == 'HKQuantityTypeIdentifierActiveEnergyBurned':
                    energy_records.append({'endDate': elem.get('endDate'), 'value': elem.get('value')})
                elem.clear()
        
        deduplicated_steps = deduplicate_apple_health_steps(steps_records)
        steps_df = aggregate_daily_data(deduplicated_steps, 'TotalSteps')
        energy_df = aggregate_daily_data(energy_records, 'ActiveEnergy_kcal')
        
        if not steps_df.empty and not energy_df.empty:
            return pd.merge(steps_df, energy_df, on='Date', how='outer')
        return steps_df if not steps_df.empty else energy_df
    except Exception as e:
        print(f"Error parsing Apple Health data: {e}")
        return pd.DataFrame()

def aggregate_daily_data(records_list, value_col_name):
    """Helper function to aggregate records into daily sums."""
    if not records_list: return pd.DataFrame()
    df = pd.DataFrame(records_list)
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df['endDate'] = pd.to_datetime(df['endDate']).dt.tz_localize(None)
    df.dropna(inplace=True)
    df.set_index('endDate', inplace=True)
    daily_total = df['value'].resample('D').sum()
    daily_df = daily_total.reset_index()
    daily_df.rename(columns={'endDate': 'Date', 'value': value_col_name}, inplace=True)
    daily_df = daily_df[daily_df[value_col_name] > 0]
    daily_df[value_col_name] = daily_df[value_col_name].astype(int)
    return daily_df

def parse_macrofactor_summary(file_path):
    """
    Parses MacroFactor Excel file by skipping the problematic header row
    and manually assigning clean column names.
    """
    try:
        # Define our own clean column names
        clean_column_names = [
            'Date', 
            'Calories_kcal', 
            'Protein_g', 
            'Fat_g', 
            'Carbs_g'
        ]

        # Read the excel file, SKIPPING the header row entirely.
        df = pd.read_excel(
            file_path, 
            engine='openpyxl', 
            header=None,  # Treat the file as if it has no header
            skiprows=1,   # Skip the first row (the problematic header)
            names=clean_column_names # Assign our own clean names
        )

        # Convert data types now that we have a clean DataFrame
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        numeric_cols = ['Calories_kcal', 'Protein_g', 'Fat_g', 'Carbs_g']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop any rows where the date could not be parsed
        df.dropna(subset=['Date'], inplace=True)
        
        df['Date'] = df['Date'].dt.tz_localize(None)
        return df
    except Exception as e:
        print(f"Error parsing MacroFactor data: {e}")
        return pd.DataFrame()

def parse_strong_summary(file_path):
    """Parses Strong CSV for total daily volume."""
    try:
        df = pd.read_csv(file_path)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
        df['Reps'] = pd.to_numeric(df['Reps'], errors='coerce')
        df.dropna(subset=['Weight', 'Reps'], inplace=True)
        df['Volume'] = df['Weight'] * df['Reps']
        daily_volume = df.groupby(df['Date'].dt.date)['Volume'].sum().reset_index()
        daily_volume.rename(columns={'Volume': 'StrengthVolume'}, inplace=True)
        daily_volume['StrengthVolume'] = daily_volume['StrengthVolume'].astype(int)
        daily_volume['Date'] = pd.to_datetime(daily_volume['Date'])
        return daily_volume
    except Exception as e:
        print(f"Error parsing Strong data: {e}")
        return pd.DataFrame()

def get_unified_daily_summary(apple_xml_path, strong_csv_path, macrofactor_files):
    """Runs the full parsing and merging pipeline."""
    apple_summary = parse_apple_health_summary(apple_xml_path)
    strong_summary = parse_strong_summary(strong_csv_path)
    
    # Process all new MacroFactor files
    macrofactor_summaries = [parse_macrofactor_summary(f) for f in macrofactor_files]
    all_macrofactor_data = pd.concat(macrofactor_summaries, ignore_index=True)

    print("\nMerging all data sources...")
    daily_summary_df = apple_summary.copy()
    if not all_macrofactor_data.empty:
        daily_summary_df = pd.merge(daily_summary_df, all_macrofactor_data, on='Date', how='outer')
    if not strong_summary.empty:
        daily_summary_df = pd.merge(daily_summary_df, strong_summary, on='Date', how='outer')
    
    daily_summary_df.sort_values(by='Date', ascending=False, inplace=True)
    return daily_summary_df.fillna(0)

def load_data_to_db(df):
    """Connects to the DB and loads the DataFrame into the daily_summaries table."""
    conn = None
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
        cur = conn.cursor()
        
        data_to_load = [tuple(x) for x in df.to_numpy()]
        
        upsert_sql = """
            INSERT INTO daily_summaries (date, total_steps, active_energy_kcal, calories_kcal, protein_g, fat_g, carbs_g, strength_volume)
            VALUES %s
            ON CONFLICT (date) DO UPDATE SET
                total_steps = EXCLUDED.total_steps,
                active_energy_kcal = EXCLUDED.active_energy_kcal,
                calories_kcal = EXCLUDED.calories_kcal,
                protein_g = EXCLUDED.protein_g,
                fat_g = EXCLUDED.fat_g,
                carbs_g = EXCLUDED.carbs_g,
                strength_volume = EXCLUDED.strength_volume;
        """
        execute_values(cur, upsert_sql, data_to_load)
        conn.commit()
        cur.close()
        print(f"\nSuccessfully loaded/updated {len(df)} rows into the 'daily_summaries' table.")
    except Exception as e:
        print(f"An error occurred during database operation: {e}")
    finally:
        if conn is not None:
            conn.close()

def process_and_load_daily_summary(apple_xml_path, strong_csv_path, macrofactor_files):
    """This is the main function that will be called by the master pipeline."""
    print("\n--- Processing Daily Summaries ---")
    unified_summary = get_unified_daily_summary(apple_xml_path, strong_csv_path, macrofactor_files)
    
    if not unified_summary.empty:
        load_data_to_db(unified_summary)
    else:
        print("No summary data to load.")

# This block allows the script to still be run by itself for testing
if __name__ == "__main__":
    # For standalone testing, you would define the paths here, for example:
    # DATA_EXPORTS_DIR = "data_exports"
    # apple_path = os.path.join(DATA_EXPORTS_DIR, 'apple_health_export', 'export.xml')
    # strong_path = os.path.join(DATA_EXPORTS_DIR, 'strong.csv')
    # mf_files = [os.path.join(DATA_EXPORTS_DIR, f) for f in os.listdir(DATA_EXPORTS_DIR) if f.startswith("MacroFactor")]
    # process_and_load_daily_summary(apple_path, strong_path, mf_files)
    print("This script is now designed to be imported as a module.")
    pass
