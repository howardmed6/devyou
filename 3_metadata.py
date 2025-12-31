import json
import requests
import os
import re

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def download_metadata():
    API_KEY = "AIzaSyBZUaGb5RXQOSGpVH25MS3vw1wSggAPZnc"
    
    try:
        data = json.load(open("data.json", encoding='utf-8'))
        print(f"Cargados {len(data)} videos del data.json")
    except:
        print("Error cargando data.json")
        return
    
    os.makedirs("videos", exist_ok=True)
    
    for v in data:
        if v.get('status') == 'pending':
            print(f"Procesando: {v['title']}")
            try:
                video_id = v['video_id']
                
                # Obtener metadatos con YouTube API
                url = "https://www.googleapis.com/youtube/v3/videos"
                params = {
                    'key': API_KEY,
                    'id': video_id,
                    'part': 'snippet,contentDetails,statistics'
                }
                
                response = requests.get(url, params=params)
                result = response.json()
                
                if 'items' in result and len(result['items']) > 0:
                    m = result['items'][0]
                    name = sanitize(m['snippet']['title'])
                    print(f"Nombre sanitizado: {name}")
                    
                    # Guardar metadata
                    video_dir = os.path.join("videos", name)
                    os.makedirs(video_dir, exist_ok=True)
                    
                    with open(os.path.join(video_dir, "metadata.json"), 'w', encoding='utf-8') as f:
                        json.dump(m, f, indent=2, ensure_ascii=False)
                    
                    # Actualizar status
                    v['status'] = 'metadata_downloaded'
                    v['sanitized_name'] = name
                    print(f"✓ Metadata guardada")
                else:
                    print(f"Error: No se encontró el video")
                    v['status'] = 'error'
                    
            except Exception as e:
                print(f"Excepción: {e}")
                v['status'] = 'error'
    
    # Guardar data.json actualizado
    with open("data.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    download_metadata()