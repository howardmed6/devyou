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
                    
                    # USAR EL TÍTULO DE data.json PARA NOMBRAR EL ARCHIVO
                    name = sanitize(v['title'])
                    print(f"Nombre sanitizado: {name}")
                    
                    # Guardar metadata directamente en videos/{nombre}.json
                    # usando el título de data.json
                    metadata_file = os.path.join("videos", f"{name}.json")
                    
                    # Preparar datos para guardar (con título de la API)
                    json_data = {
                        'title': m['snippet']['title'],
                        'description': m['snippet'].get('description', ''),
                        'tags': m['snippet'].get('tags', []),
                        'categories': ['Entertainment']
                    }
                    
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                    
                    # Actualizar status
                    v['status'] = 'metadata_downloaded'
                    v['sanitized_name'] = name
                    print(f"✓ Metadata guardada en {metadata_file}")
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