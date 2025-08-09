
#!/usr/bin/env python3
import os
import requests
import json
import logging
from flask import Flask, request, jsonify
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  
GITHUB_REPO = os.environ.get('GITHUB_REPO')
AUTHORIZED_CHAT_IDS = [int(x) for x in os.environ.get('TELEGRAM_CHAT_IDS', '').split(',') if x.strip()]

def trigger_github_action():
    if not all([GITHUB_TOKEN, GITHUB_REPO]):
        logger.error("GITHUB_TOKEN o GITHUB_REPO no configurados")
        return False
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'TelegramBot-WebhookServer'
    }
    
    data = {
        'event_type': 'telegram_trigger',
        'client_payload': {
            'timestamp': datetime.now().isoformat(),
            'trigger': 'telegram_webhook'
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 204:
            logger.info("GitHub Action disparado exitosamente")
            return True
        else:
            logger.error(f"Error disparando GitHub Action: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

def send_telegram_message(chat_id, message):
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    
    try:
        response = requests.post(url, json=data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return False

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'healthy',
        'service': 'Telegram Webhook Server',
        'telegram_configured': TELEGRAM_BOT_TOKEN is not None,
        'github_configured': GITHUB_TOKEN is not None,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return 'OK', 200
        
        message = data['message']
        chat_id = message['chat']['id']
        user_name = message.get('from', {}).get('first_name', 'Usuario')
        text = message.get('text', '').strip().lower()
        
        if chat_id not in AUTHORIZED_CHAT_IDS:
            send_telegram_message(chat_id, "❌ No autorizado")
            return 'Unauthorized', 403
        
        if text in ['start', 'run', 'ejecutar', '/start']:
            send_telegram_message(chat_id, f"🚀 <b>Iniciando automatización...</b>\n👤 {user_name}")
            success = trigger_github_action()
            
            if success:
                send_telegram_message(chat_id, "✅ Comando enviado a GitHub Actions")
            else:
                send_telegram_message(chat_id, "❌ Error iniciando automatización")
        
        elif text in ['status', '/status']:
            send_telegram_message(chat_id, f"📊 <b>Bot activo</b>\n✅ Webhook funcionando\n👤 {user_name}")
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return 'Error', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)