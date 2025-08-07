import json
import os
import time
import logging
import requests
import unicodedata
from datetime import datetime
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_uploader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class VideoUploader:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.data_json = self.script_dir / "data.json"
        self.uploadable_dir = self.script_dir / "uploadable"
        
        # Configuración Telegram
        self.bot_token = "7869024150:AAGFO6ZvpO4-5J4karX_lef252tkD3BhclE"
        self.chat_id = "6166225652"
        
        # Configuración YouTube API
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        self.CLIENT_SECRETS_FILE = "client_secrets.json"
        self.TOKEN_FILE = "youtube_token.json"
        
        self.pending_uploads = {}
        self.processed_update_ids = set()
        
        if not self.uploadable_dir.exists():
            raise FileNotFoundError(f"La carpeta uploadable no existe: {self.uploadable_dir}")
    
    def send_telegram_message(self, message):
        """Envía mensaje por Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"[TELEGRAM] Error: {e}")
            return False
    
    def send_video_preview(self, video_file, thumbnail_file, video_data):
        """Envía preview del video por Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            with open(thumbnail_file, 'rb') as photo:
                files = {'photo': photo}
                data = {
                    'chat_id': self.chat_id,
                    'caption': f"🎬 <b>Autorización requerida</b>\n\n"
                              f"📝 <b>Título:</b> {video_data.get('title', 'Sin título')[:100]}...\n"
                              f"🆔 <b>Video ID:</b> <code>{video_data.get('video_id', 'N/A')}</code>\n"
                              f"📁 <b>Video:</b> {video_file.name}\n"
                              f"🖼️ <b>Thumbnail:</b> {thumbnail_file.name}\n\n"
                              f"Responde: <code>yes {video_data.get('video_id', 'N/A')}</code>",
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, files=files, data=data, timeout=30)
                return response.status_code == 200
        except Exception as e:
            logging.error(f"[TELEGRAM] Error en preview: {e}")
            return False
    
    def check_telegram_updates(self):
        """Verifica autorizaciones en Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['ok'] and data['result']:
                    for update in data['result']:
                        update_id = update.get('update_id')
                        if update_id in self.processed_update_ids:
                            continue
                        
                        self.processed_update_ids.add(update_id)
                        message_text = update.get('message', {}).get('text', '').strip()
                        
                        if message_text.lower().startswith('yes '):
                            video_id = message_text[4:].strip()
                            # Buscar coincidencia case-insensitive
                            for pending_id in self.pending_uploads.keys():
                                if pending_id.lower() == video_id.lower():
                                    return pending_id
            return None
        except Exception as e:
            logging.error(f"[TELEGRAM] Error: {e}")
            return None
    
    def get_youtube_service(self):
        """Obtiene servicio de YouTube API"""
        credentials = None
        
        if os.path.exists(self.TOKEN_FILE):
            try:
                credentials = Credentials.from_authorized_user_file(self.TOKEN_FILE, self.SCOPES)
            except Exception as e:
                logging.warning(f"[YOUTUBE] Error cargando token: {e}")
        
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                except Exception as e:
                    logging.error(f"[YOUTUBE] Error renovando: {e}")
                    credentials = None
            
            if not credentials:
                if not os.path.exists(self.CLIENT_SECRETS_FILE):
                    logging.error(f"[YOUTUBE] client_secrets.json no encontrado")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(self.CLIENT_SECRETS_FILE, self.SCOPES)
                credentials = flow.run_local_server(port=0)
            
            with open(self.TOKEN_FILE, 'w') as token:
                token.write(credentials.to_json())
        
        return build('youtube', 'v3', credentials=credentials)
    
    def load_data_json(self):
        """Carga data.json"""
        if not self.data_json.exists():
            logging.error(f"[ERROR] data.json no encontrado")
            return []
        
        try:
            with open(self.data_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[ERROR] Error leyendo data.json: {e}")
            return []
    
    def save_data_json(self, videos):
        """Guarda data.json"""
        try:
            with open(self.data_json, 'w', encoding='utf-8') as f:
                json.dump(videos, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"[ERROR] Error guardando data.json: {e}")
            return False
    
    def normalize_filename(self, filename):
        """Normaliza nombre de archivo para comparación exacta"""
        if not filename:
            return ""
        
        # Quitar extensión
        name = Path(filename).stem
        
        # Normalizar Unicode (quitar tildes)
        name = unicodedata.normalize('NFD', name)
        name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
        
        # Limpiar caracteres especiales pero mantener estructura
        name = name.replace('¿', '').replace('?', '').replace('¡', '').replace('!', '')
        name = name.replace(':', ' ').replace(';', ' ').replace(',', ' ')
        
        # Normalizar espacios
        name = ' '.join(name.split())
        
        return name.lower().strip()
    
    def find_exact_match_files(self, title):
        """Busca archivos que coincidan por las primeras 3 palabras"""
        logging.info(f"[SEARCH] Buscando archivos para: '{title}'")
        
        all_files = list(self.uploadable_dir.glob("*"))
        title_normalized = self.normalize_filename(title)
        title_words = title_normalized.split()[:3]  # Solo primeras 3 palabras
        
        logging.info(f"[SEARCH] Palabras clave: {title_words}")
        
        # Buscar archivos que coincidan en las primeras 3 palabras
        json_file = None
        video_file = None
        thumbnail_file = None
        
        for file_path in all_files:
            file_normalized = self.normalize_filename(file_path.name)
            file_words = file_normalized.split()[:3]
            
            # Verificar si las primeras 3 palabras coinciden
            if len(title_words) >= 3 and len(file_words) >= 3:
                matches = sum(1 for tw, fw in zip(title_words, file_words) if tw == fw)
                if matches >= 3:  # Las 3 primeras palabras deben coincidir
                    ext = file_path.suffix.lower()
                    if ext == '.json' and not json_file:
                        json_file = file_path
                    elif ext == '.mp4' and not video_file:
                        video_file = file_path
                    elif ext in ['.jpg', '.jpeg', '.png'] and not thumbnail_file:
                        thumbnail_file = file_path
        
        # Si no encontró con 3 palabras, intentar con coincidencia parcial
        if not json_file and not video_file:
            for file_path in all_files:
                file_normalized = self.normalize_filename(file_path.name)
                
                # Verificar si contiene las palabras principales
                title_main = ' '.join(title_words)
                if title_main in file_normalized or any(word in file_normalized for word in title_words if len(word) > 3):
                    ext = file_path.suffix.lower()
                    if ext == '.json' and not json_file:
                        json_file = file_path
                    elif ext == '.mp4' and not video_file:
                        video_file = file_path
                    elif ext in ['.jpg', '.jpeg', '.png'] and not thumbnail_file:
                        thumbnail_file = file_path
        
        # Registrar archivos encontrados
        if json_file:
            logging.info(f"[FILES] JSON: {json_file.name}")
        if video_file:
            logging.info(f"[FILES] Video: {video_file.name}")
        if thumbnail_file:
            logging.info(f"[FILES] Thumbnail: {thumbnail_file.name}")
        
        # Cargar metadata del JSON
        json_data = None
        if json_file:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
            except Exception as e:
                logging.error(f"[ERROR] Error leyendo JSON: {e}")
                return None, None, None, None
        
        return json_file, video_file, thumbnail_file, json_data
    
    def upload_video_to_youtube(self, video_file, thumbnail_file, metadata):
        """Sube video a YouTube"""
        try:
            youtube = self.get_youtube_service()
            if not youtube:
                return False
            
            body = {
                'snippet': {
                    'title': metadata.get('title', 'Sin título'),
                    'description': metadata.get('description', ''),
                    'tags': metadata.get('tags', []),
                    'categoryId': '24'
                },
                'status': {'privacyStatus': 'public'}
            }
            
            media = MediaFileUpload(str(video_file), chunksize=-1, resumable=True, mimetype='video/mp4')
            request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
            
            response = None
            retry = 0
            
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        logging.info(f"[YOUTUBE] Progreso: {int(status.progress() * 100)}%")
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504] and retry < 3:
                        retry += 1
                        time.sleep(2 ** retry)
                    else:
                        raise
            
            if response:
                video_id = response['id']
                logging.info(f"[YOUTUBE] Video subido: {video_id}")
                
                # Subir thumbnail
                if thumbnail_file and thumbnail_file.exists():
                    try:
                        youtube.thumbnails().set(
                            videoId=video_id,
                            media_body=MediaFileUpload(str(thumbnail_file))
                        ).execute()
                        logging.info("[YOUTUBE] Thumbnail subido")
                    except Exception as e:
                        logging.warning(f"[YOUTUBE] Error en thumbnail: {e}")
                
                return video_id
            
            return False
        except Exception as e:
            logging.error(f"[YOUTUBE] Error: {e}")
            return False
    
    def update_video_status(self, video_id, status, youtube_id=None):
        """Actualiza estado en data.json"""
        videos = self.load_data_json()
        for video in videos:
            if video.get('video_id') == video_id:
                video['status'] = status
                video['uploaded_at'] = datetime.now().isoformat()
                if youtube_id:
                    video['youtube_id'] = youtube_id
                return self.save_data_json(videos)
        return False
    
    def process_ready_videos(self):
        """Procesa videos listos"""
        videos = self.load_data_json()
        ready_videos = [v for v in videos if v.get('status') == 'ok']
        
        if not ready_videos:
            self.send_telegram_message("ℹ️ No hay videos listos para subir")
            return
        
        logging.info(f"[PROCESS] {len(ready_videos)} videos listos")
        self.processed_update_ids.clear()
        
        for video_data in ready_videos:
            title = video_data.get('title', 'Sin título')
            video_id = video_data.get('video_id', '')
            
            # Buscar archivos con coincidencia por primeras 3 palabras
            json_file, video_file, thumbnail_file, metadata = self.find_exact_match_files(title)
            
            # Solo requiere JSON con metadata y MP4 (thumbnail es opcional)
            if not json_file or not video_file or not metadata:
                missing = []
                if not json_file: missing.append("JSON")
                if not video_file: missing.append("MP4")
                if not metadata: missing.append("metadata")
                
                logging.error(f"[ERROR] Faltan archivos para '{title}': {', '.join(missing)}")
                self.update_video_status(video_id, f'error - faltan: {", ".join(missing)}')
                continue
            
            # Si no hay thumbnail, usar imagen por defecto o continuar sin ella
            if not thumbnail_file:
                logging.warning(f"[WARNING] No se encontró thumbnail para: {title}, continuando sin thumbnail")
            
            
            # Enviar preview
            if not self.send_video_preview(video_file, thumbnail_file, video_data):
                self.update_video_status(video_id, 'error - preview fallido')
                continue
            
            # Guardar para autorización
            self.pending_uploads[video_id] = {
                'video_data': video_data,
                'json_file': json_file,
                'video_file': video_file,
                'thumbnail_file': thumbnail_file,
                'metadata': metadata
            }
        
        if self.pending_uploads:
            self.wait_for_authorizations()
    
    def wait_for_authorizations(self):
        """Espera autorizaciones"""
        max_wait = min(300 * len(self.pending_uploads), 1800)  # Max 30 min
        start_time = datetime.now()
        
        while self.pending_uploads:
            if (datetime.now() - start_time).total_seconds() > max_wait:
                break
            
            authorized_id = self.check_telegram_updates()
            if authorized_id and authorized_id in self.pending_uploads:
                upload_data = self.pending_uploads.pop(authorized_id)
                
                self.update_video_status(authorized_id, 'uploading')
                
                youtube_id = self.upload_video_to_youtube(
                    upload_data['video_file'],
                    upload_data['thumbnail_file'],
                    upload_data['metadata']
                )
                
                if youtube_id:
                    self.update_video_status(authorized_id, 'uploaded', youtube_id)
                    
                    # Eliminar archivos
                    try:
                        upload_data['json_file'].unlink()
                        upload_data['video_file'].unlink()
                        if upload_data['thumbnail_file']:
                            upload_data['thumbnail_file'].unlink()
                        logging.info(f"[CLEANUP] Archivos eliminados: {authorized_id}")
                    except Exception as e:
                        logging.warning(f"[CLEANUP] Error: {e}")
                    
                    # Notificar éxito
                    success_msg = f"✅ <b>Video subido</b>\n\n" \
                                f"🆔 {authorized_id}\n" \
                                f"📺 {youtube_id}\n" \
                                f"🔗 https://youtube.com/watch?v={youtube_id}"
                    self.send_telegram_message(success_msg)
                else:
                    self.update_video_status(authorized_id, 'ok')
                    error_msg = f"❌ Error subiendo: {authorized_id}"
                    self.send_telegram_message(error_msg)
            
            time.sleep(5)
        
        # Timeout para videos no autorizados
        if self.pending_uploads:
            timeout_msg = "⏰ Videos no autorizados:\n"
            for vid_id in self.pending_uploads.keys():
                timeout_msg += f"• {vid_id}\n"
                self.update_video_status(vid_id, 'ok')
            
            self.send_telegram_message(timeout_msg)
            self.pending_uploads.clear()

def main():
    uploader = VideoUploader()
    try:
        uploader.process_ready_videos()
        logging.info("[FINISH] Proceso completado")
    except Exception as e:
        logging.error(f"[CRITICAL] Error: {e}")
        try:
            uploader.send_telegram_message(f"🚨 ERROR CRÍTICO: {str(e)}")
        except:
            pass
        raise

if __name__ == "__main__":
    main()