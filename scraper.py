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
    print("Iniciando Robot 7.0 (Corrección de Pestaña)...")
    
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
        
        # --- PASO NUEVO: CAMBIAR DE PESTAÑA ---
        print("Buscando pestaña 'Buscador de Procedimientos'...")
        try:
            # Buscamos el enlace que contiene el texto de la pestaña correcta
            pestana = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos"))
            )
            pestana.click()
            print("✅ ¡Clic en la pestaña correcta! Esperando carga...")
            time.sleep(5) # Esperamos a que cambie la vista
        except Exception as e:
            print(f"⚠️ Error cambiando pestaña: {e}. Intentando forzar con JS...")
            driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();") # ID probable
            time.sleep(5)

        # 1. SELECCIONAR AÑO 2025 (Ahora en la pestaña correcta)
        print("Aplicando Rayos X para listas...")
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        
        selects = driver.find_elements(By.TAG_NAME, "select")
        anio_ok = False
        
        for s in selects:
            # Ahora que estamos en la pestaña correcta, el selector visible debería ser el bueno
            if "2025" in s.get_attribute("textContent"):
                try:
                    Select(s).select_by_visible_text("2025")
                    # Forzamos el evento change
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", s)
                    print("Año 2025 seleccionado.")
                    anio_ok = True
                    break
                except:
                    continue
        
        time.sleep(3)

        # 2. CLICK EN BUSCAR
        print("Buscando botón 'Buscar'...")
        # Al cambiar de pestaña, el botón correcto debería ser visible ahora
        botones = driver.find_elements(By.XPATH, "//button[contains(text(),'Buscar')]")
        
        if botones:
            # A veces hay 2 botones buscar (uno por pestaña), pulsamos el visible
            for b in botones:
                if b.is_displayed():
                    b.click()
                    print("Clic en botón Buscar VISIBLE.")
                    break
            else:
                # Si ninguno reporta ser visible (por headless), pulsamos el último (suele ser el de la der)
                driver.execute_script("arguments[0].click();", botones[-1])
                print("Clic forzado en el último botón Buscar encontrado.")
        else:
            print("Probando botón por ID...")
            try:
                driver.find_element(By.ID, "frmBuscador:btnBuscar").click()
                print("Clic por ID exitoso.")
            except:
                print("❌ No encontré botón Buscar.")

        print("Esperando resultados (15s)...")
        time.sleep(15)

        # 3. VERIFICAR RESULTADOS
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if filas:
            print(f"✅ ¡ÉXITO! Encontré {len(filas)} procesos.")
            fila = filas[0]
            texto = fila.text.replace("\n", " ")
            
            # PDF y Telegram
            with open("exito.pdf", "w") as f: f.write(texto)
            enviar_telegram("exito.pdf", "¡Búsqueda Exitosa! (Pestaña Correcta)")
            
            # Google Sheet
            payload = {"desc": texto[:150], "entidad": "SEACE 7.0", "pdf": "Telegram", "analisis": f"Total: {len(filas)}"}
            requests.post(WEBHOOK_URL, json=payload)
            
        else:
            print("❌ Tabla vacía. Tomando foto de diagnóstico...")
            driver.save_screenshot("error_tab.png")
            enviar_telegram("error_tab.png", "FOTO: ¿Cambiamos de pestaña?")
            print("Foto enviada a Telegram.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        driver.save_screenshot("crash.png")
        enviar_telegram("crash.png", f"Crash: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
