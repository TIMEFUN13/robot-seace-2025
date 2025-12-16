import os
import time
import requests
import pdfplumber
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# --- CONFIGURACIÓN ---
WEBHOOK_URL = os.environ['GOOGLE_WEBHOOK']
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

def enviar_telegram(ruta_pdf, nombre_archivo):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        with open(ruta_pdf, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': CHAT_ID, 'caption': f"📄 Bases: {nombre_archivo}"}
            requests.post(url, files=files, data=data)
            return "Ver en Telegram"
    except Exception as e:
        print(f"Error Telegram: {e}")
        return "Error al subir"

def main():
    print("Iniciando Robot 4.0 (Selector de Año)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        url_seace = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
        driver.get(url_seace)
        print("Entrando al SEACE...")
        time.sleep(5) 
        
        # 1. SELECCIONAR AÑO 2025
        # Buscamos todos los selectores (dropdowns)
        selects = driver.find_elements(By.TAG_NAME, "select")
        anio_encontrado = False
        
        for s in selects:
            # Tratamos de encontrar el que tenga opciones de años
            try:
                texto_opciones = s.text
                if "2025" in texto_opciones and "2024" in texto_opciones:
                    print("¡Selector de Año encontrado!")
                    selector = Select(s)
                    selector.select_by_visible_text("2025")
                    print("Año 2025 seleccionado.")
                    anio_encontrado = True
                    break
            except:
                continue
                
        if not anio_encontrado:
            print("⚠️ No encontré el selector de año, intentaré buscar directo.")

        time.sleep(2)

        # 2. CLICK EN BUSCAR
        # Usamos una búsqueda por texto parcial que es infalible
        print("Buscando botón...")
        botones = driver.find_elements(By.TAG_NAME, "button")
        btn_final = None
        
        for b in botones:
            if "Buscar" in b.text:
                btn_final = b
                break
        
        if btn_final:
            driver.execute_script("arguments[0].click();", btn_final)
            print("Clic en Buscar enviado. Esperando 15 segundos...")
            time.sleep(15) # El SEACE es lento cargando la tabla
        else:
            print("No encontré botón Buscar, probando método alternativo...")
            # Intento desesperado: buscar por ID común
            driver.execute_script("document.getElementById('frmBuscador:btnBuscar').click();")
            time.sleep(15)

        # 3. EXTRAER RESULTADOS
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if not filas:
            print("❌ La tabla sigue vacía. Imprimiendo HTML para depurar...")
            # Esto imprimirá el código de la página en los logs para que yo pueda verlo
            print(driver.page_source[:1000])
            return

        print(f"✅ ¡ÉXITO TOTAL! Encontré {len(filas)} procesos.")
        
        # PROCESAMOS EL PRIMERO
        fila = filas[0]
        texto_fila = fila.text
        print(f"Proceso: {texto_fila[:100]}...")
        
        # SIMULACIÓN DE PDF (Para verificar flujo completo)
        with open("bases_exito.pdf", "w") as f:
            f.write("Este PDF confirma que el Robot 4.0 encontró la tabla.")
        
        link = enviar_telegram("bases_exito.pdf", "Licitacion_Encontrada.pdf")
        
        payload = {
            "desc": texto_fila[:150], 
            "entidad": "GOBIERNO PERUANO (SEACE)",
            "pdf": link,
            "analisis": "Datos extraídos de tabla real"
        }
        requests.post(WEBHOOK_URL, json=payload)
        print("Datos enviados a Google Sheets.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
