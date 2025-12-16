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
    print("Iniciando Robot 3.0 (Modo Diagnóstico)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # User Agent para simular ser humano real
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    # Hacemos la ventana grande para asegurar que se vean los botones
    driver.set_window_size(1920, 1080)
    
    try:
        url_seace = "https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
        print(f"Entrando a: {url_seace}")
        driver.get(url_seace)
        time.sleep(5) # Espera simple para carga inicial
        
        print(f"TÍTULO: {driver.title}")
        
        # --- DIAGNÓSTICO DE BOTONES ---
        print("--- Buscando botones visibles ---")
        botones = driver.find_elements(By.TAG_NAME, "button")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        links = driver.find_elements(By.TAG_NAME, "a")
        
        candidato_buscar = None
        
        # Buscamos en INPUTS (SEACE suele usar inputs para botones)
        for i in inputs:
            val = i.get_attribute("value") or ""
            id_txt = i.get_attribute("id") or ""
            # Si encontramos algo que diga "Buscar" o tenga ID 'btnBuscar'
            if "Buscar" in val or "btnBuscar" in id_txt:
                print(f"¡CANDIDATO ENCONTRADO! Tag: Input | ID: {id_txt} | Value: {val}")
                candidato_buscar = i
                break
        
        # Si no, buscamos en BUTTONS
        if not candidato_buscar:
            for b in botones:
                txt = b.text
                id_txt = b.get_attribute("id") or ""
                if "Buscar" in txt or "btnBuscar" in id_txt:
                    print(f"¡CANDIDATO ENCONTRADO! Tag: Button | ID: {id_txt} | Text: {txt}")
                    candidato_buscar = b
                    break

        if candidato_buscar:
            print("Intentando hacer clic en el candidato...")
            # Usamos Javascript para forzar el clic (más efectivo en SEACE)
            driver.execute_script("arguments[0].click();", candidato_buscar)
            print("Clic enviado. Esperando resultados...")
            time.sleep(10)
        else:
            print("❌ NO ENCONTRÉ EL BOTÓN. Imprimiendo estructura de la página...")
            print(driver.page_source[:2000]) # Imprime el código HTML para ver qué pasa
            return

        # 3. EXTRAER RESULTADOS
        filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]") 
        
        if not filas:
            print("La tabla de resultados sigue vacía. Puede que necesitemos filtrar por año.")
            return

        print(f"¡ÉXITO! Encontré {len(filas)} procesos.")
        
        # PROCESAMOS EL PRIMERO
        fila = filas[0]
        texto_fila = fila.text
        print(f"Proceso: {texto_fila[:50]}...")
        
        # Simulamos PDF y envio
        with open("bases_prueba.pdf", "w") as f:
            f.write("PDF generado por Robot 3.0")
        
        link = enviar_telegram("bases_prueba.pdf", "Resultado_Exitoso.pdf")
        
        payload = {
            "desc": texto_fila[:150], 
            "entidad": "Robot 3.0",
            "pdf": link,
            "analisis": "Conexión exitosa al SEACE"
        }
        requests.post(WEBHOOK_URL, json=payload)
        print("Datos enviados a Google Sheets.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
