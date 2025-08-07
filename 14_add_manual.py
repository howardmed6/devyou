import json, subprocess, sys
from datetime import datetime

def add_video(url):
    video_id = url.split('=')[-1] if 'watch?v=' in url else url.split('/')[-1]
    
    try:
        data = json.load(open("data.json", encoding='utf-8'))
        if video_id in {v['video_id'] for v in data}:
            print("Video ya existe")
            return
    except:
        data = []
    
    try:
        r = subprocess.run(['yt-dlp', '--dump-json', '--no-download', url], 
                          capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            info = json.loads(r.stdout)
            video_data = {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": info['title'],
                "channel": info['uploader'],
                "channel_id": info.get('channel_id', ''),
                "published": info.get('upload_date', datetime.now().strftime('%Y%m%d')),
                "found_at": datetime.now().isoformat(),
                "status": "pending"
            }
            data.append(video_data)
            json.dump(data, open("data.json", 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            print(f"Agregado: {info['title']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        add_video(sys.argv[1])
    else:
        print("Uso: python 5_manual_add.py <URL>")