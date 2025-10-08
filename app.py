from flask import Flask, render_template, request, jsonify
import mysql.connector
from dotenv import load_dotenv
import os, time

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Connect to AWS RDS (MySQL)
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# Initialize DB (run once)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_message TEXT,
        bot_reply TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Database initialized")

init_db()

# Simple rule-based bot
def chatbot_reply(message):
    msg = message.lower()
    if "hello" in msg:
        return "Hi there! How can I assist you?"
    elif "cloud" in msg:
        return "Cloud computing allows flexible, on-demand access to resources!"
    elif "database" in msg:
        return "Databases store and manage your data efficiently."
    elif "bye" in msg:
        return "Goodbye! See you soon."
    else:
        return "I'm your Cloud Chatbot — ask me about cloud computing!"

@app.route("/")
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_message, bot_reply, timestamp FROM chat_history ORDER BY id DESC LIMIT 10")
    chats = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("index.html", chats=chats)

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.form["message"]
    bot_reply = chatbot_reply(user_msg)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_message, bot_reply) VALUES (%s, %s)", (user_msg, bot_reply))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"reply": bot_reply})

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
