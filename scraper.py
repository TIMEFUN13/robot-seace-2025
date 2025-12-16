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

def enviar_telegram(ruta_archivo, mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        with open(ruta_archivo, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': CHAT_ID, 'caption': mensaje}
            requests.post(url, files=files, data=data)
            return "Enviado a Telegram"
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")
        return "Error"

def main():
    print("Iniciando Robot 6.0 (Modo Fotógrafo)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # User Agent para parecer PC real
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1366, 768) # Tamaño de pantalla normal de laptop
    
    try:
        url_seace = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
        driver.get(url_seace)
        print("Entrando al SEACE...")
        time.sleep(8) 
        
        # 1. SELECCIONAR AÑO (Lógica Reforzada)
        print("Buscando selector de año...")
        # Hacemos visible el select oculto
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        
        selects = driver.find_elements(By.TAG_NAME, "select")
        anio_ok = False
        
        for s in selects:
            if "2025" in s.get_attribute("textContent"):
                try:
                    Select(s).select_by_visible_text("2025")
                    # REFUERZO: Disparar evento de cambio manualmente para que la página reaccione
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", s)
                    print("Año 2025 seleccionado y evento 'change' disparado.")
                    anio_ok = True
                    break
                except:
                    continue
        
        if not anio_ok:
            print("⚠️ No pude seleccionar el año.")
        
        time.sleep(3) # Esperar a que la página procese el cambio de año

        # 2. CLICK EN BUSCAR
        print("Buscando botón 'Buscar'...")
        # Intento directo por ID (el más común en SEACE)
        try:
            btn = driver.find_element(By.ID, "frmBuscador:btnBuscar")
            driver.execute_script("arguments[0].click();", btn)
            print("Clic enviado al botón ID: frmBuscador:btnBuscar")
        except:
            # Plan B: Buscar por texto
            print("Botón por ID no encontrado, buscando por texto...")
            botones = driver.find_elements(By.XPATH, "//button[contains(text(),'Buscar')]")
            if botones:
                driver.execute_script("arguments[0].click();", botones[0])
                print("Clic enviado al botón por Texto.")
            else:
                print("❌ NO ENCONTRÉ EL BOTÓN BUSCAR.")

        print("Esperando 15 segundos resultados...")
        time.sleep(15)

        # 3. VERIFICAR RESULTADOS O TOMAR FOTO
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if filas:
            print(f"✅ ¡ÉXITO! Encontré {len(filas)} procesos.")
            fila = filas[0]
            texto = fila.text.replace("\n", " ")
            
            # Crear PDF prueba
            with open("reporte.pdf", "w") as f: f.write(texto)
            enviar_telegram("reporte.pdf", "¡Búsqueda Exitosa!")
            
            # Guardar en Sheets
            payload = {"desc": texto[:100], "entidad": "SEACE", "pdf": "Telegram", "analisis": "OK"}
            requests.post(WEBHOOK_URL, json=payload)
            
        else:
            print("❌ La tabla sigue vacía. ¡TOMANDO FOTO DEL ERROR!")
            
            # TOMA LA FOTO
            driver.save_screenshot("error_pantalla.png")
            print("Foto tomada. Enviando a Telegram...")
            
            # ENVÍA LA FOTO A TU TELEGRAM
            enviar_telegram("error_pantalla.png", "⚠️ FOTO DEL ERROR: Mira qué pasó")
            
            # Imprime mensaje en log
            print("Revisa tu Telegram, ahí está la respuesta visual.")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        driver.save_screenshot("error_crash.png")
        enviar_telegram("error_crash.png", f"Error Crash: {str(e)}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
