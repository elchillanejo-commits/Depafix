#!/usr/bin/env python3
import os
import cv2
import numpy as np

def procesar_firmas():
    imagen_path = input("Ruta de la foto del libro de firmas (ej: libro.jpg): ").strip()
    if not os.path.exists(imagen_path):
        print("❌ El archivo no existe.")
        return
    img = cv2.imread(imagen_path)
    output_dir = "./firmas_recortadas"
    os.makedirs(output_dir, exist_ok=True)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 15)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dilated = cv2.dilate(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"🔍 Se detectaron {len(contours)} posibles bloques.")
    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 40 or h < 20 or w > img.shape[1] * 0.8: continue
        roi_img = img[y:y+h, x:x+w]
        _, mask = cv2.threshold(cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY), 200, 255, cv2.THRESH_BINARY_INV)
        mask = cv2.GaussianBlur(mask, (3, 3), 0)
        b, g, r = cv2.split(roi_img)
        rgba = cv2.merge([b, g, r, mask])
        nombre_alumno = input(f"👤 Nombre para firma {i+1} (o ENTER para saltar): ").strip()
        if not nombre_alumno: continue
        filename = "".join([c for c in nombre_alumno.replace(" ", "_") if c.isalnum() or c == "_"]) + ".png"
        dest_path = os.path.join(output_dir, filename)
        cv2.imwrite(dest_path, rgba)
        print(f"💾 Guardada: {dest_path}")
    print("\n✅ Extracción finalizada.")
if __name__ == "__main__":
    procesar_firmas()
