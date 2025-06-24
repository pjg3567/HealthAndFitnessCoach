#
# Description:
# This script connects to our PostgreSQL database ('health_coach_db') and
# creates the necessary tables to store our unified health data, workouts,
# and AI chat history.
#
# This script should only need to be run once to set up the database schema
# according to our project plan.
#

import psycopg2
import os

# --- Database Connection Details ---
# These should match the default settings for a local PostgreSQL installation.
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ") # Uses your Mac username "PJ" by default
DB_HOST = "localhost"
DB_PORT = "5432"

def create_tables():
    """Connects to the database and creates all necessary tables."""
    conn = None
    try:
        # --- 1. Establish Connection to the Database ---
        print(f"Connecting to database '{DB_NAME}'...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        print("Connection successful.")

        # --- 2. Define SQL Commands to Create Tables ---
        # Using '''triple quotes''' for multi-line strings makes the SQL readable.
        # SERIAL PRIMARY KEY creates an auto-incrementing unique ID for each row.
        # DATE UNIQUE ensures we only have one summary per day.
        # REAL is used for numbers that can have decimal points.
        # TEXT is for storing strings of any length.
        # JSONB is a special type for efficiently storing JSON data.
        # TIMESTAMPTZ stores a timestamp with timezone information.

        create_table_commands = (
            """
            CREATE TABLE IF NOT EXISTS daily_summaries (
                date DATE PRIMARY KEY,
                total_steps INTEGER,
                active_energy_kcal REAL,
                calories_kcal REAL,
                protein_g REAL,
                fat_g REAL,
                carbs_g REAL,
                strength_volume REAL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS workouts (
                workout_id SERIAL PRIMARY KEY,
                start_date TIMESTAMPTZ,
                end_date TIMESTAMPTZ,
                workout_type VARCHAR(255),
                duration_mins REAL,
                total_distance REAL,
                total_energy_burned REAL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS workout_details (
                detail_id SERIAL PRIMARY KEY,
                workout_id INTEGER REFERENCES workouts(workout_id),
                exercise_name VARCHAR(255),
                set_order INTEGER,
                weight REAL,
                reps INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                message_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                role VARCHAR(50),
                content TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS llm_insights (
                insight_id SERIAL PRIMARY KEY,
                message_id INTEGER REFERENCES chat_history(message_id),
                insight_date DATE DEFAULT CURRENT_DATE,
                structured_analysis JSONB
            )
            """
        )

        # --- 3. Execute Each Create Table Command ---
        print("\nCreating tables...")
        for command in create_table_commands:
            cur.execute(command)
        
        # --- 4. Commit Changes and Close Connection ---
        conn.commit()
        cur.close()
        print("All tables created successfully or already exist.")

    except psycopg2.OperationalError as e:
        print(f"\nCould not connect to the database. Is it running?")
        print(f"HINT: You might need to run 'brew services start postgresql@14' in your terminal.")
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


# --- Main execution block ---
if __name__ == "__main__":
    create_tables()