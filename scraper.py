import os
import time
import glob
import datetime
import requests
import pdfplumber
import google.generativeai as genai
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

def es_fecha_hoy(fecha_texto):
    try:
        hoy = datetime.datetime.now().strftime("%d/%m/%Y")
        return fecha_texto[:10] == hoy
    except: return True

def analizar_con_ia_gemini(ruta_pdf):
    print("      🧠 Consultando a Gemini...")
    texto_completo = ""
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for p in pdf.pages[:15]:
                t = p.extract_text()
                if t: texto_completo += t + "\n"
    except Exception as e: return f"Error lectura PDF: {e}"

    if len(texto_completo) < 50: return "PDF imagen/ilegible."

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Actúa como Ingeniero de Licitaciones. Analiza este TDR del SEACE:
        
        {texto_completo[:30000]}
        
        Extrae SOLO los Requisitos del Personal Clave. Responde en este formato:
        - [CARGO]: [Profesión]
        - [EXPERIENCIA]: [Tiempo y tipo de obras]
        - [OTRO]: [Maestrías/Diplomados si piden]
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e: return f"Error IA: {e}"

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
                    c = d.find_element(By.CSS_SELECTOR, "a.ui-dialog-titlebar-close")
                    forzar_click(driver, c)
                except: webdriver.ActionChains(driver).send_keys(u'\ue00c').perform()
                break
        limpio = texto.replace("Código SNIP", "").replace("Código Unico de Inversion", "").replace("Cerrar", "").strip()
        return limpio[:50] if len(limpio)>1 else "Sin Dato"
    except: return "Error"

def recuperar_pagina(driver, pagina_objetivo):
    try:
        p = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
        txt = p.find_element(By.CSS_SELECTOR, ".ui-paginator-current").text
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
    print("Iniciando Robot 28.0 (ANTI-BLOQUEOS)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    prefs = {"download.default_directory": DOWNLOAD_DIR, "download.prompt_for_download": False, "plugins.always_open_pdf_externally": True}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        
        # 1. PESTAÑA (Click JS agresivo)
        print("Abriendo buscador...")
        try:
            driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
        except:
            t = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos")))
            forzar_click(driver, t)
        time.sleep(5)

        # 2. AÑO 2025 (SOLUCIÓN AL CRASH "NOT INTERACTABLE")
        print("Seleccionando año 2025...")
        # Hacemos visibles los selects ocultos
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        
        found_year = False
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            # Buscamos el select que contiene el año 2025
            if "2025" in s.get_attribute("textContent"):
                # INTENTO 1: JS Directo (Más seguro)
                driver.execute_script("arguments[0].value = '2025'; arguments[0].dispatchEvent(new Event('change'));", s)
                found_year = True
                break
        
        if not found_year:
            print("⚠️ Advertencia: No encontré el selector de año, usando el por defecto.")
        
        time.sleep(5)

        # 3. BOTÓN BUSCAR
        print("Buscando...")
        try:
            btn = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:btnBuscarSel")
            forzar_click(driver, btn)
        except:
            driver.execute_script("document.querySelector('.btnBuscar_buscadorProcesos').click();")
        
        time.sleep(20)

        # 4. BUCLE MINERO
        pag = 1
        total = 0
        
        while True:
            print(f"--- ⛏️ PÁGINA {pag} ---")
            try: WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            except: break

            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            n = len(filas)
            
            for i in range(n):
                try:
                    filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
                    if i >= len(filas): break
                    row = filas[i]
                    cols = row.find_elements(By.TAG_NAME, "td")
                    
                    entidad = cols[1].text
                    fecha = cols[2].text
                    nom = cols[3].text
                    obj = cols[5].text
                    desc = cols[6].text
                    
                    if MODO_SOLO_HOY and not es_fecha_hoy(fecha): continue

                    # SNIP/CUI
                    snip=""; cui=""
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
                        time.sleep(6)
                        
                        pdf_st = "No PDF"
                        analisis = "Pendiente"
                        
                        # PDF y IA
                        try:
                            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")): os.remove(f)
                            WebDriverWait(driver,5).until(EC.presence_of_element_located((By.ID,"tbFicha:dtDocumentos_data")))
                            docs = driver.find_elements(By.CSS_SELECTOR, "#tbFicha\\:dtDocumentos_data tr")
                            
                            for d in docs:
                                try:
                                    lnk = d.find_element(By.TAG_NAME, "a")
                                    name = lnk.text
                                    if "Bases" in name or ".pdf" in name:
                                        print(f"⬇️ {name}...")
                                        forzar_click(driver, lnk)
                                        f_path = None
                                        for _ in range(15):
                                            time.sleep(1)
                                            fs = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
                                            if fs and not fs[0].endswith('.crdownload'):
                                                f_path = fs[0]; break
                                        
                                        if f_path:
                                            enviar_telegram_archivo(f_path, f"📄 {name}\n{nom}")
                                            pdf_st = "En Telegram ✅"
                                            analisis = analizar_con_ia_gemini(f_path)
                                            print(f"🧠 IA: {analisis[:40]}...")
                                            break
                                except: pass
                        except Exception as e: print(f"ErrDocs: {e}")

                        # Cronograma
                        crono = ""
                        try:
                            t = driver.find_element(By.ID, "tbFicha:dtCronograma_data")
                            for r in t.find_elements(By.TAG_NAME, "tr"):
                                txt = r.text
                                if "Propuestas" in txt or "Buena Pro" in txt:
                                    cc = r.find_elements(By.TAG_NAME, "td")
                                    if len(cc)>=2: crono += f"📅 {cc[0].text}: {cc[1].text}\n"
                        except: pass

                        rep = f"OBJETO: {obj}\n\n{crono}\n--- 🧠 ANÁLISIS IA ---\n{analisis}"
                        
                        payload = {
                            "fecha_real": fecha, "desc": f"{nom}\n{desc}", "entidad": entidad,
                            "pdf": pdf_st, "analisis": rep, "snip": snip, "cui": cui
                        }
                        requests.post(WEBHOOK_URL, json=payload)
                        total += 1
                        
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
