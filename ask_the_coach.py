#
# Description:
# This is the final, corrected, and most advanced version of the AI Health Coach.
# It functions as a continuous, interactive chat session and implements the full
# Retrieval-Augmented Generation (RAG) system with advanced prompt engineering.
#
# VERSION 8 - FINAL INTERACTIVE BUILD:
# - Re-implements the 'while True' loop for continuous conversation.
# - Manages chat history within the session for growing context.
# - Includes the most advanced prompt engineering for nuanced analysis.
# - The user can type 'quit' to end the session gracefully.
#

import pandas as pd
import os
import psycopg2
import google.generativeai as genai
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json
import numpy as np

# --- Database & API Configuration ---
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"
EMBEDDING_MODEL = 'models/embedding-001'
GENERATION_MODEL = 'gemini-1.5-flash-latest'

# --- RAG & Context Functions ---

def get_db_engine():
    """Creates and returns a SQLAlchemy engine."""
    db_url = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(db_url)

def get_relevant_knowledge(engine, user_question, top_k=3):
    """Finds the most relevant knowledge chunks for a user's question."""
    try:
        question_embedding = genai.embed_content(model=EMBEDDING_MODEL, content=user_question)['embedding']
        knowledge_df = pd.read_sql_query("SELECT content_chunk, embedding FROM knowledge_embeddings", engine)
        
        if knowledge_df.empty: return ""
        
        knowledge_df['embedding_vector'] = knowledge_df['embedding'].apply(lambda x: np.array(json.loads(x)))
        question_vector = np.array(question_embedding)
        
        knowledge_df['similarity'] = knowledge_df['embedding_vector'].apply(
            lambda vec: np.dot(vec, question_vector) / (np.linalg.norm(vec) * np.linalg.norm(question_vector))
        )
        
        top_chunks = knowledge_df.nlargest(top_k, 'similarity')
        knowledge_context = "\n---\n".join(top_chunks['content_chunk'])
        return knowledge_context
        
    except Exception as e:
        print(f"Error retrieving knowledge: {e}")
        return ""

def get_initial_session_data(engine):
    """Retrieves health data just once at the start of the session."""
    try:
        print("Connecting to database to retrieve your health data...")
        daily_summary_query = "SELECT * FROM daily_summaries ORDER BY date DESC LIMIT 7;"
        daily_summary_df = pd.read_sql_query(daily_summary_query, engine)
        
        distinct_workout_dates_query = """
            SELECT DISTINCT w.start_date::date
            FROM workouts w
            WHERE w.workout_type = 'TraditionalStrengthTraining'
            ORDER BY w.start_date::date DESC
            LIMIT 3;
        """
        recent_dates_df = pd.read_sql_query(distinct_workout_dates_query, engine)
        recent_dates = [str(d) for d in recent_dates_df['start_date'].tolist()]

        workout_details_df = pd.DataFrame()
        if recent_dates:
            workout_details_query = f"""
                SELECT
                    w.start_date, wd.exercise_name, wd.set_order, wd.weight, wd.reps, wd.rpe
                FROM workout_details wd
                JOIN workouts w ON wd.workout_id = w.workout_id
                WHERE w.start_date::date IN ({",".join([f"'{d}'" for d in recent_dates])})
                ORDER BY w.start_date DESC, wd.exercise_name, wd.set_order;
            """
            workout_details_df = pd.read_sql_query(workout_details_query, engine)

        print("Data retrieved successfully.")
        return daily_summary_df, workout_details_df

    except Exception as e:
        print(f"Error during data retrieval: {e}")
        return pd.DataFrame(), pd.DataFrame()

def format_workout_details_for_prompt(df):
    """Formats the detailed workout DataFrame into a clean, readable string."""
    if df.empty:
        return "No recent strength workouts with details found."
    
    log_str = ""
    for date, group in df.groupby(df['start_date'].dt.date):
        log_str += f"\n**Workout on: {date.strftime('%Y-%m-%d')}**\n"
        group['volume'] = group['weight'] * group['reps']
        total_volume = group['volume'].sum()
        log_str += f"  (Total Daily Volume: {int(total_volume)} lbs)\n"
        for exercise, sets in group.groupby('exercise_name'):
            log_str += f"  - {exercise}:\n"
            for _, row in sets.iterrows():
                rpe_str = f"RPE: {row['rpe']}" if pd.notna(row['rpe']) else "RPE: Not Logged"
                log_str += f"    - Set {row['set_order']}: {row['weight']} lbs x {row['reps']} reps ({rpe_str})\n"
    return log_str

def save_chat_to_db(engine, user_prompt, model_response):
    """Saves the conversation to the database."""
    print("Saving conversation to database...")
    try:
        with engine.connect() as conn:
            with conn.begin():
                insert_query = text("INSERT INTO chat_history (role, content) VALUES (:role, :content)")
                conn.execute(insert_query, {"role": "user", "content": user_prompt})
                conn.execute(insert_query, {"role": "model", "content": model_response})
        print("Conversation saved successfully.")
    except Exception as e:
        print(f"Error saving chat history: {e}")

# --- Main Application Logic ---

def main():
    """Main function to run the interactive RAG-powered AI Health Coach."""
    
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: raise ValueError("GEMINI_API_KEY not found in .env file.")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GENERATION_MODEL)
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
        return

    engine = get_db_engine()
    daily_summary, workout_details = get_initial_session_data(engine)
    
    daily_summary_str = daily_summary.to_string(index=False)
    workout_details_str = format_workout_details_for_prompt(workout_details)
    
    chat_history = []
    print("\n--- AI Health Coach Session Started ---")
    print("Type 'quit' to end the session.")
    
    while True:
        user_question = input("\nAsk your health coach a question: ")
        if user_question.lower() == 'quit':
            print("Ending session. Goodbye!")
            break

        print("\nAssembling context for the AI...")
        knowledge_context = get_relevant_knowledge(engine, user_question)
        
        conversation_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

        prompt = f"""
        **Role:** You are an expert health and fitness coach. Your primary goal is to provide safe, effective, and evidence-based advice for overall health and performance.

        **Your Task:** Your user will ask a question. Based on their question, the provided knowledge base context, and their detailed workout logs, provide a direct, helpful, and nuanced answer.

        **Critical Analysis Instructions:**
        1. Analyze Volume Intelligently: Recognize that 'Total Daily Volume' will naturally fluctuate based on the muscle groups trained (e.g., leg days have higher volume than upper body days). Focus your analysis on the volume trends for specific, comparable exercises over time, rather than just comparing the total volume of two different workout types.
        2. Frame Data Gaps as Coaching Opportunities: If RPE is not logged for a set, do not criticize. Instead, frame it as a helpful suggestion for the future. For example: "For this set of squats, the RPE wasn't logged. Recording it next time will help us better track if your strength gains are matching your effort level."
        3. Synthesize Volume and RPE (No Change): This is your most important task. Connect the change in volume to the perceived effort. For example: "I see you increased the weight on your Squats by 10 lbs, and your RPE only increased from 7 to 7.5. This is a great sign of strength gain." most important task. Connect the change in volume to the perceived effort. For example: "I see you increased the weight on your Squats by 10 lbs. Your RPE only increased from 7 to 7.5. This is a great sign of strength gain." OR "Your volume on Deadlifts went up significantly, and your RPE jumped to 9. This indicates a very high-intensity session; ensure you are prioritizing recovery."

        ---
        **Knowledge Base Context (Most relevant for my question):**
        {knowledge_context}
        ---
        **Previous Conversation History (this session):**
        {conversation_str}
        ---
        **My Recent Health Data:**
        (This data is for general context and may not be the most up-to-date if the conversation is long)
        Daily Summaries (last 7 days):
        {daily_summary_str}

        Strength Workout Details (recent sessions):
        {workout_details_str}
        ---
        **My Question:** {user_question}
        ---
        """

        print("--- Sending Data to AI Coach for Analysis ---")
        try:
            response = model.generate_content(prompt)
            model_response_text = response.text
            
            print("\n--- AI Coach Response ---")
            print(model_response_text)
            print("\n" + "-" * 40)
            
            chat_history.append({"role": "user", "content": user_question})
            chat_history.append({"role": "model", "content": model_response_text})
            save_chat_to_db(engine, user_question, model_response_text)

        except Exception as e:
            print(f"An error occurred while calling the Gemini API: {e}")
        
    engine.dispose()

if __name__ == "__main__":
    main()