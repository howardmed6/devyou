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
        self.bot_token = os.environ.get('BOT_TOKEN', "7869024150:AAGFO6ZvpO4-5J4karX_lef252tkD3BhclE")
        self.chat_id = os.environ.get('CHAT_ID', "6166225652")
        
        # Configuración YouTube API
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        self.CLIENT_SECRETS_FILE = "client_secrets.json"
        self.TOKEN_FILE = "youtube_token.json"
        
        if not self.uploadable_dir.exists():
            logging.warning(f"La carpeta uploadable no existe: {self.uploadable_dir}")
            self.uploadable_dir.mkdir(exist_ok=True)
    
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
                
                # En entorno de GitHub Actions, no podemos hacer autenticación interactiva
                logging.error("[YOUTUBE] Se requiere autenticación interactiva, no disponible en GitHub Actions")
                return None
        
        if credentials:
            # Guardar credenciales actualizadas
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
    
    def get_single_files_fallback(self):
        """Obtiene archivos únicos como fallback"""
        all_files = list(self.uploadable_dir.glob("*"))
        
        # Separar archivos por tipo
        json_files = [f for f in all_files if f.suffix.lower() == '.json']
        video_files = [f for f in all_files if f.suffix.lower() == '.mp4']
        thumbnail_files = [f for f in all_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
        
        # Solo usar fallback si hay exactamente un archivo de cada tipo necesario
        single_json = json_files[0] if len(json_files) == 1 else None
        single_video = video_files[0] if len(video_files) == 1 else None
        single_thumbnail = thumbnail_files[0] if len(thumbnail_files) == 1 else None
        
        logging.info(f"[FALLBACK] Archivos únicos encontrados:")
        logging.info(f"[FALLBACK] JSON: {single_json.name if single_json else 'Ninguno'} (Total: {len(json_files)})")
        logging.info(f"[FALLBACK] Video: {single_video.name if single_video else 'Ninguno'} (Total: {len(video_files)})")
        logging.info(f"[FALLBACK] Thumbnail: {single_thumbnail.name if single_thumbnail else 'Ninguno'} (Total: {len(thumbnail_files)})")
        
        return single_json, single_video, single_thumbnail
    
    def find_exact_match_files(self, title):
        """Busca archivos que coincidan por las primeras 3 palabras, con fallback a archivos únicos"""
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
        
        # FALLBACK: Si no se encontraron archivos por coincidencia, usar archivos únicos
        if not json_file or not video_file:
            logging.warning(f"[FALLBACK] No se encontraron archivos por coincidencia para '{title}', intentando con archivos únicos...")
            
            fallback_json, fallback_video, fallback_thumbnail = self.get_single_files_fallback()
            
            # Solo usar fallback si hay exactamente un archivo de cada tipo requerido
            if not json_file and fallback_json:
                json_file = fallback_json
                logging.info(f"[FALLBACK] Usando JSON único: {json_file.name}")
            
            if not video_file and fallback_video:
                video_file = fallback_video
                logging.info(f"[FALLBACK] Usando video único: {video_file.name}")
            
            # Para thumbnail, usar fallback solo si no se encontró uno específico
            if not thumbnail_file and fallback_thumbnail:
                thumbnail_file = fallback_thumbnail
                logging.info(f"[FALLBACK] Usando thumbnail único: {thumbnail_file.name}")
        
        # Registrar archivos finales encontrados
        if json_file:
            logging.info(f"[FILES] JSON: {json_file.name}")
        else:
            logging.error(f"[FILES] JSON: No encontrado")
            
        if video_file:
            logging.info(f"[FILES] Video: {video_file.name}")
        else:
            logging.error(f"[FILES] Video: No encontrado")
            
        if thumbnail_file:
            logging.info(f"[FILES] Thumbnail: {thumbnail_file.name}")
        else:
            logging.warning(f"[FILES] Thumbnail: No encontrado")
        
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
                logging.error("[YOUTUBE] No se pudo obtener servicio de YouTube")
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
    
    def process_ready_videos_auto(self):
        """Procesa videos listos automáticamente (SIN AUTORIZACIÓN)"""
        videos = self.load_data_json()
        ready_videos = [v for v in videos if v.get('status') == 'ok']
        
        if not ready_videos:
            logging.info("[PROCESS] No hay videos listos para subir")
            self.send_telegram_message("ℹ️ No hay videos listos para subir")
            return
        
        logging.info(f"[PROCESS] {len(ready_videos)} videos listos para subir automáticamente")
        self.send_telegram_message(f"🚀 Iniciando subida automática de {len(ready_videos)} videos")
        
        uploaded_count = 0
        error_count = 0
        
        for video_data in ready_videos:
            title = video_data.get('title', 'Sin título')
            video_id = video_data.get('video_id', '')
            
            logging.info(f"[UPLOAD] Procesando: {title}")
            
            # Buscar archivos con coincidencia por primeras 3 palabras o fallback a archivos únicos
            json_file, video_file, thumbnail_file, metadata = self.find_exact_match_files(title)
            
            # Solo requiere JSON con metadata y MP4 (thumbnail es opcional)
            if not json_file or not video_file or not metadata:
                missing = []
                if not json_file: missing.append("JSON")
                if not video_file: missing.append("MP4")
                if not metadata: missing.append("metadata")
                
                logging.error(f"[ERROR] Faltan archivos para '{title}': {', '.join(missing)}")
                self.update_video_status(video_id, f'error - faltan: {", ".join(missing)}')
                error_count += 1
                continue
            
            # Si no hay thumbnail, continuar sin ella
            if not thumbnail_file:
                logging.warning(f"[WARNING] No se encontró thumbnail para: {title}, continuando sin thumbnail")
            
            # Actualizar estado a "uploading"
            self.update_video_status(video_id, 'uploading')
            
            # Subir a YouTube
            youtube_id = self.upload_video_to_youtube(video_file, thumbnail_file, metadata)
            
            if youtube_id:
                # Éxito: actualizar estado y limpiar archivos
                self.update_video_status(video_id, 'uploaded', youtube_id)
                uploaded_count += 1
                
                # Eliminar archivos
                try:
                    json_file.unlink()
                    video_file.unlink()
                    if thumbnail_file:
                        thumbnail_file.unlink()
                    logging.info(f"[CLEANUP] Archivos eliminados: {video_id}")
                except Exception as e:
                    logging.warning(f"[CLEANUP] Error: {e}")
                
                # Notificar éxito
                success_msg = f"✅ <b>Video subido automáticamente</b>\n\n" \
                            f"📝 <b>Título:</b> {title[:50]}...\n" \
                            f"🆔 <b>Video ID:</b> <code>{video_id}</code>\n" \
                            f"📺 <b>YouTube ID:</b> <code>{youtube_id}</code>\n" \
                            f"🔗 https://youtube.com/watch?v={youtube_id}"
                self.send_telegram_message(success_msg)
                
            else:
                # Error: revertir estado a "ok" para reintentar más tarde
                self.update_video_status(video_id, 'ok')
                error_count += 1
                error_msg = f"❌ <b>Error subiendo video</b>\n\n" \
                           f"📝 <b>Título:</b> {title[:50]}...\n" \
                           f"🆔 <b>Video ID:</b> <code>{video_id}</code>"
                self.send_telegram_message(error_msg)
            
            # Pequeña pausa entre subidas
            time.sleep(2)
        
        # Resumen final
        final_msg = f"📊 <b>Resumen de subida automática</b>\n\n" \
                   f"✅ <b>Subidos:</b> {uploaded_count}\n" \
                   f"❌ <b>Errores:</b> {error_count}\n" \
                   f"📊 <b>Total procesados:</b> {uploaded_count + error_count}"
        
        self.send_telegram_message(final_msg)
        logging.info(f"[FINISH] Subida automática completada: {uploaded_count} éxitos, {error_count} errores")

def main():
    uploader = VideoUploader()
    try:
        # Proceso automático sin autorización
        uploader.process_ready_videos_auto()
        logging.info("[FINISH] Proceso completado")
    except Exception as e:
        logging.error(f"[CRITICAL] Error: {e}")
        try:
            uploader.send_telegram_message(f"🚨 ERROR CRÍTICO EN SUBIDA AUTOMÁTICA: {str(e)}")
        except:
            pass
        raise

if __name__ == "__main__":
    main()