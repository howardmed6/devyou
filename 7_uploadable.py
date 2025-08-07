import json
import os
import shutil
from pathlib import Path

def clean_name(name):
    """Limpia el nombre para comparación"""
    # Quitar todo después del primer paréntesis
    if '(' in name:
        name = name.split('(')[0]
    
    # Limpiar caracteres especiales (incluyendo barras verticales)
    name = name.replace('¿', '').replace('?', '').replace('¡', '').replace('!', '')
    name = name.replace(':', '').replace(';', '').replace(',', '').replace('.', '')
    name = name.replace('|', '').replace('/', '').replace('\\', '')  # Agregar barras
    name = name.replace(' ', '').replace('_', '').replace('-', '')
    
    return name.lower().strip()

def main():
    # Cargar data.json
    with open('data.json', 'r', encoding='utf-8') as f:
        all_videos = json.load(f)
        
    videos_to_process = [v for v in all_videos if v.get('status') == 'metadata_update']
    print(f"Videos a procesar: {len(videos_to_process)}")
        
    video_folder = Path('videos')
    uploadable_folder = Path('uploadable')
    uploadable_folder.mkdir(exist_ok=True)
        
    # Obtener todos los archivos
    all_files = os.listdir(video_folder)
        
    moved = 0
    for video in videos_to_process:
        title = video['title']
        title_clean = clean_name(title)
                
        print(f"\n--- {video['title'][:50]}{'...' if len(video['title']) > 50 else ''} ---")
                
        # Buscar archivos que coincidan
        matching_files = []
        for file in all_files:
            file_clean = clean_name(Path(file).stem)
            
            # Estrategia 1: coincidencia exacta o contención
            if title_clean in file_clean or file_clean in title_clean:
                matching_files.append(file)
            # Estrategia 2: primeras 10 letras coinciden
            elif len(title_clean) >= 10 and len(file_clean) >= 10:
                if title_clean[:10] == file_clean[:10]:
                    matching_files.append(file)
            # Estrategia 3: coincidencia de 80% de caracteres
            elif len(title_clean) >= 8 and len(file_clean) >= 8:
                shorter = min(len(title_clean), len(file_clean))
                matches = sum(1 for a, b in zip(title_clean, file_clean) if a == b)
                if matches / shorter >= 0.8:
                    matching_files.append(file)
                
        # Separar por tipo
        mp4_files = [f for f in matching_files if f.endswith('.mp4')]
        json_files = [f for f in matching_files if f.endswith('.json')]
        img_files = [f for f in matching_files if f.endswith(('.jpg', '.png'))]
                
        print(f"  Archivos encontrados: MP4({len(mp4_files)}) JSON({len(json_files)}) IMG({len(img_files)})")
                
        # Si encontramos al menos uno de cada tipo, mover
        if mp4_files and json_files and img_files:
            try:
                files_to_move = [mp4_files[0], json_files[0], img_files[0]]
                for file in files_to_move:
                    shutil.move(video_folder / file, uploadable_folder / file)
                                
                # Cambiar status a "letsgo"
                video['status'] = 'letsgo'
                                
                print(f"  ✅ MOVIDOS: {len(files_to_move)} archivos -> STATUS: letsgo")
                moved += 1
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print(f"  ❌ Archivos incompletos")
        
    # Guardar cambios en data.json
    if moved > 0:
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(all_videos, f, ensure_ascii=False, indent=2)
        print(f"el data.json actualizado")
        
    print(f"\nTotal videos movidos: {moved}")

if __name__ == "__main__":
    main()