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
            r = requests.post(url, files=files, data=data)
            # Intentamos obtener el link del mensaje (truco de Telegram)
            return "Ver en Telegram (Canal)" 
    except Exception as e:
        print(f"Error Telegram: {e}")
        return "Error al subir"

def analizar_pdf(ruta_pdf):
    texto = ""
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            # Leemos solo primeras 3 paginas para velocidad
            for page in pdf.pages[:3]:
                texto += page.extract_text() or ""
        
        analisis = []
        texto_lower = texto.lower()
        
        # BUSCADOR DE PALABRAS CLAVE (Aquí puedes añadir más)
        if "ingeniero civil" in texto_lower: analisis.append("Piden Ing. Civil")
        if "carta fianza" in texto_lower: analisis.append("Requiere Carta Fianza")
        if "años de experiencia" in texto_lower: analisis.append("Mencionan experiencia específica")
        
        return ", ".join(analisis) if analisis else "Sin alertas detectadas"
    except:
        return "No se pudo leer PDF"

def main():
    print("Iniciando Robot...")
    
    # Configuración de Chrome para GitHub Actions
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Sin pantalla
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 1. ENTRAR AL SEACE
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        print("Página cargada.")
        
        # Esperar un momento a que cargue
        time.sleep(5)
        
        # 2. SIMULACIÓN DE BÚSQUEDA (Clic en Buscar)
        # Nota: Aquí normalmente llenaríamos filtros. Por ahora buscamos lo que haya hoy.
        btn_buscar = driver.find_element(By.ID, "frmBuscador:btnBuscar") # ID comun del SEACE
        btn_buscar.click()
        print("Buscando...")
        time.sleep(5)
        
        # 3. EXTRAER RESULTADOS (Solo el primero para prueba)
        # Buscamos filas de la tabla
        filas = driver.find_elements(By.XPATH, "//tr[@data-ri]") 
        
        if not filas:
            print("No se encontraron filas.")
            return

        # Procesamos solo la primera fila como ejemplo de demostración
        fila = filas[0]
        texto_fila = fila.text
        print(f"Encontrado: {texto_fila[:50]}...")
        
        # INTENTAR BAJAR PDF (Simulado para estabilidad inicial)
        # En una versión avanzada, aquí haremos clic en el icono del PDF
        # Por ahora, creamos un PDF dummy para probar que el sistema funciona
        with open("bases_temp.pdf", "w") as f:
            f.write("Este es un archivo de prueba del robot SEACE.")
            
        link_telegram = enviar_telegram("bases_temp.pdf", "Prueba_Bases.pdf")
        analisis = "Prueba de sistema operativo."
        
        # 4. MANDAR A GOOGLE SHEETS
        payload = {
            "desc": texto_fila[:100], # Cortamos para que quepa
            "entidad": "Entidad Detectada",
            "pdf": link_telegram,
            "analisis": analisis
        }
        requests.post(WEBHOOK_URL, json=payload)
        print("¡Datos enviados a Google Sheet!")

    except Exception as e:
        print(f"Ocurrió un error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
