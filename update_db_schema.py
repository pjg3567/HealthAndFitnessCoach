#
# Description:
# This is a utility script to update our database schema. It adds a new
# 'rpe' column to the 'workout_details' table to store the
# Rate of Perceived Exertion for each set.
#
# This script should only need to be run once.
#

import psycopg2
import os

# --- Database Connection Details ---
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"

def add_rpe_column():
    """Connects to the database and adds an 'rpe' column."""
    conn = None
    try:
        print(f"Connecting to database '{DB_NAME}' to update schema...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        print("Connection successful.")

        # --- Define the SQL ALTER TABLE Command ---
        # This command adds a new column named 'rpe' of type REAL (a number).
        # We use "IF NOT EXISTS" to prevent an error if we accidentally run
        # the script more than once.
        alter_table_command = """
        ALTER TABLE workout_details
        ADD COLUMN IF NOT EXISTS rpe REAL;
        """

        # --- Execute the Command ---
        print("Adding 'rpe' column to 'workout_details' table...")
        cur.execute(alter_table_command)
        
        conn.commit()
        cur.close()
        print("Table 'workout_details' updated successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


# --- Main execution block ---
if __name__ == "__main__":
    add_rpe_column()