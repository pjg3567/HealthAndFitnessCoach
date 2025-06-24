#
# Description:
# This script reads the 'export.xml' file from an Apple Health data export.
# It is now modularized to extract and process multiple types of data:
# 1. Aggregates total daily step counts.
# 2. Aggregates total daily active energy burned.
# 3. Extracts a list of all workout sessions.
#
# The script demonstrates a more robust and scalable parsing strategy.
#

import xml.etree.ElementTree as ET
import pandas as pd
import os
from collections import Counter

# --- Configuration ---
# We can define the record types we're interested in at the top.
# This makes it easy to add more data types in the future.
TARGET_RECORDS = [
    'HKQuantityTypeIdentifierStepCount',
    'HKQuantityTypeIdentifierActiveEnergyBurned'
]
WORKOUT_TYPE = 'Workout'


def parse_health_records(file_path):
    """
    Parses the XML file for specific record types (like steps and calories).
    
    Args:
        file_path (str): The path to the export.xml file.

    Returns:
        dict: A dictionary where keys are record types and values are lists
              of dictionaries, each representing a raw data point.
    """
    try:
        context = ET.iterparse(file_path, events=('start', 'end'))
        all_records = {rec_type: [] for rec_type in TARGET_RECORDS}
        
        for event, elem in context:
            if event == 'end' and elem.tag == 'Record':
                record_type = elem.get('type')
                if record_type in TARGET_RECORDS:
                    all_records[record_type].append({
                        'endDate': elem.get('endDate'),
                        'value': elem.get('value')
                    })
                elem.clear()
        return all_records
    except Exception as e:
        print(f"Error parsing records: {e}")
        return {rec_type: [] for rec_type in TARGET_RECORDS}

def parse_workouts(file_path):
    """
    Parses the XML file specifically for Workout elements.

    Args:
        file_path (str): The path to the export.xml file.

    Returns:
        list: A list of dictionaries, each representing a workout.
    """
    try:
        context = ET.iterparse(file_path, events=('start', 'end'))
        workouts = []
        for event, elem in context:
            if event == 'end' and elem.tag == WORKOUT_TYPE:
                workouts.append({
                    'workoutActivityType': elem.get('workoutActivityType'),
                    'duration': elem.get('duration'),
                    'totalDistance': elem.get('totalDistance'),
                    'totalEnergyBurned': elem.get('totalEnergyBurned'),
                    'startDate': elem.get('startDate'),
                    'endDate': elem.get('endDate')
                })
                elem.clear()
        return workouts
    except Exception as e:
        print(f"Error parsing workouts: {e}")
        return []

def aggregate_daily_data(records_list, value_col_name='TotalValue'):
    """
    Aggregates a list of records into daily sums using pandas.

    Args:
        records_list (list): A list of record dictionaries.
        value_col_name (str): The desired name for the aggregated value column.

    Returns:
        DataFrame: A pandas DataFrame with daily aggregated data.
    """
    if not records_list:
        return pd.DataFrame()

    df = pd.DataFrame(records_list)
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df['endDate'] = pd.to_datetime(df['endDate'])
    df.dropna(inplace=True)
    df.set_index('endDate', inplace=True)
    
    daily_total = df['value'].resample('D').sum()
    daily_df = daily_total.reset_index()
    daily_df.rename(columns={'endDate': 'Date', 'value': value_col_name}, inplace=True)
    daily_df = daily_df[daily_df[value_col_name] > 0]
    daily_df[value_col_name] = daily_df[value_col_name].astype(int)
    
    return daily_df

def main():
    """Main function to run the data parsing and analysis."""
    file_path = os.path.join('data_exports', 'apple_health_export', 'export.xml')
    
    if not os.path.exists(file_path):
        print(f"ERROR: The file was not found at '{file_path}'.")
        return

    print("--- Parsing Health Data from XML ---")
    print("This may take a few minutes...\n")

    # Parse all target data types
    health_records = parse_health_records(file_path)
    workouts = parse_workouts(file_path)

    print("--- Daily Step Count Summary ---")
    print("Displaying the 10 most recent days:\n")
    daily_steps = aggregate_daily_data(health_records[TARGET_RECORDS[0]], 'TotalSteps')
    if not daily_steps.empty:
        print(daily_steps.tail(10).to_string(index=False))
    else:
        print("No step data found.")
    print("\n" + "-"*40)

    print("\n--- Daily Active Energy Summary ---")
    print("Displaying the 10 most recent days:\n")
    daily_energy = aggregate_daily_data(health_records[TARGET_RECORDS[1]], 'TotalActiveEnergy_kcal')
    if not daily_energy.empty:
        print(daily_energy.tail(10).to_string(index=False))
    else:
        print("No active energy data found.")
    print("\n" + "-"*40)

    print("\n--- Workout Summary ---")
    print(f"Found a total of {len(workouts)} workouts.")
    print("Displaying the 10 most recent workouts:\n")
    if workouts:
        # Sort workouts by start date, descending
        workouts.sort(key=lambda x: x['startDate'], reverse=True)
        for workout in workouts[:10]:
            # Clean up the workout type name for display
            activity_name = workout['workoutActivityType'].replace('HKWorkoutActivityType', '')
            print(f"Date: {workout['startDate'][:10]} | Type: {activity_name:<25} | Duration: {float(workout['duration']):.1f} mins")
    else:
        print("No workout data found.")
    print("\n" + "-"*40)


if __name__ == "__main__":
    main()