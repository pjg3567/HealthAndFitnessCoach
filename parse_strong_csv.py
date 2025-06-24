#
# Description:
# This script reads the workout data from the Strong app CSV export.
# It prompts the user to enter an exercise name, then calculates the
# total training volume (Weight * Reps) for that exercise for each
# workout session where it was performed.
#
# This demonstrates how to filter, clean, and perform calculations on the
# strength training data to track progress over time.
#

import pandas as pd
import os

def analyze_exercise_volume():
    """
    Analyzes the Strong app CSV to calculate total volume for a specific exercise.
    """
    try:
        # --- 1. Define and read the file path ---
        file_name = 'strong.csv'
        file_path = os.path.join('data_exports', file_name)
        print(f"Reading Strong workout data from: {file_path}")
        
        # Load the entire CSV into a DataFrame
        df = pd.read_csv(file_path)

        # --- 2. Get user input for the exercise to analyze ---
        # input() pauses the script and waits for the user to type something.
        print("\nNote: Exercise names must match the CSV exactly (e.g., 'Squat - T1', 'Bench Press - T2')")
        exercise_name = input("Enter the full name of the exercise to analyze: ")

        # --- 3. Filter the DataFrame for the chosen exercise ---
        exercise_df = df[df['Exercise Name'] == exercise_name].copy()

        if exercise_df.empty:
            print(f"\nNo data found for the exercise '{exercise_name}'. Please check the name and try again.")
            return

        print(f"\nFound {len(exercise_df)} sets for '{exercise_name}'. Calculating volume...")

        # --- 4. Clean and prepare the data ---
        # Convert columns to the correct data types for calculation.
        # errors='coerce' will turn any non-numeric values into NaN (Not a Number).
        exercise_df['Date'] = pd.to_datetime(exercise_df['Date'])
        exercise_df['Weight'] = pd.to_numeric(exercise_df['Weight'], errors='coerce')
        exercise_df['Reps'] = pd.to_numeric(exercise_df['Reps'], errors='coerce')
        
        # Drop rows where 'Weight' or 'Reps' could not be converted (are NaN)
        exercise_df.dropna(subset=['Weight', 'Reps'], inplace=True)
        
        # --- 5. Calculate volume for each set ---
        # Volume is the key metric for tracking workload.
        exercise_df['Volume'] = exercise_df['Weight'] * exercise_df['Reps']
        
        # --- 6. Aggregate volume by workout session ---
        # We group by the 'Date' of the workout. Since all sets in a single workout
        # have the same timestamp, this effectively groups them by session.
        # We then sum the 'Volume' for each session.
        daily_volume = exercise_df.groupby(exercise_df['Date'].dt.date)['Volume'].sum().reset_index()
        daily_volume.rename(columns={'Volume': 'TotalVolume'}, inplace=True)
        daily_volume['TotalVolume'] = daily_volume['TotalVolume'].astype(int)


        # --- 7. Display the results ---
        print(f"\n--- Total Volume Trend for {exercise_name} ---")
        print(daily_volume.to_string(index=False))
        print("\n" + "-" * 40)


    except FileNotFoundError:
        print(f"\nERROR: The file '{file_name}' was not found at '{file_path}'.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Main execution block ---
if __name__ == "__main__":
    analyze_exercise_volume()