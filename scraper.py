import os
import time
import glob
import datetime
import requests
import pdfplumber
import pypdf
import google.generativeai as genai
from pdf2image import convert_from_path # Nueva librería para convertir PDF a Imagen
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
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
MODO_SOLO_HOY = False 

genai.configure(api_key=GEMINI_API_KEY)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

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

def limpiar_texto_snip(texto_sucio):
    try:
        if "Sin información" in texto_sucio: return "-"
        import re
        numeros = re.findall(r'\d{6,8}', texto_sucio)
        if numeros: return " / ".join(numeros)
        return texto_sucio[:20]
    except: return texto_sucio

def analizar_con_ia_gemini(ruta_pdf):
    print("      🧠 Consultando a Gemini...")
    texto_completo = ""
    es_imagen = False
    
    # INTENTO 1: Extracción de Texto Normal
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for p in pdf.pages[:15]:
                t = p.extract_text()
                if t: texto_completo += t + "\n"
    except: pass

    # Si hay muy poco texto, asumimos que es ESCANEADO (IMAGEN)
    if len(texto_completo) < 100:
        print("      ⚠️ Texto no detectado. Activando MODO VISIÓN (OCR)...")
        es_imagen = True

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt_texto = """
        Eres un Ingeniero de Licitaciones. Analiza este documento técnico (TDR).
        Extrae los REQUISITOS DEL PERSONAL CLAVE.
        Responde EXACTAMENTE con este formato:
        👷 **[CARGO]**: [Profesión/Título]
        🕒 [Experiencia Específica]
        🎓 [Otros requisitos]
        Si no hay personal, resume el OBJETO DEL SERVICIO.
        """

        if es_imagen:
            # --- MODO VISIÓN: Enviamos IMÁGENES a Gemini ---
            # Convertimos las primeras 6 páginas a imágenes (para no saturar memoria)
            imagenes = convert_from_path(ruta_pdf, first_page=1, last_page=6)
            
            # Enviamos el prompt + las imágenes
            contenido = [prompt_texto] + imagenes
            response = model.generate_content(contenido)
        else:
            # --- MODO TEXTO: Enviamos el STRING extraído ---
            response = model.generate_content(f"{prompt_texto}\n\nTEXTO DEL PDF:\n{texto_completo[:30000]}")
            
        return response.text.strip()

    except Exception as e:
        print(f"Error IA: {e}")
        return "Error IA o PDF muy complejo"

def extraer_dato_popup(driver, boton_lupa, tipo):
    try:
        forzar_click(driver, boton_lupa)
        time.sleep(2)
        dialogos = driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
        texto = "No encontrado"
        for d in dialogos:
            if d.is_displayed():
                texto = obtener_texto_seguro(d).replace("\n", " | ")
                try:
                    c = d.find_element(By.CSS_SELECTOR, "a.ui-dialog-titlebar-close")
                    forzar_click(driver, c)
                except: webdriver.ActionChains(driver).send_keys(u'\ue00c').perform()
                break
        limpio = texto.replace("Código SNIP", "").replace("Código Unico de Inversion", "").replace("Cerrar", "").strip()
        return limpiar_texto_snip(limpio)
    except: return "Error"

def recuperar_pagina(driver, pagina_objetivo):
    try:
        p = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
        txt = obtener_texto_seguro(p.find_element(By.CSS_SELECTOR, ".ui-paginator-current"))
        import re
        m = re.search(r'Página:\s*(\d+)', txt)
        act = int(m.group(1)) if m else 1
        if act < pagina_objetivo:
            nxt = p.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
            for _ in range(pagina_objetivo - act):
                forzar_click(driver, nxt)
                time.sleep(2)
            return True
    except: pass
    return False

def main():
    print("Iniciando Robot 36.0 (MODO VISIÓN)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    prefs = {"download.default_directory": DOWNLOAD_DIR, "download.prompt_for_download": False, "plugins.always_open_pdf_externally": True}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # NAVEGACION
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        try: driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
        except: pass
        time.sleep(5)

        # AÑO 2025
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            if "2025" in obtener_texto_seguro(s):
                driver.execute_script("arguments[0].value = '2025'; arguments[0].dispatchEvent(new Event('change'));", s)
                break
        time.sleep(5)

        # BUSCAR
        print("Buscando...")
        try: driver.execute_script("document.getElementById('tbBuscador:idFormBuscarProceso:btnBuscarSel').click();")
        except: driver.execute_script("document.querySelector('.btnBuscar_buscadorProcesos').click();")
        
        print("Esperando tabla (60s)...")
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
        
        pag = 1
        
        while True:
            print(f"--- ⛏️ PÁGINA {pag} ---")
            time.sleep(3)
            
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            if not filas: break

            for i in range(len(filas)):
                try:
                    filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
                    if i >= len(filas): break
                    row = filas[i]
                    cols = row.find_elements(By.TAG_NAME, "td")
                    
                    entidad = obtener_texto_seguro(cols[1])
                    fecha = obtener_texto_seguro(cols[2])
                    nom = obtener_texto_seguro(cols[3])
                    obj = obtener_texto_seguro(cols[5])
                    desc = obtener_texto_seguro(cols[6])
                    
                    if not entidad:
                        time.sleep(1)
                        entidad = obtener_texto_seguro(cols[1])

                    if MODO_SOLO_HOY and not es_fecha_hoy(fecha): continue

                    snip="-"; cui="-"
                    try:
                        l=row.find_element(By.CSS_SELECTOR, "[id$=':graCodSnip']")
                        if l.is_displayed(): snip=extraer_dato_popup(driver,l,"SNIP")
                    except: pass
                    try:
                        l=row.find_element(By.CSS_SELECTOR, "[id$=':graCodCUI']")
                        if l.is_displayed(): cui=extraer_dato_popup(driver,l,"CUI")
                    except: pass
                    
                    # FICHA
                    try:
                        btn_ficha = row.find_element(By.CSS_SELECTOR, "[id$=':grafichaSel']")
                        forzar_click(driver, btn_ficha)
                        time.sleep(5)
                        
                        pdf_st = "Sin Archivo"
                        analisis = "Sin PDF"
                        
                        try:
                            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")): os.remove(f)
                            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID,"tbFicha:dtDocumentos_data")))
                            
                            enlaces_descarga = driver.find_elements(By.CSS_SELECTOR, "a[onclick*='descargaDocGeneral']")
                            target_link = None
                            
                            for lnk in enlaces_descarga:
                                try:
                                    fila_padre = lnk.find_element(By.XPATH, "./../..")
                                    texto_fila = obtener_texto_seguro(fila_padre).upper()
                                    if "BASES" in texto_fila or "ADMINISTRATIVAS" in texto_fila:
                                        target_link = lnk; break
                                except: pass
                            
                            if not target_link and enlaces_descarga: target_link = enlaces_descarga[0]

                            if target_link:
                                print(f"⬇️ Descargando...")
                                forzar_click(driver, target_link)
                                f_path = None
                                for _ in range(25):
                                    time.sleep(1)
                                    fs = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
                                    if fs and not fs[0].endswith('.crdownload'): f_path = fs[0]; break
                                
                                if f_path:
                                    enviar_telegram_archivo(f_path, f"📄 {nom}")
                                    pdf_st = "En Telegram ✅"
                                    # ANÁLISIS IA (Multimodal)
                                    analisis = analizar_con_ia_gemini(f_path)
                                    print(f"🧠 IA Responde: {analisis[:30]}...")
                                else: print("❌ Timeout archivo")
                            else: print("⚠️ Sin enlace")

                        except Exception as e: print(f"ErrDocs: {e}")

                        crono = ""
                        try:
                            t = driver.find_element(By.ID, "tbFicha:dtCronograma_data")
                            for r in t.find_elements(By.TAG_NAME, "tr"):
                                txt = obtener_texto_seguro(r)
                                if "Propuestas" in txt or "Buena Pro" in txt:
                                    cc = r.find_elements(By.TAG_NAME, "td")
                                    if len(cc)>=2: crono += f"📅 {obtener_texto_seguro(cc[0])}: {obtener_texto_seguro(cc[1])}\n"
                        except: pass

                        rep = f"OBJETO: {obj}\n\n{crono}\n--- 🧠 ANÁLISIS IA ---\n{analisis}"
                        
                        payload = {
                            "fecha_real": fecha, "desc": f"{nom}\n{desc}", "entidad": entidad,
                            "pdf": pdf_st, "analisis": rep, "snip": snip, "cui": cui
                        }
                        requests.post(WEBHOOK_URL, json=payload)
                        
                        try: 
                            b = driver.find_element(By.XPATH, "//button[contains(text(),'Regresar')]")
                            forzar_click(driver, b)
                        except: driver.execute_script("window.history.back();")
                        
                        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
                        recuperar_pagina(driver, pag)
                    
                    except: 
                        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
                        time.sleep(5)
                        continue
                except: continue

            print(f"✅ Pág {pag} Ok.")
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
