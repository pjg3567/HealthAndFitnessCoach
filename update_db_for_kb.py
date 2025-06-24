#
# Description:
# This is a utility script to update our database schema. It adds a new
# 'knowledge_embeddings' table. This table will store chunks of text
# from the research documents and their corresponding numerical embeddings,
# creating a searchable knowledge base for the AI.
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

def create_knowledge_base_table():
    """Connects to the database and creates the knowledge_embeddings table."""
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
        # This command creates the table to store our knowledge.
        # - embedding_id: A unique ID for each text chunk.
        # - source_document: The name of the file the text came from.
        # - content_chunk: The actual piece of text (e.g., a paragraph).
        # - embedding: The numerical representation of the text, stored as TEXT.
        create_table_command = """
        CREATE TABLE IF NOT EXISTS knowledge_embeddings (
            embedding_id SERIAL PRIMARY KEY,
            source_document VARCHAR(255),
            content_chunk TEXT,
            embedding TEXT
        );
        """

        # --- Execute the Command ---
        print("Creating 'knowledge_embeddings' table...")
        cur.execute(create_table_command)
        
        conn.commit()
        cur.close()
        print("Table 'knowledge_embeddings' created successfully or already exists.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


# --- Main execution block ---
if __name__ == "__main__":
    create_knowledge_base_table()