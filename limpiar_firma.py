#!/usr/bin/env python3
import sys, os
from PIL import Image
import numpy as np

def limpiar_firma(entrada, salida=None):
    img = Image.open(entrada).convert("RGBA")
    arr = np.array(img)
    # Si el pixel es claro (fondo papel), hacerlo transparente
    r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
    mascara = (r > 200) & (g > 200) & (b > 200)
    arr[mascara] = [255, 255, 255, 0]
    Image.fromarray(arr).save(salida or entrada)
    print(f"✅ Firma limpia: {salida or entrada}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 limpiar_firma.py firma.jpg [firma_limpia.png]")
        sys.exit(1)
    limpiar_firma(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
