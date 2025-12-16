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
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for p in pdf.pages[:10]:
                t = p.extract_text()
                if t: texto_completo += t + "\n"
    except Exception as e: return f"Error lectura PDF: {e}"

    if len(texto_completo) < 50: return "PDF imagen/ilegible."

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Eres un Ingeniero de Licitaciones. Analiza este texto técnico (TDR) del SEACE.
        {texto_completo[:25000]}
        
        Extrae REQUISITOS DEL PERSONAL CLAVE.
        Si no hay, resume el OBJETO DEL SERVICIO.

        Responde EXACTAMENTE con este formato:
        👷 **[CARGO 1]**: [Profesión]
        🕒 [Experiencia requerida]
        👷 **[CARGO 2]**: [Profesión]...
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
        return limpiar_texto_snip(limpio)
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
    print("Iniciando Robot 32.0 (EL VISUAL)...")
    
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
            if "2025" in s.get_attribute("textContent"):
                driver.execute_script("arguments[0].value = '2025'; arguments[0].dispatchEvent(new Event('change'));", s)
                break
        time.sleep(5)

        # BUSCAR
        print("Buscando...")
        try: driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:btnBuscarSel").click()
        except: driver.execute_script("document.querySelector('.btnBuscar_buscadorProcesos').click();")
        
        print("Esperando tabla...")
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
        
        pag = 1
        
        while True:
            print(f"--- ⛏️ PÁGINA {pag} ---")
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            if not filas: break

            for i in range(len(filas)):
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
                        analisis = "Sin PDF para analizar"
                        
                        try:
                            # 1. Limpiar carpeta
                            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")): os.remove(f)
                            
                            # 2. Esperar tabla de documentos
                            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID,"tbFicha:dtDocumentos_data")))
                            
                            # 3. LÓGICA VISUAL: BUSCAR EL ICONO DEL PDF
                            # Buscamos cualquier imagen que tenga 'pdf' en su nombre (ej: pdf.png)
                            # y hacemos clic en el enlace que la contiene.
                            botones_descarga = driver.find_elements(By.CSS_SELECTOR, "#tbFicha\\:dtDocumentos_data img[src*='pdf']")
                            
                            if botones_descarga:
                                print(f"⬇️ Icono PDF detectado. Descargando...")
                                # Click en el primero que encuentre (suelen ser las Bases)
                                boton = botones_descarga[0]
                                # A veces el click debe ser en el padre <a>
                                try:
                                    parent = boton.find_element(By.XPATH, "..")
                                    forzar_click(driver, parent)
                                except:
                                    forzar_click(driver, boton)
                                
                                # 4. Esperar descarga
                                f_path = None
                                for _ in range(25): # Damos 25 segundos
                                    time.sleep(1)
                                    fs = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
                                    if fs and not fs[0].endswith('.crdownload'): 
                                        f_path = fs[0]
                                        break
                                
                                if f_path:
                                    # EXITO!
                                    enviar_telegram_archivo(f_path, f"📄 {nom}")
                                    pdf_st = "En Telegram ✅"
                                    analisis = analizar_con_ia_gemini(f_path)
                                    print(f"🧠 IA Responde: {analisis[:30]}...")
                                else:
                                    print("❌ Timeout esperando archivo.")
                            else:
                                print("⚠️ No vi ningún icono de PDF en la tabla.")

                        except Exception as e: print(f"Error Docs: {e}")

                        # CRONOGRAMA
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
                        
                        # SALIR
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
