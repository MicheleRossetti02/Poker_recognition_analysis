#!/usr/bin/env python3
"""
Script per convertire labels YOLO da formato poligono a bounding box
Converte le righe con >5 valori (poligoni) nel formato standard detection (5 valori)
"""

import os
import sys
from pathlib import Path

def polygon_to_bbox(coords):
    """
    Converte coordinate poligono in bounding box YOLO format
    coords: lista di coordinate [x1, y1, x2, y2, x3, y3, ...]
    Returns: (x_center, y_center, width, height) normalized
    """
    # Estrai tutte le x e y
    x_coords = [float(coords[i]) for i in range(0, len(coords), 2)]
    y_coords = [float(coords[i]) for i in range(1, len(coords), 2)]
    
    # Trova min e max
    x_min = min(x_coords)
    x_max = max(x_coords)
    y_min = min(y_coords)
    y_max = max(y_coords)
    
    # Calcola centro e dimensioni (già normalized 0-1)
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2
    width = x_max - x_min
    height = y_max - y_min
    
    return x_center, y_center, width, height

def convert_label_file(file_path):
    """
    Converte un file label da formato misto a solo detection
    Returns: numero di righe convertite
    """
    converted_count = 0
    new_lines = []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        parts = line.strip().split()
        
        if len(parts) < 2:
            # Riga vuota o invalida, salta
            continue
        
        if len(parts) == 5:
            # Formato detection già corretto
            new_lines.append(line)
        elif len(parts) > 5:
            # Formato poligono, converti
            class_id = parts[0]
            coords = parts[1:]
            
            # Converti poligono in bbox
            x_c, y_c, w, h = polygon_to_bbox(coords)
            
            # Crea nuova riga in formato YOLO detection
            new_line = f"{class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}\n"
            new_lines.append(new_line)
            converted_count += 1
        else:
            # Formato invalido, mantieni comunque
            new_lines.append(line)
    
    # Sovrascrivi file
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    return converted_count

def main():
    print("=" * 70)
    print("🔧 CONVERSIONE LABELS: Poligoni → Bounding Box")
    print("=" * 70)
    
    # Directories da processare
    dirs_to_process = ['train/labels', 'valid/labels', 'test/labels']
    
    total_files = 0
    total_converted = 0
    
    for dir_path in dirs_to_process:
        if not os.path.exists(dir_path):
            print(f"\n⚠️  Cartella {dir_path} non trovata, skip")
            continue
        
        print(f"\n📁 Processando {dir_path}...")
        
        label_files = list(Path(dir_path).glob('*.txt'))
        files_with_conversions = 0
        conversions_in_dir = 0
        
        for label_file in label_files:
            converted = convert_label_file(label_file)
            if converted > 0:
                files_with_conversions += 1
                conversions_in_dir += converted
        
        print(f"   ✅ File processati: {len(label_files)}")
        print(f"   🔄 File con conversioni: {files_with_conversions}")
        print(f"   📊 Righe convertite: {conversions_in_dir}")
        
        total_files += len(label_files)
        total_converted += conversions_in_dir
    
    print("\n" + "=" * 70)
    print("✅ CONVERSIONE COMPLETATA!")
    print("=" * 70)
    print(f"\n📊 Riepilogo:")
    print(f"   Total file processati: {total_files}")
    print(f"   Total righe convertite: {total_converted}")
    print(f"\n✅ Dataset ora in formato detection uniforme!")
    print("=" * 70)

if __name__ == "__main__":
    main()
