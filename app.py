from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
import os, requests, random

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Database configuration
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Chutes LLM configuration
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY")
CHUTES_BASE_URL = "https://llm.chutes.ai/v1/chat/completions"
CHARACTER_MODEL = "deepseek-ai/DeepSeek-V3-0324"
DEMO_MODE = os.getenv("DEMO_MODE", "False") == "True"

# Database models
class Chat(db.Model):
    __tablename__ = 'chat'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, default="New Chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='chat', cascade="all, delete-orphan", lazy=True)

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'user' or 'ai'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/message", methods=["POST"])
def save_message():
    data = request.get_json()
    chat_id = data.get("chat_id")
    content = data.get("content")
    msg_type = data.get("type")

    if not content or not msg_type:
        return jsonify({"error": "Missing content or type"}), 400

    if not chat_id:
        chat = Chat(title="Japanese Learning Chat")
        db.session.add(chat)
        db.session.commit()
        chat_id = chat.id
    else:
        chat = db.session.get(Chat, chat_id)
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

    message = Message(chat_id=chat_id, content=content, type=msg_type)
    db.session.add(message)
    db.session.commit()
    # Update chat title if it's the first user message
    if msg_type == "user" and chat.title == "New Chat":
        title = content[:30] + ("..." if len(content) > 30 else "")
        chat.title = title
        db.session.commit()

    return jsonify({
        "chat_id": chat_id,
        "message_id": message.id,
        "timestamp": message.timestamp.isoformat()
    })

@app.route("/api/chats", methods=["GET", "POST"])
def chats():
    if request.method == "GET":
        chats = Chat.query.order_by(Chat.created_at.desc()).all()
        return jsonify([{"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in chats])
    
    elif request.method == "POST":
        data = request.get_json() or {}
        title = data.get("title", "Japanese Learning Chat")
        chat = Chat(title=title)
        db.session.add(chat)
        db.session.commit()
        return jsonify({"id": chat.id, "title": chat.title, "created_at": chat.created_at.isoformat()}), 201

@app.route("/api/chat/<int:chat_id>", methods=["GET"])
def get_chat(chat_id):
    chat = db.session.get(Chat, chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    messages = [
        {"id": m.id, "content": m.content, "type": m.type, "timestamp": m.timestamp.isoformat()}
        for m in chat.messages
    ]
    return jsonify({"id": chat.id, "title": chat.title, "messages": messages})

# Japanese Learning Chat
@app.route("/chat", methods=["POST"])
def japanese_chat():
    data = request.get_json()
    user_msg = data.get("message", "")
    chat_id = data.get("chat_id")

    if not chat_id:
        chat = Chat(title="Japanese Learning Chat")
        db.session.add(chat)
        db.session.commit()
        chat_id = chat.id
    else:
        chat = db.session.get(Chat, chat_id)
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

    # Save user message
    user_message = Message(chat_id=chat_id, content=user_msg, type="user")
    db.session.add(user_message)
    db.session.commit()

    if DEMO_MODE:
        reply = random.choice([
            "こんにちは！ (Hello!)", 
            "今日はどうですか？ (How are you today?)", 
            "頑張って！ (Keep going!)"
        ])
    else:
        system_prompt = (
            "You are a friendly Japanese language tutor. "
            "Answer in simple Japanese, provide English translations, "
            "and give explanations when appropriate."
        )
        payload = {
            "model": CHARACTER_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 500
        }
        headers = {"Authorization": f"Bearer {CHUTES_API_KEY}", "Content-Type": "application/json"}
        try:
            resp = requests.post(CHUTES_BASE_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                reply = resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                reply = "Too many requests. Please try again later."
            else:
                reply = f"Error: {resp.status_code}"
        except requests.exceptions.RequestException:
            reply = "Network error. Please try again."

    # Save AI reply
    ai_message = Message(chat_id=chat_id, content=reply, type="ai")
    db.session.add(ai_message)
    db.session.commit()

    return jsonify({"chat_id": chat_id, "reply": reply})

# Delete a chat and all its messages
@app.route("/api/chat/<int:chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    chat = db.session.get(Chat, chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    db.session.delete(chat)
    db.session.commit()
    return jsonify({"message": f"Chat {chat_id} deleted successfully."})


# Initialize DB and run server
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
