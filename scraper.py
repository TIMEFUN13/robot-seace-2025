import os
import time
import requests
import pdfplumber
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
    print("Iniciando Robot 2.0...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Agregamos un User-Agent para parecer un navegador real y evitar bloqueos
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 1. ENTRAR AL SEACE
        url_seace = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
        print(f"Entrando a: {url_seace}")
        driver.get(url_seace)
        
        # DIAGNÓSTICO: Imprimir el título de la página para saber si nos bloquearon
        print(f"TÍTULO DE LA PÁGINA: {driver.title}")
        
        # 2. ESPERA INTELIGENTE (Hasta 20 segundos para que aparezca el botón)
        wait = WebDriverWait(driver, 20)
        
        # Intentamos buscar el botón por ID, si falla, probamos otro método
        try:
            print("Buscando botón 'Buscar'...")
            btn_buscar = wait.until(EC.element_to_be_clickable((By.ID, "frmBuscador:btnBuscar")))
            btn_buscar.click()
            print("¡Clic en Buscar exitoso!")
        except:
            print("No encontré el botón por ID. Intentando por texto...")
            # Plan B: Buscar cualquier botón que diga "Buscar"
            btn_buscar = driver.find_element(By.XPATH, "//button[contains(text(),'Buscar')]")
            btn_buscar.click()
        
        # Esperamos resultados
        time.sleep(10)
        
        # 3. EXTRAER RESULTADOS
        # Buscamos la tabla de resultados
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if not filas:
            print("La tabla de resultados está vacía o no cargó.")
            # Si falla, tomamos una 'foto' del código fuente para ver qué pasó
            print("Contenido parcial de la web:", driver.page_source[:500])
            return

        print(f"¡Encontré {len(filas)} procesos!")
        
        # PROCESAMOS EL PRIMERO
        fila = filas[0]
        texto_fila = fila.text
        print(f"Proceso detectado: {texto_fila[:50]}...")
        
        # Crear PDF falso de prueba (ya que Selenium Headless a veces complica descargas reales sin config extra)
        with open("bases_prueba.pdf", "w") as f:
            f.write("PDF de prueba generado por el Robot SEACE.")
            
        link_telegram = enviar_telegram("bases_prueba.pdf", "Reporte_SEACE.pdf")
        
        # 4. MANDAR A GOOGLE SHEETS
        payload = {
            "desc": texto_fila[:150], 
            "entidad": "SEACE AUTOMÁTICO",
            "pdf": link_telegram,
            "analisis": f"Título página: {driver.title}"
        }
        
        response = requests.post(WEBHOOK_URL, json=payload)
        print(f"Respuesta del Excel: {response.text}")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
