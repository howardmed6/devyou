import json, requests, re, os
from urllib.parse import unquote

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

def get_video_info(url):
    """Extrae información básica del HTML de YouTube"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        title_match = re.search(r'<title>([^<]+)</title>', html)
        title = title_match.group(1).replace(' - YouTube', '') if title_match else 'Título no disponible'
        
        channel_patterns = [
            r'"ownerText":{"runs":\[{"text":"([^"]+)"',
            r'"author":"([^"]+)"',
            r'<link itemprop="name" content="([^"]+)">'
        ]
        
        channel = "Canal no disponible"
        for pattern in channel_patterns:
            match = re.search(pattern, html)
            if match:
                channel = match.group(1)
                break
        
       
        desc_patterns = [
            r'"shortDescription":"([^"]*)"',
            r'<meta name="description" content="([^"]*)"'
        ]
        
        description = ""
        for pattern in desc_patterns:
            match = re.search(pattern, html)
            if match:
                description = unquote(match.group(1)).replace('\\n', '\n')
                break
        
        
        tags = []
        if 'oficial' in title.lower(): tags.append('oficial')
        if 'trailer' in title.lower() or 'tráiler' in title.lower(): tags.append('trailer')
        if 'netflix' in title.lower(): tags.append('netflix')
        
        return {
            "title": title,
            "channel": channel,
            "description": description,
            "tags": tags,
            "categories": ["Entertainment"]  
        }
        
    except Exception as e:
        print(f"Error obteniendo info: {e}")
        return None

def backup_metadata():
    try:
        data = json.load(open("data.json", encoding='utf-8'))
    except:
        return

    os.makedirs("videos", exist_ok=True)

    for v in data:
        if v.get('status') == 'pending':
            try:
                info = get_video_info(v['url'])
                if info:
                    name = sanitize(v['title'])  
                    out = {
                        "title": v['title'],     
                        "channel": v['channel'],  
                        "description": info.get('description', ''),
                        "tags": info.get('tags', []),
                        "categories": info.get('categories', [])
                    }
                    with open(f"videos/{name}.json", 'w', encoding='utf-8') as f:
                        json.dump(out, f, ensure_ascii=False, indent=2)
                    print(f"Metadatos: {name}")
            except:
                pass

if __name__ == "__main__":
    backup_metadata()