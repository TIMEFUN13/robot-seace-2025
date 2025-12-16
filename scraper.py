import os
import time
import glob
import datetime
import requests
import pdfplumber
import google.generativeai as genai # El cerebro de Google
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
GEMINI_API_KEY = os.environ['GEMINI_API_KEY'] # Tu nueva llave
MODO_SOLO_HOY = False 

# Configurar el cerebro
genai.configure(api_key=GEMINI_API_KEY)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def enviar_telegram_archivo(ruta_archivo, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        with open(ruta_archivo, 'rb') as f:
            data = {'chat_id': CHAT_ID, 'caption': caption[:1000]} # Telegram tiene limite de texto
            files = {'document': f}
            requests.post(url, data=data, files=files)
            return True
    except: return False

def forzar_click(driver, elemento):
    driver.execute_script("arguments[0].click();", elemento)

def es_fecha_hoy(fecha_texto):
    try:
        hoy = datetime.datetime.now().strftime("%d/%m/%Y")
        return fecha_texto[:10] == hoy
    except: return True

def analizar_con_ia_gemini(ruta_pdf):
    """
    Lee el PDF y le pide a Google Gemini un resumen técnico.
    """
    print("      🧠 Consultando al Ingeniero IA (Gemini)...")
    texto_completo = ""
    
    # 1. Extraer texto del PDF (Primeras 15 páginas para no saturar)
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            paginas = pdf.pages[:15] 
            for p in paginas:
                texto_pag = p.extract_text()
                if texto_pag: texto_completo += texto_pag + "\n"
    except Exception as e:
        return f"Error leyendo PDF: {e}"

    if len(texto_completo) < 50:
        return "PDF ilegible o escaneado (Imagen)."

    # 2. Enviar a Gemini
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Actúa como un Ingeniero de Licitaciones experto. Analiza el siguiente texto extraído de unas Bases del SEACE (Términos de Referencia).
        
        Tu misión es extraer SOLO los Requisitos de Calificación del Personal Clave.
        Ignora temas legales, garantías o penalidades. Céntrate en el PERFIL.

        TEXTO:
        {texto_completo[:30000]} 

        Responde con este formato EXACTO y conciso (máximo 4 líneas):
        - [PUESTO]: [Profesión requerida]
        - [EXPERIENCIA]: [Tiempo en años/meses y tipo de obras]
        - [OTRO]: [Maestría, Diplomado o requisito especial si lo hay]
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error IA: {e}"

def extraer_dato_popup(driver, boton_lupa, tipo):
    try:
        forzar_click(driver, boton_lupa)
        time.sleep(2)
        dialogos = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        texto = "No encontrado"
        for d in dialogos:
            if d.is_displayed():
                texto = d.text.replace("\n", " | ")
                try:
                    cerrar = d.find_element(By.CSS_SELECTOR, "a.ui-dialog-titlebar-close")
                    forzar_click(driver, cerrar)
                except: webdriver.ActionChains(driver).send_keys(u'\ue00c').perform()
                break
        limpio = texto.replace("Código SNIP", "").replace("Código Unico de Inversion", "").replace("Cerrar", "").strip()
        return limpio[:50] if len(limpio) > 1 else "Sin Dato"
    except: return "Error"

def recuperar_pagina(driver, pagina_objetivo):
    try:
        paginador = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
        txt = paginador.find_element(By.CSS_SELECTOR, ".ui-paginator-current").text
        import re
        match = re.search(r'Página:\s*(\d+)', txt)
        pag_actual = int(match.group(1)) if match else 1
        if pag_actual < pagina_objetivo:
            next_btn = paginador.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
            for _ in range(pagina_objetivo - pag_actual):
                forzar_click(driver, next_btn)
                time.sleep(2.5)
            return True
    except: pass
    return False

def main():
    print("Iniciando Robot 27.0 (INGENIERO IA)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        
        # Pestaña y Año (Simplificado)
        try:
            pestana = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos")))
            forzar_click(driver, pestana)
        except: driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
        time.sleep(5)

        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            if "2025" in s.get_attribute("textContent"):
                try: Select(s).select_by_visible_text("2025"); driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", s); break
                except: continue
        time.sleep(5)

        # Buscar
        try: driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:btnBuscarSel").click()
        except: 
            btns = driver.find_elements(By.CSS_SELECTOR, ".btnBuscar_buscadorProcesos")
            if btns: btns[0].click()
        time.sleep(20)

        pagina_actual = 1
        procesos_totales = 0
        
        while True:
            print(f"--- ⛏️ ANALIZANDO PÁGINA {pagina_actual} ---")
            try: WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            except: break

            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            num_filas = len(filas)
            
            for i in range(num_filas):
                try:
                    filas_refresh = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
                    if i >= len(filas_refresh): break
                    fila = filas_refresh[i]
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    entidad = celdas[1].text
                    fecha_pub = celdas[2].text
                    nomenclatura = celdas[3].text
                    objeto = celdas[5].text
                    desc_corta = celdas[6].text
                    
                    if MODO_SOLO_HOY and not es_fecha_hoy(fecha_pub): continue

                    # SNIP/CUI
                    snip = ""; cui = ""
                    try:
                        l = fila.find_element(By.CSS_SELECTOR, "[id$=':graCodSnip']")
                        if l.is_displayed(): snip = extraer_dato_popup(driver, l, "SNIP")
                    except: pass
                    try:
                        l = fila.find_element(By.CSS_SELECTOR, "[id$=':graCodCUI']")
                        if l.is_displayed(): cui = extraer_dato_popup(driver, l, "CUI")
                    except: pass
                    
                    # FICHA
                    try:
                        btn_ficha = fila.find_element(By.CSS_SELECTOR, "[id$=':grafichaSel']")
                        forzar_click(driver, btn_ficha)
                        time.sleep(6)
                        
                        pdf_status = "No PDF"
                        analisis_ia = "Sin Análisis"
                        
                        # DESCARGA Y ANALISIS
                        try:
                            # Limpiar
                            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")): os.remove(f)
                            
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "tbFicha:dtDocumentos_data")))
                            filas_docs = driver.find_elements(By.CSS_SELECTOR, "#tbFicha\\:dtDocumentos_data tr")
                            
                            for fd in filas_docs:
                                try:
                                    link = fd.find_element(By.CSS_SELECTOR, "a")
                                    nombre = link.text
                                    
                                    if "Bases" in nombre or ".pdf" in nombre:
                                        print(f"⬇️ Bajando: {nombre}...")
                                        forzar_click(driver, link)
                                        
                                        archivo_descargado = None
                                        for _ in range(20): # Esperar
                                            time.sleep(1)
                                            archivos = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
                                            if archivos and not archivos[0].endswith('.crdownload'):
                                                archivo_descargado = archivos[0]
                                                break
                                        
                                        if archivo_descargado:
                                            # 1. Telegram
                                            enviar_telegram_archivo(archivo_descargado, f"📄 {nombre}\n{nomenclatura}")
                                            pdf_status = "En Telegram ✅"
                                            
                                            # 2. IA GEMINI
                                            analisis_ia = analizar_con_ia_gemini(archivo_descargado)
                                            print(f"🧠 IA Dice: {analisis_ia[:50]}...")
                                            break
                                except: pass
                        except Exception as e: print(f"Error PDF: {e}")

                        # CRONOGRAMA
                        crono_txt = ""
                        try:
                            t = driver.find_element(By.ID, "tbFicha:dtCronograma_data")
                            for r in t.find_elements(By.TAG_NAME, "tr"):
                                txt = r.text
                                if "Propuestas" in txt or "Buena Pro" in txt:
                                    c = r.find_elements(By.TAG_NAME, "td")
                                    if len(c)>=2: crono_txt += f"📅 {c[0].text}: {c[1].text}\n"
                        except: pass

                        # GUARDAR
                        # Aquí combinamos el Cronograma + El Análisis de la IA
                        reporte = f"OBJETO: {objeto}\n\n{crono_txt}\n--- 🧠 ANÁLISIS IA ---\n{analisis_ia}"

                        payload = {
                            "fecha_real": fecha_pub,
                            "desc": f"{nomenclatura}\n{desc_corta}",
                            "entidad": entidad,
                            "pdf": pdf_status,
                            "analisis": reporte,
                            "snip": snip,
                            "cui": cui
                        }
                        
                        requests.post(WEBHOOK_URL, json=payload)
                        procesos_totales += 1
                        
                        # Volver
                        try: 
                            b = driver.find_element(By.XPATH, "//button[contains(text(),'Regresar')]")
                            forzar_click(driver, b)
                        except: driver.execute_script("window.history.back();")
                        
                        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
                        recuperar_pagina(driver, pagina_actual)

                    except: 
                        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
                        time.sleep(5)
                        continue
                        
                except: continue

            print(f"✅ Pág {pagina_actual} Ok.")
            try:
                pag_bottom = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
                next_btn = pag_bottom.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
                if "ui-state-disabled" in next_btn.get_attribute("class"): break
                forzar_click(driver, next_btn)
                time.sleep(10)
                pagina_actual += 1
                if pagina_actual > 100: break
            except: break

    except Exception as e: print(f"❌ CRASH: {e}")
    finally: driver.quit()

if __name__ == "__main__":
    main()
