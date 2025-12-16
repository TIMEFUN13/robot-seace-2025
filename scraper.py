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
    print("Iniciando Robot 5.0 (Modo 'Rayos X')...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # User Agent es vital para que no nos detecten como robot
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        url_seace = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
        driver.get(url_seace)
        print("Entrando al SEACE...")
        time.sleep(8) # Damos buen tiempo para cargar scripts
        
        # TRUCO MAESTRO: Hacer visibles los selectores ocultos de PrimeFaces
        print("Aplicando Rayos X para ver listas ocultas...")
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        time.sleep(1)

        # 1. SELECCIONAR AÑO 2025
        selects = driver.find_elements(By.TAG_NAME, "select")
        anio_seleccionado = False
        
        print(f"Encontré {len(selects)} listas desplegables. Buscando el año...")
        
        for s in selects:
            # Usamos 'textContent' porque 'text' a veces falla en elementos ocultos
            texto_interno = s.get_attribute("textContent")
            if "2025" in texto_interno and "2024" in texto_interno:
                print("¡Lista de Años ENCONTRADA!")
                
                # Método 1: Selección directa Selenium
                try:
                    selector = Select(s)
                    selector.select_by_visible_text("2025")
                    print("Intento 1: Año seleccionado vía Selenium.")
                    anio_seleccionado = True
                except:
                    print("Intento 1 falló. Probando fuerza bruta JavaScript...")
                    
                # Método 2: Fuerza bruta (Si el 1 falla o para asegurar)
                if not anio_seleccionado:
                    driver.execute_script("arguments[0].value = '2025'; arguments[0].dispatchEvent(new Event('change'));", s)
                    print("Intento 2: Año forzado vía JavaScript.")
                    anio_seleccionado = True
                break
        
        if not anio_seleccionado:
            print("⚠️ ALERTA: No pude seleccionar el año. La búsqueda podría fallar.")
        
        time.sleep(2)

        # 2. CLICK EN BUSCAR
        print("Buscando botón 'Buscar'...")
        # Buscamos botones o inputs que digan "Buscar"
        botones = driver.find_elements(By.XPATH, "//button[contains(text(),'Buscar')] | //input[contains(@value,'Buscar')]")
        
        if botones:
            print("Botón encontrado. Hiciendo clic...")
            driver.execute_script("arguments[0].click();", botones[0])
            print("Clic enviado. Esperando 15 segundos a que cargue la tabla...")
            time.sleep(15) 
        else:
            print("No encontré botón por texto. Probando ID 'frmBuscador:btnBuscar'...")
            try:
                btn = driver.find_element(By.ID, "frmBuscador:btnBuscar")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(15)
            except:
                print("❌ No pude dar clic en Buscar.")

        # 3. EXTRAER RESULTADOS
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if not filas:
            print("❌ La tabla sigue vacía.")
            print("HTML parcial:", driver.page_source[:500])
            return

        print(f"✅ ¡ÉXITO TOTAL! Encontré {len(filas)} procesos.")
        
        # PROCESAMOS EL PRIMERO
        fila = filas[0]
        texto_fila = fila.text.replace("\n", " ") # Limpiamos saltos de linea
        print(f"Proceso: {texto_fila[:100]}...")
        
        # SIMULACIÓN DE PDF
        with open("reporte_seace.pdf", "w") as f:
            f.write(f"Reporte generado. Proceso encontrado: {texto_fila}")
        
        link = enviar_telegram("reporte_seace.pdf", "Alerta_SEACE.pdf")
        
        payload = {
            "desc": texto_fila, 
            "entidad": "SEACE (GitHub)",
            "pdf": link,
            "analisis": f"Procesos hoy: {len(filas)}"
        }
        requests.post(WEBHOOK_URL, json=payload)
        print("Datos enviados a Google Sheets.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
