import json
import os
import shutil
import argparse
from collections import Counter

def setup_scene_files_and_targets(dataset_root, dataset_name, split, scene_id_int, sensor_suffix, output_targets_filename):
    """
    Prepara los archivos JSON estándar para una escena BOP (copiando/renombrando
    desde archivos específicos del sensor si es necesario) y genera un archivo de targets
    para esa escena.
    """
    scene_id_str_padded = f"{scene_id_int:06d}"
    scene_path = os.path.join(dataset_root, dataset_name, split, scene_id_str_padded)

    if not os.path.isdir(scene_path):
        print(f"Error: La ruta de la escena no existe: {scene_path}")
        return

    print(f"--- Procesando escena: {scene_path} ---")
    if sensor_suffix:
        print(f"Usando sensor_suffix: '{sensor_suffix}' para los archivos fuente.")
    else:
        print("No se especificó sensor_suffix, se asumirán nombres de archivo estándar como fuente.")

    standard_files_to_prepare = {
        "camera": "scene_camera.json",
        "gt": "scene_gt.json",
        "gt_info": "scene_gt_info.json"
    }
    
    gt_file_successfully_prepared = False

    for key, std_name in standard_files_to_prepare.items():
        src_name_with_suffix = f"scene_{key}_{sensor_suffix}.json"
        
        # Determinar el nombre del archivo fuente real
        actual_src_name = std_name if not sensor_suffix else src_name_with_suffix
        actual_src_path = os.path.join(scene_path, actual_src_name)
        
        dst_path = os.path.join(scene_path, std_name)

        if not os.path.exists(actual_src_path):
            if sensor_suffix: # Solo es un problema si se esperaba un archivo con sufijo
                print(f"Advertencia: El archivo fuente '{actual_src_name}' no se encontró en {scene_path}.")
            elif not os.path.exists(dst_path): # Si no hay sufijo y el estándar tampoco existe
                 print(f"Advertencia: El archivo estándar '{std_name}' no se encontró en {scene_path}.")

            if key == "gt" and not os.path.exists(dst_path): # El archivo GT es esencial
                print(f"Error: El archivo GT ('{actual_src_name}' o '{std_name}') es necesario y no se encontró.")
                return # No se puede continuar sin el GT
            continue 

        if actual_src_path != dst_path:
            try:
                print(f"Copiando '{actual_src_name}' a '{std_name}'...")
                shutil.copy2(actual_src_path, dst_path)
                if key == "gt":
                    gt_file_successfully_prepared = True
            except Exception as e:
                print(f"Error al copiar '{actual_src_name}' a '{dst_path}': {e}")
                if key == "gt": return # No continuar si falla la copia del GT
        else:
            print(f"El archivo '{std_name}' ya tiene el nombre estándar y existe.")
            if key == "gt":
                gt_file_successfully_prepared = True
    
    # Verificar si el archivo GT estándar está disponible para generar targets
    final_gt_file_for_targets = os.path.join(scene_path, standard_files_to_prepare["gt"])
    if not os.path.exists(final_gt_file_for_targets):
        if not gt_file_successfully_prepared: # Si no se preparó ni existía antes
             print(f"Error: El archivo '{standard_files_to_prepare['gt']}' no está disponible en {scene_path} después del intento de preparación. No se pueden generar targets.")
             return


    # --- Generar archivo de targets ---
    print(f"\n--- Generando targets desde: {final_gt_file_for_targets} ---")
    
    try:
        with open(final_gt_file_for_targets, 'r') as f:
            scene_gt_data = json.load(f)
    except Exception as e:
        print(f"Error al cargar {final_gt_file_for_targets}: {e}")
        return

    targets = []
    if not isinstance(scene_gt_data, dict):
        print(f"Error: El contenido de {final_gt_file_for_targets} no es un diccionario como se esperaba.")
        return

    for im_id_str, gt_annotations in scene_gt_data.items():
        try:
            im_id_int = int(im_id_str)
        except ValueError:
            print(f"Advertencia: im_id '{im_id_str}' en {final_gt_file_for_targets} no es un entero. Saltando esta imagen para targets.")
            continue

        if not isinstance(gt_annotations, list):
            print(f"Advertencia: Las anotaciones para im_id '{im_id_str}' no son una lista. Saltando. Contenido: {gt_annotations}")
            continue
            
        obj_counts_in_image = Counter()
        for ann in gt_annotations:
            if isinstance(ann, dict) and "obj_id" in ann:
                obj_counts_in_image[ann["obj_id"]] += 1
            else:
                print(f"Advertencia: Anotación inválida o sin 'obj_id' en im_id {im_id_str}. Anotación: {ann}")

        for obj_id, count in obj_counts_in_image.items():
            targets.append({
                "scene_id": scene_id_int,
                "im_id": im_id_int,
                "obj_id": obj_id,
                "inst_count": count 
            })
            
    if not targets:
        print("Advertencia: No se generaron targets. ¿Está el archivo scene_gt.json vacío o sus anotaciones no tienen 'obj_id'?")
    
    dataset_base_path = os.path.join(dataset_root, dataset_name)
    output_targets_path = os.path.join(dataset_base_path, output_targets_filename)
    
    try:
        os.makedirs(os.path.dirname(output_targets_path), exist_ok=True)
        with open(output_targets_path, 'w') as f:
            json.dump(targets, f, indent=2)
        print(f"Archivo de targets guardado en: {output_targets_path}")
        print(f"Total de entradas de target generadas: {len(targets)}")
    except Exception as e:
        print(f"Error al guardar el archivo de targets en {output_targets_path}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepara archivos JSON de escena BOP y genera un archivo de targets.")
    parser.add_argument("--dataset_root", required=True, help="Ruta a la carpeta raíz de datasets BOP (ej. /home/cuevas/imagenes/bop_toolkit/datasets).")
    parser.add_argument("--dataset_name", required=True, help="Nombre del dataset (ej. ipd).")
    parser.add_argument("--split", required=True, help="Split del dataset (ej. test, val).")
    parser.add_argument("--scene_id", required=True, type=int, help="ID de la escena (ej. 4).")
    parser.add_argument("--sensor_suffix", default="", help="Sufijo del sensor para los archivos originales (ej. photoneo, cam1). Dejar vacío si los archivos ya tienen nombres estándar (scene_gt.json, etc.).")
    parser.add_argument("--output_targets_filename", default="targets_custom.json", help="Nombre para el archivo de targets generado (ej. targets_scene4.json). Se guardará en la raíz del dataset especificado.")

    args = parser.parse_args()

    setup_scene_files_and_targets(
        args.dataset_root,
        args.dataset_name,
        args.split,
        args.scene_id,
        args.sensor_suffix,
        args.output_targets_filename
    )