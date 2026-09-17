from playwright.sync_api import sync_playwright
import time
import csv
import json

def scrap_libros_sandbox():
    todos_los_libros = []
    pagina_actual = 1
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        while True:
            if pagina_actual == 1:
                url = "https://books.toscrape.com/"
            else:
                url = f"https://books.toscrape.com/catalogue/page-{pagina_actual}.html"
                
            print(f"Scrapeando página {pagina_actual}: {url}")
            page.goto(url)
            
            try:
                page.wait_for_selector(".product_pod", timeout=5000)
            except:
                print("No hay más páginas o tiempo de espera agotado.")
                break
                
            libros_pagina = page.evaluate("""() => {
                const productos = document.querySelectorAll('.product_pod');
                return Array.from(productos).map(libro => {
                    const titulo = libro.querySelector('h3 a').getAttribute('title');
                    const precio = libro.querySelector('.price_color').innerText;
                    const stock = libro.querySelector('.instock.availability') !== null;
                    const ratingClasses = libro.querySelector('.star-rating').className;
                    const rating = ratingClasses.split(' ')[1];
                    return { titulo, precio, stock, rating };
                });
            }""")
            
            if not libros_pagina:
                break
                
            todos_los_libros.extend(libros_pagina)
            pagina_actual += 1
            time.sleep(0.5)
            
        browser.close()
    
    guardar_csv(todos_los_libros)
    guardar_json(todos_los_libros)
    print(f"¡Proceso finalizado! Total de registros extraídos: {len(todos_los_libros)}")

def guardar_csv(libros, archivo="libros.csv"):
    with open(archivo, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["titulo", "precio", "stock", "rating"])
        writer.writeheader()
        writer.writerows(libros)
    print(f"Datos exportados exitosamente a {archivo}")

def guardar_json(libros, archivo="libros.json"):
    with open(archivo, mode="w", encoding="utf-8") as f:
        json.dump(libros, f, ensure_ascii=False, indent=2)
    print(f"Datos exportados exitosamente a {archivo}")

if __name__ == "__main__":
    scrap_libros_sandbox()
