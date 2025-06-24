#
# Description:
# This is the main application file for our AI Health Coach web interface.
# It now includes all the backend logic to connect to the database, assemble
# the "Smart Context" prompt, and call the Gemini API.
#
# It defines a new '/ask' route that will handle incoming questions from the
# user interface and return the AI's analysis.
#

from flask import Flask, render_template, request, jsonify
import pandas as pd
import os
import psycopg2
import google.generativeai as genai
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json
import numpy as np

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Database & API Configuration ---
DB_NAME = "health_coach_db"
DB_USER = os.getenv("DB_USER", "PJ")
DB_HOST = "localhost"
DB_PORT = "5432"
EMBEDDING_MODEL = 'models/embedding-001'
GENERATION_MODEL = 'gemini-1.5-flash-latest'

# --- RAG & Context Functions (Copied from ask_the_coach.py) ---

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
        knowledge_df['similarity'] = knowledge_df['embedding_vector'].apply(lambda vec: np.dot(vec, question_vector) / (np.linalg.norm(vec) * np.linalg.norm(question_vector)))
        top_chunks = knowledge_df.nlargest(top_k, 'similarity')
        return "\n---\n".join(top_chunks['content_chunk'])
    except Exception as e:
        print(f"Error retrieving knowledge: {e}")
        return ""

def get_session_data(engine):
    """Retrieves health data and chat history for the current session."""
    try:
        daily_summary_query = "SELECT * FROM daily_summaries ORDER BY date DESC LIMIT 7;"
        daily_summary_df = pd.read_sql_query(daily_summary_query, engine)
        
        distinct_workout_dates_query = "SELECT DISTINCT w.start_date::date FROM workouts w WHERE w.workout_type = 'TraditionalStrengthTraining' ORDER BY w.start_date::date DESC LIMIT 3;"
        recent_dates_df = pd.read_sql_query(distinct_workout_dates_query, engine)
        recent_dates = [str(d) for d in recent_dates_df['start_date'].tolist()]

        workout_details_df = pd.DataFrame()
        if recent_dates:
            dates_in_clause = ",".join([f"'{d}'" for d in recent_dates])
            workout_details_query = f"SELECT w.start_date, wd.exercise_name, wd.set_order, wd.weight, wd.reps, wd.rpe FROM workout_details wd JOIN workouts w ON wd.workout_id = w.workout_id WHERE w.start_date::date IN ({dates_in_clause}) ORDER BY w.start_date DESC, wd.exercise_name, wd.set_order;"
            workout_details_df = pd.read_sql_query(workout_details_query, engine)

        chat_history_query = "SELECT role, content FROM chat_history ORDER BY timestamp DESC LIMIT 4;"
        chat_history_df = pd.read_sql_query(chat_history_query, engine).iloc[::-1]

        return daily_summary_df, workout_details_df, chat_history_df
    except Exception as e:
        print(f"Error during data retrieval: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def format_workout_details_for_prompt(df):
    """Formats the detailed workout DataFrame into a clean, readable string."""
    if df.empty: return "No recent strength workouts with details found."
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
    try:
        with engine.connect() as conn:
            with conn.begin():
                insert_query = text("INSERT INTO chat_history (role, content) VALUES (:role, :content)")
                conn.execute(insert_query, {"role": "user", "content": user_prompt})
                conn.execute(insert_query, {"role": "model", "content": model_response})
    except Exception as e:
        print(f"Error saving chat history: {e}")


# --- Flask Routes ---

@app.route('/')
def home():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    """
    Handles POST requests with a user's question.
    Connects to the AI, gets an analysis, and returns it as JSON.
    """
    # 1. Get the user's question from the incoming request data
    user_question = request.json.get('question')
    if not user_question:
        return jsonify({"error": "No question provided"}), 400

    try:
        # 2. Configure Gemini (needs to be done for each request in a simple setup)
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key: raise ValueError("GEMINI_API_KEY not found.")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GENERATION_MODEL)

        # 3. Assemble the full context for the AI
        engine = get_db_engine()
        knowledge_context = get_relevant_knowledge(engine, user_question)
        daily_summary, workout_details, chat_history = get_session_data(engine)
        
        daily_summary_str = daily_summary.to_string(index=False)
        workout_details_str = format_workout_details_for_prompt(workout_details)
        conversation_str = "\n".join([f"{row['role']}: {row['content']}" for _, row in chat_history.iterrows()])

        prompt = f"""
        **Role:** You are an expert health and fitness coach. Your primary goal is to provide safe, effective, and evidence-based advice for overall health and performance.

        **Your Task:** Your user will ask a question. Based on their question, the provided knowledge base context, and their detailed workout logs, provide a direct, helpful, and nuanced answer.

        **Critical Analysis Instructions:**
        1. Acknowledge Data Gaps Briefly: If RPE is not logged for a set, state it once and then focus your analysis on the data that IS available.
        2. Analyze Workouts Comparatively: Compare the most recent workout to the previous ones. Look for changes in volume, reps, or weight on a per-exercise basis.
        3. Synthesize Volume and RPE: Connect the change in volume to the perceived effort to assess progress and intensity.

        ---
        **Knowledge Base Context:**
        {knowledge_context}
        ---
        **Previous Conversation:**
        {conversation_str}
        ---
        **My Recent Health Data:**
        Daily Summaries:
        {daily_summary_str}
        Strength Workout Details:
        {workout_details_str}
        ---
        **My Question:** {user_question}
        ---
        """

        # 4. Get the response from Gemini
        response = model.generate_content(prompt)
        model_response_text = response.text
        
        # 5. Save the full conversation to the database
        save_chat_to_db(engine, user_question, model_response_text)
        
        # 6. Return the response to the frontend
        return jsonify({"answer": model_response_text})

    except Exception as e:
        print(f"An error occurred in /ask route: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/strength_volume_data')
def strength_volume_data():
    """
    This endpoint queries the database and returns all historical strength
    training volume data, formatted for use with a charting library.
    """
    try:
        engine = get_db_engine()
        # Query to get all days where strength training occurred, sorted by date
        query = text("""
            SELECT date, strength_volume 
            FROM daily_summaries 
            WHERE strength_volume > 0 
            ORDER BY date ASC;
        """)
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
            df['date'] = pd.to_datetime(df['date'])
        
        # Format the data into a structure that Chart.js understands
        chart_data = {
            'labels': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'data': df['strength_volume'].tolist()
        }
        # Return the data as a JSON response
        return jsonify(chart_data)
        
    except Exception as e:
        print(f"Error in /api/strength_volume_data route: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
