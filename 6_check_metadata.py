import json, os, re

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def check_metadata_files():
    try:
        data = json.load(open("data.json", encoding='utf-8'))
    except:
        return
    
    reverted = 0
    for v in data:
        if v.get('status') == 'metadata_update':
            if not os.path.exists(f"videos/{sanitize(v['title'])}.json"):
                v['status'] = 'pending'
                reverted += 1
                print(f"Revertido: {v['title']}")
    
    if reverted > 0:
        json.dump(data, open("data.json", 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
        print(f"Se revirtieron {reverted} videos")

if __name__ == "__main__":
    check_metadata_files()