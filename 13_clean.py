import json
from datetime import datetime
from collections import defaultdict

def main():
    # Cargar data.json
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            all_videos = json.load(f)
        print(f"✅ data.json cargado - Total videos: {len(all_videos)}")
    except FileNotFoundError:
        print("❌ Error: No se encontró data.json")
        return
    
    # Agrupar por canal
    videos_by_channel = defaultdict(list)
    for video in all_videos:
        channel = video.get('channel', 'Sin canal')
        videos_by_channel[channel].append(video)
    
    print(f"📺 Canales encontrados: {len(videos_by_channel)}")
    
    # Mostrar estadísticas antes de limpiar
    for channel, videos in videos_by_channel.items():
        print(f"  {channel}: {len(videos)} videos")
    
    # Mantener solo los últimos 11 de cada canal
    videos_to_keep = []
    removed_count = 0
    
    for channel, videos in videos_by_channel.items():
        # Ordenar por fecha (más reciente primero)
        videos.sort(key=lambda x: x.get('published', ''), reverse=True)
        
        # Mantener solo los últimos 11
        keep = videos[:11]
        remove = videos[11:]
        
        videos_to_keep.extend(keep)
        removed_count += len(remove)
        
        if len(videos) > 11:
            print(f"🗑️  {channel}: eliminando {len(remove)} videos (manteniendo {len(keep)})")
        else:
            print(f"✅ {channel}: manteniendo todos los {len(videos)} videos")
    
    # Guardar el data.json limpio
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(videos_to_keep, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 Resumen:")
    print(f"  Videos originales: {len(all_videos)}")
    print(f"  Videos eliminados: {removed_count}")
    print(f"  Videos mantenidos: {len(videos_to_keep)}")
    print(f"✅ data.json actualizado")

if __name__ == "__main__":
    main()