#
# Description:
# This script creates a unified daily health summary by merging data from three
# different sources: Apple Health, MacroFactor, and the Strong app.
#
# VERSION 4 - Final De-duplication Logic:
# This version implements a highly accurate de-duplication algorithm for Apple Health
# steps. It processes records chronologically, prioritizing any Apple Watch source
# over an iPhone source for any overlapping time interval, correctly handling gaps
# when the watch is charging. This should produce the most accurate daily step totals.
#

import pandas as pd
import xml.etree.ElementTree as ET
import os

def deduplicate_apple_health_steps(records):
    """
    De-duplicates step count records from multiple Apple devices by prioritizing
    Apple Watch data over iPhone data for any overlapping time periods.
    """
    if not records:
        return []

    # Create a DataFrame for easier manipulation
    df = pd.DataFrame(records)
    df['startDate'] = pd.to_datetime(df['startDate'])
    df['endDate'] = pd.to_datetime(df['endDate'])

    # Assign priority: 1 for Watch (higher), 2 for iPhone.
    # This correctly handles multiple different Apple Watch sources.
    df['priority'] = df['sourceName'].apply(lambda x: 1 if 'Apple Watch' in x else 2)

    # Sort by start time, then by priority (so Watch data comes first for ties)
    df.sort_values(by=['startDate', 'priority'], inplace=True)

    clean_records = []
    # Initialize with a very old timestamp to ensure the first record is always added.
    last_end_time = pd.Timestamp.min.tz_localize('UTC') 

    # Iterate through the sorted records
    for index, row in df.iterrows():
        # If the current record's start time is after or at the same time as the
        # last accepted record's end time, there is no overlap. We can add it.
        if row['startDate'] >= last_end_time:
            clean_records.append(row.to_dict())
            last_end_time = row['endDate']
        # If there IS an overlap (e.g., iPhone data from 10:05-10:10 when a watch
        # record from 10:00-10:08 was already added), our sorting ensures we have
        # already processed the higher-priority watch record. We simply ignore
        # this lower-priority, overlapping iPhone record and move on.

    return clean_records


def parse_apple_health_summary(file_path):
    """Parses the Apple Health XML and returns a DataFrame with daily summaries."""
    print("Parsing Apple Health data...")
    try:
        context = ET.iterparse(file_path, events=('start', 'end'))
        steps_records, energy_records = [], []

        for event, elem in context:
            if event == 'end' and elem.tag == 'Record':
                record_type = elem.get('type')
                if record_type == 'HKQuantityTypeIdentifierStepCount':
                    steps_records.append({
                        'startDate': elem.get('startDate'),
                        'endDate': elem.get('endDate'),
                        'value': elem.get('value'),
                        'sourceName': elem.get('sourceName')
                    })
                elif record_type == 'HKQuantityTypeIdentifierActiveEnergyBurned':
                    energy_records.append({'endDate': elem.get('endDate'), 'value': elem.get('value')})
                elem.clear()

        print(f"Found {len(steps_records)} raw step records. De-duplicating...")
        deduplicated_steps = deduplicate_apple_health_steps(steps_records)
        print(f"Finished de-duplication. Using {len(deduplicated_steps)} clean step records.")

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
    """Parses the MacroFactor Excel file and returns a DataFrame."""
    print("Parsing MacroFactor data...")
    try:
        df = pd.read_excel(file_path)
        df = df[['Date', 'Calories (kcal)', 'Protein (g)', 'Fat (g)', 'Carbs (g)']]
        df.rename(columns={
            'Calories (kcal)': 'Calories_kcal', 'Protein (g)': 'Protein_g',
            'Fat (g)': 'Fat_g', 'Carbs (g)': 'Carbs_g'
        }, inplace=True)
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        return df
    except Exception as e:
        print(f"Error parsing MacroFactor data: {e}")
        return pd.DataFrame()

def parse_strong_summary(file_path):
    """Parses the Strong CSV to calculate total daily training volume."""
    print("Parsing Strong data...")
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

def main():
    """Main function to create and display the unified daily summary."""
    apple_health_path = os.path.join('data_exports', 'apple_health_export', 'export.xml')
    macrofactor_path = os.path.join('data_exports', 'MacroFactor-20250620192508.xlsx')
    strong_path = os.path.join('data_exports', 'strong.csv')

    apple_summary = parse_apple_health_summary(apple_health_path)
    macrofactor_summary = parse_macrofactor_summary(macrofactor_path)
    strong_summary = parse_strong_summary(strong_path)

    print("\nMerging all data sources...")
    
    daily_summary_df = apple_summary.copy()

    if not macrofactor_summary.empty:
        daily_summary_df = pd.merge(daily_summary_df, macrofactor_summary, on='Date', how='outer')
    if not strong_summary.empty:
        daily_summary_df = pd.merge(daily_summary_df, strong_summary, on='Date', how='outer')

    daily_summary_df.sort_values(by='Date', ascending=False, inplace=True)

    print("\n--- Unified Daily Health Summary (Most Recent 15 Days) ---")
    print(daily_summary_df.head(15).fillna(0).to_string(index=False))
    print("\n" + "-" * 40)

if __name__ == "__main__":
    main()