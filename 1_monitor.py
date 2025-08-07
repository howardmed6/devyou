import json
import feedparser
from datetime import datetime
import os

def monitor_channels():
    # Lista de canales a monitorear
    channels = [
        "UCcVNDl7ZJMf9lC9a34CY4RA",  # Canal original
        "UC5ZiUaIJ2b5dYBYGf5iEUrA",  # Segundo canal
        "UCjq5m8s71qA9ZMfJw0q7Fgw",  # Tercer canal
        "UCP7i-E6AYr-UChpNcO0EEag"   # Cuarto canal
    ]
    
    data_file = "data.json"
    
    # Cargar datos existentes
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        existing_ids = {item['video_id'] for item in existing_data}
    except:
        existing_data = []
        existing_ids = set()
    
    new_videos_count = 0
    
    # Procesar cada canal
    for channel_id in channels:
        try:
            print(f"Monitoreando canal: {channel_id}")
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                print(f"  No se pudieron obtener videos del canal {channel_id}")
                continue
            
            channel_new_videos = 0
            
            # Procesar los últimos 10 videos del canal
            for entry in feed.entries[:20]:
                video_id = entry.link.split('=')[-1]
                
                if video_id not in existing_ids:
                    video_data = {
                        "video_id": video_id,
                        "url": entry.link,
                        "title": entry.title,
                        "channel": entry.author,
                        "channel_id": channel_id,  # Agregamos el ID del canal
                        "published": entry.published,
                        "found_at": datetime.now().isoformat(),
                        "status": "pending"
                    }
                    existing_data.append(video_data)
                    existing_ids.add(video_id)  # Actualizar el set para evitar duplicados
                    channel_new_videos += 1
                    new_videos_count += 1
                    print(f"  Nuevo video: {entry.title}")
            
            if channel_new_videos == 0:
                print(f"  No hay videos nuevos en este canal")
            else:
                print(f"  Se encontraron {channel_new_videos} videos nuevos")
                
        except Exception as e:
            print(f"Error procesando canal {channel_id}: {e}")
    
    # Guardar datos actualizados
    try:
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        print(f"\nResumen: Se encontraron {new_videos_count} videos nuevos en total")
        print(f"Total de videos en la base de datos: {len(existing_data)}")
    except Exception as e:
        print(f"Error guardando datos: {e}")

if __name__ == "__main__":
    monitor_channels()