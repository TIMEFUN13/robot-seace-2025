import os
import time
import glob
import datetime
import requests
import subprocess
import pdfplumber
import pypdf
import google.generativeai as genai
from docx import Document
from pdf2image import convert_from_path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
WEBHOOK_URL = os.environ['GOOGLE_WEBHOOK']
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
MODO_SOLO_HOY = False 

genai.configure(api_key=GEMINI_API_KEY)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def enviar_telegram_foto(ruta_foto, caption):
    """Envía capturas de pantalla para depuración"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(ruta_foto, 'rb') as f:
            data = {'chat_id': CHAT_ID, 'caption': caption}
            files = {'photo': f}
            requests.post(url, data=data, files=files)
    except: pass

def enviar_telegram_archivo(ruta_archivo, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        with open(ruta_archivo, 'rb') as f:
            data = {'chat_id': CHAT_ID, 'caption': caption[:1000]}
            files = {'document': f}
            requests.post(url, data=data, files=files)
            return True
    except: return False

def forzar_click(driver, elemento):
    driver.execute_script("arguments[0].click();", elemento)

def resaltar_elemento(driver, elemento):
    """Pone un borde rojo al elemento para ver cuál eligió"""
    driver.execute_script("arguments[0].style.border='3px solid red';", elemento)

def obtener_texto_seguro(elemento):
    try:
        txt = elemento.get_attribute("textContent")
        if not txt: txt = elemento.text
        return txt.strip()
    except: return ""

def es_fecha_hoy(fecha_texto):
    try:
        hoy = datetime.datetime.now().strftime("%d/%m/%Y")
        return fecha_texto[:10] == hoy
    except: return True

def extraer_texto_word(ruta_archivo):
    texto = ""
    try:
        if ruta_archivo.lower().endswith('.docx'):
            doc = Document(ruta_archivo)
            for para in doc.paragraphs: texto += para.text + "\n"
        elif ruta_archivo.lower().endswith('.doc'):
            result = subprocess.run(['antiword', ruta_archivo], capture_output=True, text=True)
            texto = result.stdout
    except: pass
    return texto

def analizar_con_ia_gemini(ruta_archivo):
    print("      🧠 Consultando a Gemini...")
    ext = ruta_archivo.lower().split('.')[-1]
    texto_completo = ""
    es_imagen = False
    
    if ext in ['doc', 'docx']:
        texto_completo = extraer_texto_word(ruta_archivo)
    elif ext == 'pdf':
        try:
            with pdfplumber.open(ruta_archivo) as pdf:
                for p in pdf.pages[:15]:
                    t = p.extract_text()
                    if t: texto_completo += t + "\n"
        except: pass
        if len(texto_completo) < 100: es_imagen = True
    
    modelos = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']
    
    prompt = """
    Rol: Ingeniero de Licitaciones.
    Tarea: Extraer Personal Clave del TDR.
    Formato:
    👷 **[CARGO]**: [Profesión]
    🕒 [Experiencia]
    Si no hay, resume el OBJETO.
    """
    
    for nombre_modelo in modelos:
        try:
            model = genai.GenerativeModel(nombre_modelo)
            if es_imagen and ext == 'pdf':
                try:
                    imgs = convert_from_path(ruta_archivo, first_page=1, last_page=5)
                    response = model.generate_content([prompt] + imgs)
                    return response.text.strip()
                except: pass
            else:
                if len(texto_completo) < 20: return "Archivo vacío"
                response = model.generate_content(f"{prompt}\n\nDOC:\n{texto_completo[:30000]}")
                return response.text.strip()
        except: continue
            
    return "Error IA: Conexión fallida."

def recuperar_pagina(driver, pagina_objetivo):
    """
    Intenta recuperar la tabla si desapareció.
    """
    try:
        # FOTO DE DIAGNÓSTICO AL VOLVER
        driver.save_screenshot("regreso.png")
        enviar_telegram_foto("regreso.png", f"📸 Diagnóstico: Así se ve la pantalla al intentar ir al proceso {pagina_objetivo}")
        
        # Si no hay filas, pulsamos Buscar de nuevo
        if not driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]"):
            print("⚠️ Tabla vacía al volver. Refrescando...")
            try: driver.execute_script("document.getElementById('tbBuscador:idFormBuscarProceso:btnBuscarSel').click();")
            except: driver.execute_script("document.querySelector('.btnBuscar_buscadorProcesos').click();")
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            
        return True
    except: return False

def main():
    print("Iniciando Robot 43.0 (DETECTIVE)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    prefs = {"download.default_directory": DOWNLOAD_DIR, "download.prompt_for_download": False, "plugins.always_open_pdf_externally": True}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        try: driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
        except: pass
        time.sleep(5)

        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            if "2025" in obtener_texto_seguro(s):
                driver.execute_script("arguments[0].value = '2025'; arguments[0].dispatchEvent(new Event('change'));", s)
                break
        time.sleep(5)

        print("Buscando...")
        try: driver.execute_script("document.getElementById('tbBuscador:idFormBuscarProceso:btnBuscarSel').click();")
        except: driver.execute_script("document.querySelector('.btnBuscar_buscadorProcesos').click();")
        
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
        pag = 1
        
        while True:
            print(f"--- ⛏️ PÁGINA {pag} ---")
            time.sleep(3)
            filas_iniciales = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            if not filas_iniciales: break
            num_filas = len(filas_iniciales)

            for i in range(num_filas):
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
                    filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
                    if i >= len(filas): break
                    row = filas[i]
                    cols = row.find_elements(By.TAG_NAME, "td")
                    
                    nom = obtener_texto_seguro(cols[3])
                    entidad = obtener_texto_seguro(cols[1])
                    if not entidad: time.sleep(1); entidad = obtener_texto_seguro(cols[1])
                    fecha = obtener_texto_seguro(cols[2])
                    obj = obtener_texto_seguro(cols[5])
                    desc = obtener_texto_seguro(cols[6])
                    
                    if MODO_SOLO_HOY and not es_fecha_hoy(fecha): continue
                    
                    # --- DETECCIÓN VISUAL DE BOTONES ---
                    celda_acciones = cols[-1]
                    botones = celda_acciones.find_elements(By.TAG_NAME, "a")
                    btn_objetivo = None
                    
                    # Lógica: Buscar el que NO sea historial
                    for btn in botones:
                        try:
                            # Buscamos si tiene imagen dentro
                            imgs = btn.find_elements(By.TAG_NAME, "img")
                            if imgs:
                                src = imgs[0].get_attribute("src")
                                if "Historial" not in src: # Si NO es historial, es la ficha
                                    btn_objetivo = btn
                                    break
                        except: pass
                    
                    # Si falló la lógica inteligente, usar posición (el último suele ser la ficha)
                    if not btn_objetivo and len(botones) > 0:
                        btn_objetivo = botones[-1]

                    if btn_objetivo:
                        # 📸 FOTO EVIDENCIA ANTES DE CLICK
                        resaltar_elemento(driver, btn_objetivo)
                        driver.save_screenshot("objetivo.png")
                        enviar_telegram_foto("objetivo.png", f"🎯 Voy a hacer clic aquí para: {nom[:20]}")
                        
                        forzar_click(driver, btn_objetivo)
                        time.sleep(6)
                        
                        # --- PROCESO DE DESCARGA ---
                        pdf_st = "Sin Archivo"; analisis = "Sin Doc"
                        snip="-"; cui="-" # Simplificado para debug
                        
                        try:
                            # Limpieza
                            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")): 
                                try: os.remove(f)
                                except: pass
                            
                            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID,"tbFicha:dtDocumentos_data")))
                            
                            filas_docs = driver.find_elements(By.CSS_SELECTOR, "#tbFicha\\:dtDocumentos_data tr")
                            mejor_link = None
                            mejor_prio = 0
                            
                            for fd in filas_docs:
                                try:
                                    enlaces = fd.find_elements(By.CSS_SELECTOR, "a[onclick*='descargaDocGeneral']")
                                    if not enlaces: continue
                                    lnk = enlaces[0]
                                    txt = obtener_texto_seguro(fd).upper()
                                    
                                    prio = 0
                                    if "BASES" in txt: prio = 4
                                    elif "TDR" in txt or "TERMINOS" in txt: prio = 3
                                    elif fd.find_elements(By.CSS_SELECTOR, "img[src*='pdf']"): prio = 2
                                    elif fd.find_elements(By.CSS_SELECTOR, "img[src*='word']"): prio = 1
                                    
                                    if prio >= mejor_prio:
                                        mejor_prio = prio
                                        mejor_link = lnk
                                except: pass
                            
                            if mejor_link:
                                print(f"⬇️ Descargando...")
                                forzar_click(driver, mejor_link)
                                f_path = None
                                for _ in range(30):
                                    time.sleep(1)
                                    fs = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
                                    validos = [f for f in fs if not f.endswith('.crdownload') and os.path.getsize(f) > 0]
                                    if validos: f_path = validos[0]; break
                                
                                if f_path:
                                    enviar_telegram_archivo(f_path, f"📄 {nom}")
                                    pdf_st = "En Telegram ✅"
                                    analisis = analizar_con_ia_gemini(f_path)
                                    print(f"🧠 IA: {analisis[:20]}...")
                                else: print("❌ Timeout")
                            else: print("⚠️ Sin docs")

                        except Exception as e: print(f"ErrDocs: {e}")

                        # Enviar a Sheets
                        crono = "Ver Ficha" # Simplificado
                        rep = f"OBJETO: {obj}\n\n{crono}\n--- 🧠 ANÁLISIS IA ---\n{analisis}"
                        payload = {"fecha_real": fecha, "desc": f"{nom}\n{desc}", "entidad": entidad, "pdf": pdf_st, "analisis": rep, "snip": snip, "cui": cui}
                        requests.post(WEBHOOK_URL, json=payload)
                        
                        # --- RETROCESO ---
                        try: 
                            b = driver.find_element(By.XPATH, "//button[contains(text(),'Regresar')]")
                            forzar_click(driver, b)
                        except: driver.execute_script("window.history.back();")
                        
                        # DIAGNÓSTICO VISUAL DEL REGRESO
                        recuperar_pagina(driver, i+2) # Pasamos índice solo como referencia
                        
                    else:
                        print("⚠️ No encontré botón ficha.")
                    
                except Exception as e: 
                    print(f"⚠️ Error fila: {e}")
                    driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
                    time.sleep(5)
                    continue

            print(f"✅ Pág {pag} terminada.")
            try:
                pb = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
                nxt = pb.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
                if "ui-state-disabled" in nxt.get_attribute("class"): break
                forzar_click(driver, nxt)
                time.sleep(10)
                pag += 1
                if pag>100: break
            except: break

    except Exception as e: print(f"❌ CRASH FINAL: {e}")
    finally: driver.quit()

if __name__ == "__main__":
    main()
