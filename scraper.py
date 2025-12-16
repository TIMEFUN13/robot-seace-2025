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
    print("Iniciando Robot 8.0 (ID Francotirador)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        url_seace = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
        driver.get(url_seace)
        print("Entrando al SEACE...")
        time.sleep(5) 
        
        # 1. CAMBIAR DE PESTAÑA
        print("Buscando pestaña 'Buscador de Procedimientos'...")
        try:
            pestana = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos"))
            )
            pestana.click()
            print("✅ ¡Clic en la pestaña correcta! Esperando carga...")
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Error cambiando pestaña: {e}")

        # 2. SELECCIONAR AÑO 2025
        print("Aplicando Rayos X para listas...")
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            if "2025" in s.get_attribute("textContent"):
                try:
                    Select(s).select_by_visible_text("2025")
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", s)
                    print("Año 2025 seleccionado.")
                    break
                except:
                    continue
        
        time.sleep(3)

        # 3. CLICK EN BUSCAR (CON EL ID QUE ENCONTRASTE)
        print("Buscando botón con ID exacto...")
        
        # ID DESCUBIERTO EN TU FOTO: tbBuscador:idFormBuscarProceso:btnBuscarSel
        id_francotirador = "tbBuscador:idFormBuscarProceso:btnBuscarSel"
        
        try:
            # Opción A: Clic directo por ID
            btn = driver.find_element(By.ID, id_francotirador)
            driver.execute_script("arguments[0].click();", btn)
            print(f"✅ ¡CLIC CONFIRMADO en ID: {id_francotirador}!")
        except:
            print("⚠️ Falla por ID exacto. Probando por clase CSS específica...")
            # Opción B: Por la clase única que también sale en tu foto
            try:
                btn = driver.find_element(By.CSS_SELECTOR, ".btnBuscar_buscadorProcesos")
                driver.execute_script("arguments[0].click();", btn)
                print("✅ ¡CLIC CONFIRMADO por Clase CSS!")
            except Exception as e:
                 print(f"❌ Error crítico al buscar botón: {e}")

        print("Esperando 15 segundos resultados...")
        time.sleep(15)

        # 4. VERIFICAR RESULTADOS
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if filas:
            print(f"✅ ¡ÉXITO! Encontré {len(filas)} procesos.")
            fila = filas[0]
            texto = fila.text.replace("\n", " ")
            
            # PDF y Telegram
            with open("exito.pdf", "w") as f: f.write(texto)
            enviar_telegram("exito.pdf", f"¡VICTORIA! {len(filas)} procesos encontrados.")
            
            # Google Sheet
            payload = {"desc": texto[:150], "entidad": "SEACE 8.0", "pdf": "Telegram", "analisis": "Tabla Encontrada"}
            requests.post(WEBHOOK_URL, json=payload)
            
        else:
            print("❌ Tabla vacía. Tomando foto...")
            driver.save_screenshot("error_final.png")
            enviar_telegram("error_final.png", "FOTO: Botón presionado, pero sin datos.")
            print("Foto enviada.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        driver.save_screenshot("crash.png")
        enviar_telegram("crash.png", f"Crash: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
