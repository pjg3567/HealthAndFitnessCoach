#
# Description:
# This script builds the AI coach's searchable knowledge base. It reads all
# .pdf and .docx files from the 'knowledge_base' directory, splits their
# content into smaller chunks, generates a numerical embedding for each chunk
# using the Gemini API, and stores the chunk and its embedding in the
# 'knowledge_embeddings' table in our PostgreSQL database.
#
# This is a one-time setup script to process your research documents.
#

import os
import pypdf
import docx
import google.generativeai as genai
import psycopg2
from dotenv import load_dotenv
import json

# --- Configuration and Setup ---
KNOWLEDGE_BASE_DIR = "knowledge_base"
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"

# --- Document Reading Functions ---
def read_pdf(file_path):
    """Reads and extracts text from a PDF file."""
    print(f"  Reading PDF: {os.path.basename(file_path)}")
    with open(file_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def read_docx(file_path):
    """Reads and extracts text from a DOCX file."""
    print(f"  Reading DOCX: {os.path.basename(file_path)}")
    doc = docx.Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def chunk_text(text, chunk_size=500, overlap=100):
    """Splits text into smaller, overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

# --- Main Embedding and Loading Function ---
def build_and_load_knowledge_base():
    """Processes all documents and loads their embeddings into the database."""
    # 1. Configure Gemini API
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file.")
        genai.configure(api_key=api_key)
        # Use the specific model for generating embeddings
        embedding_model = 'models/embedding-001'
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
        return

    # 2. Connect to the database
    conn = None
    try:
        print(f"Connecting to database '{DB_NAME}'...")
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
        cur = conn.cursor()
        print("Connection successful.")

        # 3. Process each document in the knowledge base directory
        print(f"\nProcessing documents in '{KNOWLEDGE_BASE_DIR}' folder...")
        for filename in os.listdir(KNOWLEDGE_BASE_DIR):
            file_path = os.path.join(KNOWLEDGE_BASE_DIR, filename)
            text = ""
            if filename.lower().endswith(".pdf"):
                text = read_pdf(file_path)
            elif filename.lower().endswith(".docx"):
                text = read_docx(file_path)
            
            if text:
                chunks = chunk_text(text)
                print(f"    -> Split '{filename}' into {len(chunks)} chunks.")
                
                for chunk in chunks:
                    # Check if this exact chunk already exists to avoid duplicates
                    cur.execute("SELECT 1 FROM knowledge_embeddings WHERE content_chunk = %s", (chunk,))
                    if cur.fetchone() is None:
                        # 4. Generate embedding for the chunk
                        embedding = genai.embed_content(model=embedding_model, content=chunk)
                        
                        # 5. Insert the data into the database
                        # We store the embedding as a JSON string
                        insert_query = """
                            INSERT INTO knowledge_embeddings (source_document, content_chunk, embedding)
                            VALUES (%s, %s, %s);
                        """
                        cur.execute(insert_query, (filename, chunk, json.dumps(embedding['embedding'])))
        
        conn.commit()
        cur.close()
        print("\nKnowledge base embedding process complete.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


# --- Main execution block ---
if __name__ == "__main__":
    build_and_load_knowledge_base()