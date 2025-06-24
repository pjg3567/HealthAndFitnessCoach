#
# Description:
# This script populates the 'workouts' and 'workout_details' tables.
#
# VERSION 5 - REFACTORED:
# - All logic is now contained within a main function, `process_and_load_workout_details`,
#   to allow this script to be imported and called by a master pipeline script.
# - The function now accepts file paths as arguments.
# - It retains the advanced RPE parsing logic.
#

import pandas as pd
import xml.etree.ElementTree as ET
import os
import psycopg2
import re

# --- Database Connection Details ---
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"

# --- Data Parsing Functions ---

def parse_apple_health_workouts(file_path):
    """Parses the XML file specifically for Workout elements."""
    try:
        context = ET.iterparse(file_path, events=('start', 'end'))
        workouts = []
        for event, elem in context:
            if event == 'end' and elem.tag == 'Workout':
                workouts.append({
                    'start_date': elem.get('startDate'),
                    'end_date': elem.get('endDate'),
                    'workout_type': elem.get('workoutActivityType').replace('HKWorkoutActivityType', ''),
                    'duration_mins': float(elem.get('duration')),
                    'total_distance': float(elem.get('totalDistance', 0)),
                    'total_energy_burned': float(elem.get('totalEnergyBurned', 0))
                })
                elem.clear()
        return workouts
    except Exception as e:
        print(f"  - Error parsing Apple Health workouts: {e}")
        return []

def parse_rpe_from_note(note_text, set_order):
    """Extracts an RPE value from a note string for a specific set number."""
    if not isinstance(note_text, str):
        return None
    match = re.search(fr'Set\s{set_order}\sRPE\s=\s(\d+\.?\d*)', note_text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None

def parse_strong_workouts(file_path):
    """
    Parses the Strong CSV for detailed workout sets, with advanced RPE logic
    that can parse a single note for an entire exercise.
    """
    try:
        df = pd.read_csv(file_path)
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Clean numeric columns
        df['Set Order'] = pd.to_numeric(df['Set Order'], errors='coerce')
        df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
        df['Reps'] = pd.to_numeric(df['Reps'], errors='coerce')
        df['RPE'] = pd.to_numeric(df['RPE'], errors='coerce')
        df.dropna(subset=['Date', 'Exercise Name', 'Set Order'], inplace=True)
        
        df['Set Order'] = df['Set Order'].astype(int)

        processed_rows = []
        # Group by workout day and then by exercise name to process each exercise block
        for (date, exercise_name), group in df.groupby(['Date', 'Exercise Name']):
            
            # Find the single note for this entire exercise group (it's likely on the first set)
            notes_list = group['Notes'].dropna().unique()
            rpe_note_text = notes_list[0] if len(notes_list) > 0 else ""
            
            # Pre-parse all RPEs from that single note into a dictionary (e.g., {1: 8.0, 2: 8.5})
            rpe_from_note_dict = {}
            if isinstance(rpe_note_text, str):
                matches = re.findall(r'Set\s(\d+)\sRPE\s=\s(\d+\.?\d*)', rpe_note_text, re.IGNORECASE)
                for match in matches:
                    rpe_from_note_dict[int(match[0])] = float(match[1])

            # Apply the correct RPE to each set in the group
            for _, row in group.iterrows():
                set_order = row['Set Order']
                final_rpe = None
                
                # First, prioritize the native RPE column if it has data
                if pd.notna(row['RPE']) and row['RPE'] > 0:
                    final_rpe = row['RPE']
                # If not, check our dictionary parsed from the note
                elif set_order in rpe_from_note_dict:
                    final_rpe = rpe_from_note_dict[set_order]
                
                # Append the processed row with the final RPE value
                new_row = row.to_dict()
                new_row['final_rpe'] = final_rpe
                processed_rows.append(new_row)

        if not processed_rows:
            return pd.DataFrame()

        final_df = pd.DataFrame(processed_rows)
        # We now rename columns for consistency with the loading function
        final_df.rename(columns={'Date': 'start_date', 'Exercise Name': 'Exercise Name', 'Set Order': 'Set Order', 'Weight': 'Weight', 'Reps': 'Reps'}, inplace=True)
        return final_df

    except Exception as e:
        print(f"  - Error parsing Strong data: {e}")
        return pd.DataFrame()

def load_workouts_to_db(apple_workouts, strong_df):
    """Loads workout data into the 'workouts' and 'workout_details' tables."""
    conn = None
    try:
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
        cur = conn.cursor()

        # Load Apple Health Workouts
        apple_workouts_loaded = 0
        for workout in apple_workouts:
            cur.execute(
                "SELECT 1 FROM workouts WHERE start_date = %s AND workout_type = %s",
                (workout['start_date'], workout['workout_type'])
            )
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO workouts (start_date, end_date, workout_type, duration_mins, total_distance, total_energy_burned) VALUES (%(start_date)s, %(end_date)s, %(workout_type)s, %(duration_mins)s, %(total_distance)s, %(total_energy_burned)s)",
                    workout
                )
                apple_workouts_loaded += 1
        print(f"  - {apple_workouts_loaded} new Apple Health workouts loaded.")
        
        # Load Strong Workouts and their Details
        strong_sessions_processed = 0
        if not strong_df.empty:
            for workout_date, sets in strong_df.groupby('start_date'):
                cur.execute(
                    "SELECT workout_id FROM workouts WHERE start_date = %s AND workout_type = 'TraditionalStrengthTraining'",
                    (workout_date,)
                )
                result = cur.fetchone()
                if result:
                    strong_sessions_processed += 1
                    workout_id = result[0]
                    for _, set_row in sets.iterrows():
                        cur.execute(
                            "UPDATE workout_details SET weight = %s, reps = %s, rpe = %s WHERE workout_id = %s AND exercise_name = %s AND set_order = %s",
                            (set_row['Weight'], set_row['Reps'], set_row['final_rpe'], workout_id, set_row['Exercise Name'], set_row['Set Order'])
                        )
                        if cur.rowcount == 0: # If no row was updated, insert a new one
                            cur.execute(
                                "INSERT INTO workout_details (workout_id, exercise_name, set_order, weight, reps, rpe) VALUES (%s, %s, %s, %s, %s, %s)",
                                (workout_id, set_row['Exercise Name'], set_row['Set Order'], set_row['Weight'], set_row['Reps'], set_row['final_rpe'])
                            )
            print(f"  - Details updated for {strong_sessions_processed} Strong workout sessions.")

        conn.commit()
        cur.close()

    except Exception as e:
        print(f"  - An error occurred during database operation: {e}")
    finally:
        if conn is not None:
            conn.close()

def process_and_load_workout_details(apple_xml_path, strong_csv_path):
    """This is the main function that will be called by the master pipeline."""
    print("\n--- Processing Workout Details ---")
    apple_workouts = parse_apple_health_workouts(apple_xml_path)
    strong_workouts_df = parse_strong_workouts(strong_csv_path)

    if apple_workouts or not strong_workouts_df.empty:
        load_workouts_to_db(apple_workouts, strong_workouts_df)
    else:
        print("No new workout data to process.")

# This block allows the script to still be run by itself for testing
if __name__ == "__main__":
    print("This script is now designed to be imported as a module.")
    pass