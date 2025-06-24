#
# Description:
# This is a utility script to update our database schema. It adds a new
# 'pipeline_runs' table. This table will store a timestamp after each
# successful run of our main data pipeline, creating a more efficient
# state-tracking mechanism.
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

def create_pipeline_runs_table():
    """Connects to the database and creates the pipeline_runs table."""
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

        # --- Define the SQL CREATE TABLE Command ---
        # This table will store a log of when the pipeline was last run.
        create_table_command = """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id SERIAL PRIMARY KEY,
            run_timestamp TIMESTAMPTZ NOT NULL
        );
        """

        # --- Execute the Command ---
        print("Creating 'pipeline_runs' table...")
        cur.execute(create_table_command)
        
        conn.commit()
        cur.close()
        print("Table 'pipeline_runs' created successfully or already exists.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


# --- Main execution block ---
if __name__ == "__main__":
    create_pipeline_runs_table()
