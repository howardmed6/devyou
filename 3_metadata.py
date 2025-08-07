import json, subprocess, os, re

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def download_metadata():
    try:
        data = json.load(open("data.json", encoding='utf-8'))
        print(f"Cargados {len(data)} videos del data.json")  # DEBUG
    except:
        print("Error cargando data.json")  # DEBUG
        return

    os.makedirs("videos", exist_ok=True)

    for v in data:
        if v.get('status') == 'pending':
            print(f"Procesando: {v['title']}")  # DEBUG
            try:
                r = subprocess.run(['yt-dlp', '--dump-json', v['url']], capture_output=True, text=True)
                print(f"yt-dlp returncode: {r.returncode}")  # DEBUG
                if r.returncode == 0:
                    m = json.loads(r.stdout)
                    name = sanitize(m['title'])
                    print(f"Nombre sanitizado: {name}")  # DEBUG
                    # ... resto del código igual
                else:
                    print(f"Error yt-dlp: {r.stderr}")  # DEBUG
            except Exception as e:
                print(f"Excepción: {e}")  # DEBUG

if __name__ == "__main__":
    download_metadata()