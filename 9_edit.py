import json
import os
import subprocess
import requests
from pathlib import Path
from datetime import datetime

def send_notification(message):
    """Envía notificación a Telegram"""
    try:
        bot_token = "7869024150:AAGFO6ZvpO4-5J4karX_lef252tkD3BhclE"
        chat_id = "6166225652"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, {"chat_id": chat_id, "text": message}, timeout=5)
    except Exception as e:
        print(f"Error enviando notificación: {e}")

def clean_name(name):
    """Limpia el nombre para comparacion"""
    # Quitar todo despues del primer parentesis
    if '(' in name:
        name = name.split('(')[0]
    
    # Limpiar caracteres especiales (incluyendo barras verticales y acentos)
    name = name.replace('¿', '').replace('?', '').replace('¡', '').replace('!', '')
    name = name.replace(':', '').replace(';', '').replace(',', '').replace('.', '')
    name = name.replace('|', '').replace('/', '').replace('\\', '')  # Agregar barras
    name = name.replace(' ', '').replace('_', '').replace('-', '')
    
    # Remover acentos comunes
    name = name.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    name = name.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    name = name.replace('ü', 'u')
    
    return name.lower().strip()

def get_video_duration(video_path):
    """Obtiene la duracion del video en segundos"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error obteniendo duracion de {video_path}: {e}")
        return None

def get_video_resolution(video_path):
    """Obtiene la resolución del video"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0', str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
        width, height = result.stdout.strip().split(',')
        return int(width), int(height)
    except Exception as e:
        print(f"Error obteniendo resolución de {video_path}: {e}")
        return None, None

def edit_video(input_path, complement_path, output_path, cut_seconds=13):
    """Edita el video: quita los ultimos segundos y agrega el complemento"""
    try:
        # Obtener duracion del video original
        duration = get_video_duration(input_path)
        if duration is None:
            return False
        
        # Calcular tiempo de corte
        cut_time = duration - cut_seconds
        if cut_time <= 0:
            print(f"El video {input_path} es muy corto para cortar {cut_seconds} segundos")
            return False
        
        print(f"Procesando: {input_path.name}")
        print(f"Duración original: {duration:.2f}s -> Cortando a: {cut_time:.2f}s")
        
        # Obtener resolución del video original
        orig_width, orig_height = get_video_resolution(input_path)
        comp_width, comp_height = get_video_resolution(complement_path)
        
        if orig_width is None or comp_width is None:
            print("Error obteniendo resoluciones")
            return False
            
        print(f"Video original: {orig_width}x{orig_height}")
        print(f"Complemento: {comp_width}x{comp_height}")
        
        # Determinar resolución target (usar la del video original)
        target_width, target_height = orig_width, orig_height
        print(f"Resolución target: {target_width}x{target_height}")
        
        # Crear archivos temporales
        temp_cut = input_path.parent / f"temp_cut_{os.getpid()}_{input_path.name}"
        temp_complement = input_path.parent / f"temp_complement_{os.getpid()}.mp4"
        
        # PASO 1: Cortar el video original (mantener resolución original)
        cut_cmd = [
            'ffmpeg', '-i', str(input_path),
            '-t', str(cut_time),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-r', '30',
            '-ar', '48000',
            '-ac', '2',
            '-y', str(temp_cut)
        ]
        
        print("Paso 1: Cortando video...")
        result = subprocess.run(cut_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if result.returncode != 0:
            print(f"Error cortando video: {result.stderr}")
            return False
        
        # PASO 2: Re-encodear y ESCALAR el complemento para que coincida con la resolución original
        complement_cmd = [
            'ffmpeg', '-i', str(complement_path),
            '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-r', '30',
            '-ar', '48000',
            '-ac', '2',
            '-y', str(temp_complement)
        ]
        
        print("Paso 2: Re-encodeando y escalando complemento...")
        result = subprocess.run(complement_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if result.returncode != 0:
            print(f"Error re-encodeando complemento: {result.stderr}")
            # Limpiar archivos temporales
            if temp_cut.exists():
                temp_cut.unlink()
            return False
        
        # PASO 3: Concatenar usando filtro concat (mejor sincronización)
        concat_cmd = [
            'ffmpeg', 
            '-i', str(temp_cut),
            '-i', str(temp_complement),
            '-filter_complex', '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]',
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-r', '30',
            '-ar', '48000',
            '-ac', '2',
            '-y', str(output_path)
        ]
        
        print("Paso 3: Concatenando videos con filtro concat...")
        result = subprocess.run(concat_cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        # Limpiar archivos temporales
        cleanup_files = [temp_cut, temp_complement]
        for temp_file in cleanup_files:
            if temp_file.exists():
                temp_file.unlink()
        
        if result.returncode != 0:
            print(f"Error concatenando videos: {result.stderr}")
            return False
        
        print(f"✅ Video editado exitosamente: {output_path.name}")
        return True
        
    except Exception as e:
        print(f"❌ Error editando video {input_path}: {e}")
        return False

def update_video_status(video_data, video_title, new_status):
    """Actualiza el estado de un video específico en data.json"""
    try:
        for video in video_data:
            if video['title'] == video_title:
                video['status'] = new_status
                break
        
        # Guardar cambios
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(video_data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error actualizando estado del video: {e}")
        return False

def main():
    # Verificar que existe ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, encoding='utf-8', errors='ignore')
        print("✅ FFmpeg encontrado")
    except FileNotFoundError:
        print("❌ Error: ffmpeg no esta instalado o no esta en el PATH")
        return
    
    # Cargar data.json
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            all_videos = json.load(f)
        print("✅ data.json cargado")
    except FileNotFoundError:
        print("❌ Error: No se encontro data.json")
        return
    
    # Filtrar videos que cumplan las condiciones
    videos_to_edit = [v for v in all_videos 
                      if v.get('status') == 'letsgo' 
                      and v.get('channel') == 'Netflix Latinoamérica']
    
    print(f"📹 Videos a editar: {len(videos_to_edit)}")
    
    if not videos_to_edit:
        print("ℹ️  No hay videos para editar")
        return
    
    # Verificar carpetas y archivos
    uploadable_folder = Path('uploadable')
    complement_path = Path('complement.mp4')
    
    if not uploadable_folder.exists():
        print("❌ Error: No existe la carpeta 'uploadable'")
        return
    
    if not complement_path.exists():
        print("❌ Error: No existe el archivo 'complement.mp4'")
        return
    
    print("✅ Carpeta 'uploadable' y 'complement.mp4' encontrados")
    
    # Obtener archivos MP4 en uploadable
    mp4_files = list(uploadable_folder.glob('*.mp4'))
    print(f"📁 Archivos MP4 en uploadable: {len(mp4_files)}")
    
    edited_count = 0
    edited_videos = []  # Lista para almacenar los títulos de videos editados
    
    for i, video in enumerate(videos_to_edit, 1):
        title = video['title']
        title_clean = clean_name(title)
        
        print(f"\n{'='*60}")
        print(f"📹 Procesando video {i}/{len(videos_to_edit)}")
        print(f"Título: {title}")
        print(f"Título limpio: {title_clean}")
        
        # Buscar archivo MP4 que coincida
        matching_file = None
        for mp4_file in mp4_files:
            file_clean = clean_name(mp4_file.stem)
            print(f"  Comparando: {mp4_file.name} -> {file_clean}")  # Debug
            
            # Estrategia 1: coincidencia exacta o contención
            if title_clean in file_clean or file_clean in title_clean:
                matching_file = mp4_file
                print(f"    ✓ Coincidencia por contención")
                break
            # Estrategia 2: primeras 10 letras coinciden
            elif len(title_clean) >= 10 and len(file_clean) >= 10:
                if title_clean[:10] == file_clean[:10]:
                    matching_file = mp4_file
                    print(f"    ✓ Coincidencia por primeras 10 letras")
                    break
            # Estrategia 3: coincidencia de 80% de caracteres
            elif len(title_clean) >= 8 and len(file_clean) >= 8:
                shorter = min(len(title_clean), len(file_clean))
                matches = sum(1 for a, b in zip(title_clean, file_clean) if a == b)
                if matches / shorter >= 0.8:
                    matching_file = mp4_file
                    print(f"    ✓ Coincidencia por 80% similaridad")
                    break
        
        if not matching_file:
            print("❌ No se encontró archivo MP4 correspondiente")
            continue
        
        print(f"✅ Archivo encontrado: {matching_file.name}")
        
        # Crear archivo de salida temporal
        temp_output = uploadable_folder / f"temp_edited_{os.getpid()}_{matching_file.name}"
        
        # Editar video
        if edit_video(matching_file, complement_path, temp_output):
            # Reemplazar archivo original con el editado
            try:
                original_size = matching_file.stat().st_size
                new_size = temp_output.stat().st_size
                
                matching_file.unlink()  # Eliminar original
                temp_output.rename(matching_file)  # Renombrar temporal
                
                print(f"✅ Video reemplazado: {matching_file.name}")
                print(f"📊 Tamaño: {original_size/1024/1024:.1f}MB -> {new_size/1024/1024:.1f}MB")
                
                # Actualizar estado del video a 'edited'
                if update_video_status(all_videos, title, 'edited'):
                    print(f"✅ Estado actualizado: {title} -> edited")
                    edited_videos.append(title)
                    edited_count += 1
                else:
                    print(f"❌ Error actualizando estado de: {title}")
                
            except Exception as e:
                print(f"❌ Error reemplazando archivo: {e}")
                if temp_output.exists():
                    temp_output.unlink()
        else:
            print("❌ Error editando el video")
            if temp_output.exists():
                temp_output.unlink()
    
    print(f"\n{'='*60}")
    print(f"🎉 Total videos editados: {edited_count}/{len(videos_to_edit)}")
    print("✅ Proceso completado")
    
    # Enviar notificación por Telegram si se editaron videos
    if edited_count > 0:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🎬 Videos editados: {edited_count}\n⏰ {timestamp}\n\n"
        
        # Agregar lista de videos editados (limitando a 10 para evitar mensajes muy largos)
        if len(edited_videos) <= 10:
            message += "Videos procesados:\n"
            for i, video_title in enumerate(edited_videos, 1):
                # Truncar título si es muy largo
                short_title = video_title[:50] + "..." if len(video_title) > 50 else video_title
                message += f"{i}. {short_title}\n"
        else:
            message += f"Videos procesados: {len(edited_videos)} (lista muy larga)\n"
        
        message += f"\n✅ Estado cambiado de 'letsgo' a 'edited'"
        
        send_notification(message)
        print(f"📱 Notificación enviada por Telegram")

if __name__ == "__main__":
    main()
