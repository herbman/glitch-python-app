# app.py
import os
import requests
import sqlite3
from flask import Flask, request, jsonify, g
import openai

app = Flask(__name__)

# Configure sua chave de API da OpenAI
openai.api_key = 'YOUR_OPENAI_API_KEY'

DATABASE = './db.sqlite3'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = data['messages'][0]['text']['body']
    phone_number = data['messages'][0]['from']
    assistant_id = data.get('assistant_id', 'default')

    # Salvar mensagem no banco de dados
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO messages (assistant_id, phone_number, message) VALUES (?, ?, ?)", (assistant_id, phone_number, message))
    db.commit()

    # Obter histórico de mensagens para o assistant_id
    cursor.execute("SELECT message FROM messages WHERE assistant_id = ? ORDER BY timestamp", (assistant_id,))
    rows = cursor.fetchall()
    conversation_history = "\n".join([row[0] for row in rows])

    # Enviar a mensagem para a API da OpenAI com o histórico de conversas
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=conversation_history + "\nUser: " + message + "\nBot:",
        max_tokens=150
    )
    reply = response.choices[0].text.strip()

    # Enviar a resposta de volta para o WhatsApp
    send_message(reply, phone_number)

    return jsonify({"status": "success"})

def send_message(message, phone_number):
    url = "https://graph.facebook.com/v13.0/YOUR_PHONE_NUMBER_ID/messages"
    headers = {
        "Authorization": "Bearer YOUR_WHATSAPP_API_TOKEN",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "text": {
            "body": message
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response

if __name__ == '__main__':
    init_db()
    app.run(port=3000, debug=True)
