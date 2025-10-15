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

    # If no chat exists, create a new one
    if not chat_id:
        chat = Chat(title="New Chat")
        db.session.add(chat)
        db.session.commit()
        chat_id = chat.id
    else:
        chat = db.session.get(Chat, chat_id)
        if not chat:
            return jsonify({"error": "Chat not found"}), 404

    # Save the message
    message = Message(chat_id=chat_id, content=content, type=msg_type)
    db.session.add(message)
    db.session.commit()

    # Generate a smart title if it's the first user message
    if msg_type == "user" and chat.title == "New Chat":
        if DEMO_MODE:
            # Simple fallback title
            chat.title = random.choice([
                "Basic Greetings", 
                "First Japanese Chat", 
                "Learning New Words", 
                "Daily Conversation"
            ])
        else:
            try:
                title_prompt = (
                    "You are a helpful assistant that generates short, meaningful titles "
                    "for chat sessions. Create a short English title (max 6 words) for a "
                    f"Japanese learning conversation based on this user message:\n\n"
                    f"\"{content}\"\n\n"
                    "Return only the title, no punctuation or quotes."
                )
                payload = {
                    "model": CHARACTER_MODEL,
                    "messages": [
                        {"role": "system", "content": title_prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 20
                }
                headers = {
                    "Authorization": f"Bearer {CHUTES_API_KEY}",
                    "Content-Type": "application/json"
                }
                resp = requests.post(CHUTES_BASE_URL, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    new_title = resp.json()["choices"][0]["message"]["content"].strip()
                    chat.title = new_title if new_title else content[:30]
                else:
                    chat.title = content[:30]  # fallback
            except requests.exceptions.RequestException:
                chat.title = content[:30]

        db.session.commit()

    return jsonify({
        "chat_id": chat_id,
        "message_id": message.id,
        "timestamp": message.timestamp.isoformat(),
        "chat_title": chat.title
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
            "You are a warm, patient **Japanese conversation tutor** for complete beginners (JLPT N5 level).\n\n"
            "📋 **Core Rules (MUST follow every time):**\n"
            "1. **ONLY use hiragana and katakana** - NEVER use kanji\n"
            "2. Use simple, natural **です・ます form** (polite Japanese)\n"
            "3. Limit vocabulary to **JLPT N5 basic words** (~800 most common words)\n"
            "4. Keep responses **2-4 sentences maximum** in Japanese\n\n"
            
            "✅ **Response Structure (use this format):**\n"
            "```\n"
            "[Japanese text in hiragana/katakana]\n"
            "English: [Natural English translation]\n"
            "💡 [ONE key learning point - word meaning OR grammar pattern]\n"
            "```\n\n"
            
            "🎯 **Your Teaching Style:**\n"
            "- Speak like a friendly language partner, not a formal teacher\n"
            "- When learner makes mistakes: gently show the correct version + brief reason\n"
            "- Give lots of encouragement: すごい！、いいですね！、よくできました！\n"
            "- Ask simple follow-up questions to keep conversation flowing\n"
            "- Focus on ONE new word or grammar point per message\n\n"
            
            "🚫 **What NOT to do:**\n"
            "- Don't write long explanations (keep it under 30 words)\n"
            "- Don't introduce multiple new concepts at once\n"
            "- Don't use complex grammar or advanced vocabulary\n"
            "- Don't overwhelm with too much information\n\n"
            
            "💬 **Example Response:**\n"
            "こんにちは！きょうは げんきですか？\n"
            "English: Hello! Are you well today?\n"
            "💡 「げんき」means healthy/energetic - a common way to ask how someone is feeling.\n\n"
            
            "Remember: You're helping someone take their very first steps in Japanese. Keep it simple, natural, and encouraging! 🌸"
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
