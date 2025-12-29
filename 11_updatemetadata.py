import json
import os
import time
import logging
import requests
import unicodedata
from datetime import datetime
from pathlib import Path
import re

# Configurar logging con UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('metadata_updater.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class MetadataUpdater:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.data_json = self.script_dir / "data.json"
        self.uploadable_dir = self.script_dir / "uploadable"
        
        # API Claude y Telegram desde variables de entorno - SIN HARDCODEAR
        self.api_key = os.environ.get('CLAUDE_API_KEY')
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.bot_token = os.environ.get('BOT_TOKEN')
        self.chat_id = os.environ.get('CHAT_ID')
        
        # Validar que las variables de entorno estén disponibles
        if not self.api_key:
            logging.error("[INIT] ❌ CLAUDE_API_KEY no encontrada en variables de entorno")
            logging.error("[INIT] 💡 Configura el secreto CLAUDE_API_KEY en GitHub Actions")
        
        if not self.bot_token:
            logging.error("[INIT] ❌ BOT_TOKEN no encontrada en variables de entorno")
            logging.error("[INIT] 💡 Configura el secreto TELEGRAM_BOT_TOKEN en GitHub Actions")
            
        if not self.chat_id:
            logging.error("[INIT] ❌ CHAT_ID no encontrada en variables de entorno")
            logging.error("[INIT] 💡 Configura el secreto TELEGRAM_CHAT_ID en GitHub Actions")
        
        logging.info(f"[INIT] Archivo data.json: {self.data_json}")
        logging.info(f"[INIT] Carpeta uploadable: {self.uploadable_dir}")
        logging.info(f"[INIT] API Key disponible: {'Sí' if self.api_key else 'No'}")
        logging.info(f"[INIT] Bot Token disponible: {'Sí' if self.bot_token else 'No'}")
        logging.info(f"[INIT] Chat ID disponible: {'Sí' if self.chat_id else 'No'}")
        
        # Solo mostrar primeros caracteres si la API key existe
        if self.api_key:
            logging.info(f"[INIT] API Key (primeros 15 chars): {self.api_key[:15]}...")
        
        if not self.uploadable_dir.exists():
            logging.error(f"[ERROR] La carpeta uploadable no existe: {self.uploadable_dir}")
            raise FileNotFoundError(f"La carpeta uploadable no existe: {self.uploadable_dir}")
    
    def validate_api_key(self):
        """Valida el formato de la API key de Claude"""
        if not self.api_key:
            logging.error("[API] ❌ API Key de Claude no encontrada en variables de entorno")
            logging.error("[API] 💡 Asegúrate de que CLAUDE_API_KEY esté configurada como secreto en GitHub")
            return False
        
        # Las API keys de Claude empiezan con 'sk-ant-api03-'
        if not self.api_key.startswith('sk-ant-api03-'):
            logging.error(f"[API] ❌ API Key no tiene el formato correcto")
            logging.error(f"[API] Expected: sk-ant-api03-...")
            logging.error(f"[API] Current: {self.api_key[:20]}...")
            return False
        
        # Verificar longitud aproximada (las API keys suelen tener ~100 caracteres)
        if len(self.api_key) < 50:
            logging.error(f"[API] ❌ API Key parece muy corta ({len(self.api_key)} caracteres)")
            return False
        
        logging.info("[API] ✅ API Key tiene formato válido")
        return True
    
    def send_telegram_notification(self, message):
        """Envía notificación por Telegram"""
        if not self.bot_token or not self.chat_id:
            logging.warning("[TELEGRAM] Bot token o chat ID no disponibles")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logging.info("[TELEGRAM] Notificación enviada exitosamente")
                return True
            else:
                logging.warning(f"[TELEGRAM] Error al enviar notificación: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"[TELEGRAM] Error en notificación: {e}")
            return False
    
    def load_data_json(self):
        """Carga el archivo data.json"""
        if not self.data_json.exists():
            logging.error(f"[ERROR] Archivo data.json no encontrado: {self.data_json}")
            return []
        
        try:
            with open(self.data_json, 'r', encoding='utf-8') as f:
                videos = json.load(f)
            logging.info(f"[JSON] Cargados {len(videos)} videos desde data.json")
            return videos
        except Exception as e:
            logging.error(f"[ERROR] Error al leer data.json: {e}")
            return []
    
    def save_data_json(self, videos):
        """Guarda el archivo data.json actualizado"""
        try:
            with open(self.data_json, 'w', encoding='utf-8') as f:
                json.dump(videos, f, indent=2, ensure_ascii=False)
            logging.info("[JSON] data.json actualizado exitosamente")
            return True
        except Exception as e:
            logging.error(f"[ERROR] Error al guardar data.json: {e}")
            return False
    
    def find_edited_videos(self):
        """Encuentra videos con estado 'edited'"""
        videos = self.load_data_json()
        if not videos:
            return []
        
        edited_videos = [video for video in videos if video.get('status') == 'edited']
        logging.info(f"[FILTER] Encontrados {len(edited_videos)} videos con estado 'edited'")
        return edited_videos
    
    def clean_and_get_first_words(self, text, count=3):
        """Limpia el texto y obtiene las primeras 'count' palabras significativas"""
        if not text:
            return []
        
        # Quitar paréntesis y contenido
        if '(' in text:
            text = text.split('(')[0]
        
        # Normalizar caracteres Unicode (quitar tildes)
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        
        # Limpiar caracteres especiales
        text = re.sub(r'[¿?¡!:;,.]', '', text)
        text = text.lower().strip()
        
        # Extraer palabras (más de 2 caracteres)
        words = [word for word in text.split() if len(word) > 2]
        
        # Retornar las primeras 'count' palabras
        return words[:count]
    
    def find_json_file_by_title(self, title):
        """Busca el archivo JSON comparando las primeras 3 palabras del título"""
        logging.info(f"[SEARCH] Buscando JSON para: '{title}'")
        
        if not self.uploadable_dir.exists():
            logging.error(f"[ERROR] Carpeta uploadable no existe: {self.uploadable_dir}")
            return None, None
        
        # Obtener las primeras 3 palabras del título buscado
        title_first_words = self.clean_and_get_first_words(title, 3)
        logging.info(f"[SEARCH] Primeras 3 palabras del título: {title_first_words}")
        
        if len(title_first_words) < 3:
            logging.warning(f"[SEARCH] El título no tiene suficientes palabras para comparar")
            return None, None
        
        # Buscar archivos JSON en la carpeta uploadable
        json_files = list(self.uploadable_dir.glob("*.json"))
        logging.info(f"[SEARCH] Encontrados {len(json_files)} archivos JSON en uploadable")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                json_title = json_data.get('title', '')
                json_first_words = self.clean_and_get_first_words(json_title, 3)
                
                logging.info(f"[COMPARE] Archivo: {json_file.name}")
                logging.info(f"[COMPARE] Título JSON: '{json_title}'")
                logging.info(f"[COMPARE] Primeras 3 palabras JSON: {json_first_words}")
                
                # Verificar si las primeras 3 palabras coinciden exactamente
                if len(json_first_words) >= 3 and title_first_words == json_first_words:
                    logging.info(f"[MATCH] ✓ Coincidencia exacta encontrada: {json_file.name}")
                    return json_file, json_data
                    
            except Exception as e:
                logging.warning(f"[WARNING] Error al leer {json_file.name}: {e}")
                continue
        
        logging.warning(f"[NOT FOUND] No se encontró JSON con coincidencia exacta para: '{title}'")
        return None, None
    
    def create_claude_prompt(self, video_metadata):
        """Crea el prompt para la API de Claude"""
        title = video_metadata.get('title', '')
        description = video_metadata.get('description', '')
        tags = video_metadata.get('tags', [])
        tags_str = ', '.join(tags) if isinstance(tags, list) else str(tags)
        
        return f"""Mejora estos metadatos de video de YouTube siguiendo EXACTAMENTE el formato solicitado:

METADATOS ACTUALES:
TÍTULO: {title}
DESCRIPCIÓN: {description}
TAGS ACTUALES: {tags_str}

INSTRUCCIONES ESPECÍFICAS:

1. TÍTULO (sin emojis y sin nombre de actores):
- Mantener el nombre de película/serie en MAYÚSCULAS
- SIEMPRE incluir la palabra "Tráiler" o "Trailer"
- Si menciona "español latino", mantener esas palabras
- Mantener el año entre paréntesis (2025) y no poner años anteriores al 2025
- Hacer el título más atractivo y profesional

2. DESCRIPCIÓN (300-600 palabras):
- Crear una descripción completamente nueva y atractiva con base a la info del cine mas reciente
- Incluir emojis relevantes (🎬🔥⚡🎭)
- Añadir información intrigante sobre la película/serie
- Incluir llamados a la acción (like, comentario, suscripción)
- Añadir hashtags relevantes al final, minimo 10
- Hacer que suene profesional y emocionante

3. TAGS:
- Quitar al menos 2-3 tags actuales
- Añadir 3-5 nuevos tags más específicos y relevantes
- Total final: entre 5-12 tags optimizados
- Incluir tags en español e inglés
- Priorizar tags relacionados con trailers, películas, entretenimiento

FORMATO DE RESPUESTA REQUERIDO:
TÍTULO: [título mejorado sin emojis]
DESCRIPCIÓN: [descripción completa con emojis y hashtags]
TAGS: [tag1, tag2, tag3, etc.]

Responde SOLO con el formato anterior, sin explicaciones adicionales."""
    
    def call_claude_api(self, prompt):
        """Llama a la API de Claude con validaciones mejoradas"""
        # Validar API key antes de hacer la llamada
        if not self.validate_api_key():
            return None
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        
        try:
            logging.info("[API] 🚀 Enviando solicitud a Claude...")
            logging.info(f"[API] 🌐 Endpoint: {self.api_url}")
            logging.info(f"[API] 🔑 API Key válida: ✅")
            logging.info(f"[API] 📊 Modelo: {data['model']}")
            
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=120
            )
            
            logging.info(f"[API] 📊 Código de respuesta: {response.status_code}")
            
            # Manejar diferentes códigos de error
            if response.status_code == 401:
                logging.error("=" * 60)
                logging.error("[API] 🚨 ERROR 401 - UNAUTHORIZED")
                logging.error("=" * 60)
                
                try:
                    error_data = response.json()
                    logging.error(f"[API] 💬 Error detallado: {error_data}")
                except:
                    logging.error(f"[API] 📄 Respuesta raw: {response.text}")
                
                logging.error("[API] ✅ Soluciones posibles:")
                logging.error("[API] 1. Verifica que CLAUDE_API_KEY esté bien configurada en GitHub Secrets")
                logging.error("[API] 2. Ve a https://console.anthropic.com/ y genera una nueva API key")
                logging.error("[API] 3. Asegúrate de tener créditos disponibles")
                logging.error("[API] 4. Verifica que la API key no haya expirado")
                logging.error("=" * 60)
                return None
                
            elif response.status_code == 400:
                logging.error("[API] ❌ Error 400: Petición mal formada")
                try:
                    error_data = response.json()
                    logging.error(f"[API] Detalle: {error_data}")
                except:
                    logging.error(f"[API] Respuesta: {response.text}")
                return None
                
            elif response.status_code == 403:
                logging.error("[API] ❌ Error 403: Acceso prohibido - API key sin permisos")
                return None
                
            elif response.status_code == 429:
                logging.warning("[API] ⚠️ Rate limit alcanzado, esperando 30 segundos...")
                time.sleep(30)
                return None
                
            elif response.status_code == 500:
                logging.error("[API] ❌ Error 500: Error interno del servidor Claude")
                return None
                
            elif response.status_code != 200:
                logging.error(f"[API] ❌ Error HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    logging.error(f"[API] Detalle: {error_data}")
                except:
                    logging.error(f"[API] Respuesta: {response.text}")
                return None
            
            # Parsear respuesta exitosa
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logging.error(f"[API] ❌ Error al parsear JSON: {e}")
                logging.error(f"[API] Respuesta raw: {response.text}")
                return None
            
            # Validar estructura de respuesta
            if 'content' not in result:
                logging.error(f"[API] ❌ Respuesta sin campo 'content': {result}")
                return None
                
            if not result['content'] or len(result['content']) == 0:
                logging.error(f"[API] ❌ Campo 'content' vacío: {result}")
                return None
                
            if 'text' not in result['content'][0]:
                logging.error(f"[API] ❌ Primer elemento de content sin 'text': {result['content'][0]}")
                return None
            
            content = result['content'][0]['text']
            logging.info("[API] ✅ Respuesta recibida exitosamente")
            logging.info(f"[API] 📏 Longitud de respuesta: {len(content)} caracteres")
            logging.info(f"[API] 📝 Inicio de respuesta: {content[:100]}...")
            
            return content
            
        except requests.exceptions.Timeout:
            logging.error("[API] ⏰ Timeout en la solicitud a Claude (120s)")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"[API] 🌐 Error de conexión: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"[API] 🌐 Error de requests: {e}")
            return None
        except Exception as e:
            logging.error(f"[API] 💥 Error inesperado: {e}")
            import traceback
            logging.error(f"[API] 🔍 Traceback: {traceback.format_exc()}")
            return None
    
    def parse_claude_response(self, response_text):
        """Parsea la respuesta de Claude"""
        try:
            logging.info("[PARSE] Parseando respuesta de Claude...")
            response_text = response_text.strip()
            parsed_data = {}
            
            patterns = {
                'title': r'TÍTULO:\s*(.+?)(?=\n|$)',
                'description': r'DESCRIPCIÓN:\s*(.*?)(?=\nTAGS:|$)',
                'tags': r'TAGS:\s*(.+?)(?=\n|$)'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    
                    if key == 'tags':
                        tags_list = [tag.strip() for tag in value.split(',')]
                        parsed_data[key] = [tag for tag in tags_list if tag]
                    else:
                        parsed_data[key] = value
                else:
                    logging.warning(f"[PARSE] No se encontró {key} en la respuesta")
            
            required_fields = ['title', 'description', 'tags']
            missing_fields = [field for field in required_fields if field not in parsed_data or not parsed_data[field]]
            
            if missing_fields:
                logging.error(f"[PARSE] Campos faltantes: {missing_fields}")
                logging.error(f"[PARSE] Respuesta original: {response_text}")
                return None
            
            logging.info("[PARSE] Datos parseados exitosamente:")
            logging.info(f"  - Título: {parsed_data['title'][:50]}...")
            logging.info(f"  - Descripción: {len(parsed_data['description'])} caracteres")
            logging.info(f"  - Tags: {len(parsed_data['tags'])} elementos")
            
            return parsed_data
            
        except Exception as e:
            logging.error(f"[PARSE] Error al parsear respuesta: {e}")
            return None
    
    def update_video_json(self, json_file, json_data, claude_metadata):
        """Actualiza el archivo JSON del video"""
        try:
            if claude_metadata:
                json_data.update({
                    'title': claude_metadata['title'],
                    'description': claude_metadata['description'],
                    'tags': claude_metadata['tags']
                })
                logging.info("[UPDATE] Metadatos actualizados con respuesta de Claude")
            else:
                logging.warning("[UPDATE] No hay metadatos de Claude, manteniendo originales")
            
            json_data['categories'] = ['Trailer']
            json_data.pop('channel', None)  # Eliminar campo del canal si existe
            json_data['metadata_updated_at'] = datetime.now().isoformat()
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"[UPDATE] JSON actualizado: {json_file.name}")
            return True
            
        except Exception as e:
            logging.error(f"[UPDATE] Error al actualizar JSON: {e}")
            return False
    
    def update_video_status(self, video_id, new_status='ok'):
        """Actualiza el estado del video en data.json"""
        videos = self.load_data_json()
        if not videos:
            return False
        
        for video in videos:
            if video.get('video_id', '') == video_id:
                video['status'] = new_status
                video['metadata_updated_at'] = datetime.now().isoformat()
                logging.info(f"[STATUS] Video {video_id} actualizado a '{new_status}'")
                return self.save_data_json(videos)
        
        logging.warning(f"[STATUS] Video {video_id} no encontrado")
        return False
    
    def process_edited_videos(self):
        """Procesa todos los videos con estado 'edited'"""
        logging.info("[START] Iniciando procesamiento de videos editados...")
        
        # Validar configuración inicial
        if not self.validate_api_key():
            error_msg = "🚨 <b>ERROR CRÍTICO</b>\n\n❌ API Key de Claude no válida\n\n" \
                       "✅ <b>Soluciones:</b>\n" \
                       "1. Ve a https://console.anthropic.com/\n" \
                       "2. Genera una nueva API key\n" \
                       "3. Configúrala como secreto CLAUDE_API_KEY en GitHub\n" \
                       "4. Verifica que tengas créditos"
            self.send_telegram_notification(error_msg)
            return
        
        edited_videos = self.find_edited_videos()
        
        if not edited_videos:
            logging.info("[EMPTY] No hay videos con estado 'edited' para procesar")
            message = "🤖 <b>Metadata Updater</b>\n\nℹ️ No hay videos con estado 'edited' para procesar."
            self.send_telegram_notification(message)
            return
        
        logging.info(f"[PROCESS] Procesando {len(edited_videos)} videos...")
        
        successful_updates = 0
        updated_videos = []
        failed_videos = []
        
        for i, video_data in enumerate(edited_videos, 1):
            logging.info(f"\n--- Procesando video {i}/{len(edited_videos)} ---")
            
            title = video_data.get('title', 'Sin título')
            video_id = video_data.get('video_id', '')
            
            logging.info(f"[VIDEO] Título: {title}")
            logging.info(f"[VIDEO] ID: {video_id}")
            
            # Buscar archivo JSON correspondiente
            json_file, json_data = self.find_json_file_by_title(title)
            
            if not json_file or not json_data:
                logging.error(f"[ERROR] No se encontró JSON para el video: {title}")
                failed_videos.append({
                    'title': title,
                    'video_id': video_id,
                    'reason': 'JSON no encontrado'
                })
                continue
            
            # Procesar con Claude
            prompt = self.create_claude_prompt(json_data)
            claude_response = self.call_claude_api(prompt)
            claude_metadata = None
            
            if claude_response:
                claude_metadata = self.parse_claude_response(claude_response)
                if not claude_metadata:
                    logging.warning("[WARNING] No se pudo parsear respuesta de Claude")
            else:
                logging.warning("[WARNING] No se pudo obtener respuesta de Claude, continuando con datos originales")
            
            # Actualizar archivos (incluso si Claude falló)
            if self.update_video_json(json_file, json_data, claude_metadata):
                if self.update_video_status(video_id, 'ok'):
                    successful_updates += 1
                    updated_videos.append({
                        'title': title,
                        'video_id': video_id,
                        'new_title': claude_metadata['title'] if claude_metadata else title,
                        'claude_used': bool(claude_metadata)
                    })
                    logging.info(f"[SUCCESS] Video {i} procesado exitosamente")
                else:
                    logging.error(f"[ERROR] Error al actualizar estado del video {i}")
                    failed_videos.append({
                        'title': title,
                        'video_id': video_id,
                        'reason': 'Error al actualizar estado'
                    })
            else:
                logging.error(f"[ERROR] Error al actualizar JSON del video {i}")
                failed_videos.append({
                    'title': title,
                    'video_id': video_id,
                    'reason': 'Error al actualizar JSON'
                })
            
            # Pequeña pausa entre requests para evitar rate limits
            if i < len(edited_videos):
                time.sleep(2)
        
        # Resumen
        logging.info(f"\n[SUMMARY] Procesamiento completado:")
        logging.info(f"[SUMMARY] Videos procesados exitosamente: {successful_updates}")
        logging.info(f"[SUMMARY] Videos fallidos: {len(edited_videos) - successful_updates}")
        
        self.send_process_summary_notification(updated_videos, failed_videos, len(edited_videos))
    
    def send_process_summary_notification(self, updated_videos, failed_videos, total_videos):
        """Envía un resumen del procesamiento por Telegram"""
        try:
            claude_success = sum(1 for v in updated_videos if v.get('claude_used', False))
            claude_failed = len(updated_videos) - claude_success
            
            message = "🤖 <b>Metadata Updater - Resumen</b>\n"
            message += f"📊 <b>Total procesados:</b> {total_videos}\n"
            message += f"✅ <b>Exitosos:</b> {len(updated_videos)}\n"
            message += f"❌ <b>Fallidos:</b> {len(failed_videos)}\n"
            message += f"🤖 <b>Claude exitoso:</b> {claude_success}\n"
            message += f"⚠️ <b>Sin Claude:</b> {claude_failed}\n\n"
            
            if updated_videos:
                message += "🎬 <b>Videos actualizados:</b>\n"
                for i, video in enumerate(updated_videos[:5], 1):  # Solo primeros 5
                    title = video['title'][:50] + "..." if len(video['title']) > 50 else video['title']
                    claude_emoji = "🤖" if video.get('claude_used') else "⚠️"
                    
                    message += f"{i}. {claude_emoji} <code>{video['video_id']}</code>\n"
                    message += f"   📝 {title}\n"
                
                if len(updated_videos) > 5:
                    message += f"... y {len(updated_videos) - 5} videos más.\n"
            
            if failed_videos:
                message += f"\n❌ <b>Errores ({len(failed_videos)}):</b>\n"
                for i, video in enumerate(failed_videos[:3], 1):  # Solo primeros 3
                    title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
                    message += f"{i}. {title}\n"
                    message += f"   🚫 {video['reason']}\n"
                
                if len(failed_videos) > 3:
                    message += f"... y {len(failed_videos) - 3} errores más.\n"
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message += f"\n🕒 <b>Completado:</b> {now}"
            
            self.send_telegram_notification(message)
            
        except Exception as e:
            logging.error(f"[TELEGRAM] Error al crear mensaje de resumen: {e}")
            simple_message = f"🤖 Metadata Updater completado\n" \
                           f"✅ Exitosos: {len(updated_videos)}\n" \
                           f"❌ Fallidos: {len(failed_videos)}"
            self.send_telegram_notification(simple_message)

def main():
    """Función principal"""
    updater = MetadataUpdater()
    
    try:
        updater.process_edited_videos()
        logging.info("[FINISH] Proceso completado exitosamente")
    except Exception as e:
        logging.error(f"[CRITICAL] Error crítico: {e}")
        error_message = f"🚨 <b>ERROR CRÍTICO - Metadata Updater</b>\n\n" \
                       f"💥 Error: {str(e)}\n" \
                       f"🕒 Tiempo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            updater.send_telegram_notification(error_message)
        except:
            pass
        raise

if __name__ == "__main__":
    main()
