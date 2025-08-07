import json

def limpiar_shorts(data_file="data.json"):
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error leyendo el archivo: {e}")
        return

    originales = len(data)

    # Filtramos: nos quedamos solo con los que NO tienen "short" en el ID
    data_filtrada = [video for video in data if "short" not in video["video_id"].lower()]

    eliminados = originales - len(data_filtrada)

    try:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data_filtrada, f, indent=2, ensure_ascii=False)
        print(f"✅ Limpieza completada. Se eliminaron {eliminados} videos tipo short.")
    except Exception as e:
        print(f"Error guardando el archivo: {e}")

if __name__ == "__main__":
    limpiar_shorts()
