import os
import time
import glob
import json
import base64
import datetime
import requests
import subprocess
import pdfplumber
import pypdf
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

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

MODELO_ACTUAL = None

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

def obtener_modelo_dinamico():
    global MODELO_ACTUAL
    if MODELO_ACTUAL: return MODELO_ACTUAL

    print("      🔍 Buscando modelo IA disponible...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            modelos = data.get('models', [])
            candidato = None
            for m in modelos:
                nombre = m['name']
                metodos = m.get('supportedGenerationMethods', [])
                if 'generateContent' in metodos:
                    if 'flash' in nombre.lower():
                        MODELO_ACTUAL = nombre
                        return MODELO_ACTUAL
                    elif 'pro' in nombre.lower() and not candidato:
                        candidato = nombre
            if candidato:
                MODELO_ACTUAL = candidato
                return MODELO_ACTUAL
            return "models/gemini-1.5-flash"
        else:
            return "models/gemini-1.5-flash"
    except:
        return "models/gemini-1.5-flash"

def clasificar_proceso(nombre_proceso, descripcion):
    nombre = nombre_proceso.upper()
    desc = descripcion.upper()
    
    tipo_excel = "OTROS"
    if "LP" in nombre or "LICITACION" in desc: tipo_excel = "LICITACIÓN PÚBLICA"
    elif "CP" in nombre or "CONCURSO" in desc: tipo_excel = "CONCURSO PÚBLICO"
    elif "AS" in nombre or "ADJUDICACION SIMPLIFICADA" in desc: tipo_excel = "ADJUDICACIÓN SIMPLIFICADA"
    elif "SIE" in nombre or "SUBASTA" in desc: tipo_excel = "SUBASTA INVERSA"
    elif "SCI" in nombre or "CONSULTORES INDIVIDUALES" in desc: tipo_excel = "SEL. CONSULTORES INDIVIDUALES"
    elif "COMPRE" in nombre: tipo_excel = "COMPARACIÓN DE PRECIOS"

    categoria_prompt = "GENERAL"
    if "OBRA" in desc or "EJECUCION" in desc or "MANTENIMIENTO VIAL" in desc:
        categoria_prompt = "OBRA"
    elif "CONSULTORIA" in desc or "SUPERVISION" in desc or "ESTUDIO" in desc or "ELABORACION" in desc:
        categoria_prompt = "CONSULTORIA"
    elif "SERVICIO" in desc or "CONTRATACION DE" in desc:
        categoria_prompt = "SERVICIO"
    elif "ADQUISICION" in desc or "COMPRA" in desc or "SUMINISTRO" in desc:
        categoria_prompt = "BIEN"
    
    if "SIE" in nombre: categoria_prompt = "SUBASTA"
        
    return tipo_excel, categoria_prompt

def obtener_prompt_experto(categoria):
    if categoria == "OBRA":
        return """
        [ROL]: Actúa como Gerente Técnico de Infraestructura experto en Licitaciones Públicas de Obras.
        [CONTEXTO]: Estamos evaluando participar en esta ejecución de obra. Un error en los requisitos técnicos o financieros nos descalifica inmediatamente.
        [ACCIÓN]: Analiza las bases integradas (TDR) y extrae los requisitos críticos de admisibilidad y puntaje.
        [EXPECTATIVA]: Genera un reporte estratégico ESTRICTAMENTE con esta estructura:
        
        🎯 **ESTRATEGIA:** [Resumen de 1 línea sobre la magnitud de la obra]
        💰 **SOLVENCIA (KILLER):**
           * Facturación requerida: [Monto exacto y periodo]
           * Línea de Crédito: [Monto exacto]
        👷 **PLANTEL CLAVE:**
           * [Cargo]: [Profesión] | [Experiencia exacta requerida]
        🚜 **MAQUINARIA CRÍTICA:**
           * [Equipo] | [Antigüedad máxima permitida]
        🏆 **PUNTAJE EXTRA:** [¿Qué nos da ventaja?]
        """
    elif categoria == "CONSULTORIA":
        return """
        [ROL]: Actúa como Especialista Senior en Concursos de Méritos y Consultoría.
        [CONTEXTO]: En consultoría, la experiencia del personal y la metodología definen al ganador. Necesitamos saber si cumplimos el perfil.
        [ACCIÓN]: Audita los Términos de Referencia y detecta los requisitos del equipo humano.
        [EXPECTATIVA]: Genera un reporte estratégico ESTRICTAMENTE con esta estructura:

        🎯 **ESTRATEGIA:** [Tipo de estudio o supervisión]
        🧠 **JEFE DE PROYECTO (CRÍTICO):**
           * Profesión: [Carrera exacta]
           * Grados: [¿Pide Maestría/Doctorado?]
           * Experiencia: [Tiempo exacto en meses/años]
        👥 **EQUIPO TÉCNICO:**
           * [Especialista]: [Requisito clave]
        🏆 **FACTORES DE EVALUACIÓN:** [¿Qué da más puntos? ¿Metodología? ¿ISO?]
        💼 **EXPERIENCIA EMPRESA:** [Monto facturado requerido]
        """
    elif categoria == "BIEN":
        return """
        [ROL]: Actúa como Jefe de Compras y Logística del Estado.
        [CONTEXTO]: Es una adquisición de bienes. Si el producto no cumple una especificación técnica o el plazo, nos ejecutan la penalidad.
        [ACCIÓN]: Extrae las especificaciones técnicas "duras" y las condiciones de entrega.
        [EXPECTATIVA]: Genera un reporte estratégico ESTRICTAMENTE con esta estructura:

        🎯 **PRODUCTO:** [Nombre y cantidad principal]
        ⚙️ **ESPECIFICACIONES TÉCNICAS (NO NEGOCIABLES):**
           * [Características clave: Material, Medidas, Normas Técnicas]
        🧪 **MUESTRAS:** [¿Se exige presentación de muestras? SÍ/NO y cuándo]
        🚚 **LOGÍSTICA:**
           * Plazo: [Días calendario]
           * Lugar: [Punto de entrega]
        📄 **DOCUMENTACIÓN OBLIGATORIA:** [Fichas técnicas, manuales, registros sanitarios]
        """
    elif categoria == "SUBASTA":
        return """
        [ROL]: Actúa como Analista de Costos para Subasta Inversa Electrónica.
        [CONTEXTO]: En SIE solo importa el precio y cumplir la ficha técnica para ser admitido. No hay puntaje técnico.
        [ACCIÓN]: Verifica la admisibilidad del producto.
        [EXPECTATIVA]: Genera un reporte rápido ESTRICTAMENTE con esta estructura:

        ⚡ **FICHA PERÚ COMPRAS:** [Código o nombre de la ficha técnica]
        🚫 **REQUISITOS HABILITANTES:** [Documentos obligatorios para no ser depurado]
        📍 **DESTINO:** [Lugar de entrega para cálculo de flete]
        📅 **FECHA PUJA:** [Si aparece, indícala]
        """
    else: # SERVICIO GENERAL
        return """
        [ROL]: Actúa como Administrador de Contratos de Servicios.
        [CONTEXTO]: Proceso de contratación de servicios generales (limpieza, seguridad, mantenimiento). El volumen de personal y cumplimiento laboral es clave.
        [ACCIÓN]: Extrae los requisitos operativos y documentales.
        [EXPECTATIVA]: Genera un reporte estratégico ESTRICTAMENTE con esta estructura:

        🎯 **SERVICIO:** [Alcance principal]
        👥 **PERSONAL OPERATIVO:**
           * Cantidad: [Número de operarios]
           * Requisitos: [Estudios, cursos, carnets]
        🛠️ **EQUIPAMIENTO/MATERIALES:** [Lista de lo que debemos poner]
        📜 **DOCUMENTACIÓN:** [Registros obligatorios como RENSSC, SUCAMEC, etc.]
        💼 **EXPERIENCIA:** [Facturación requerida]
        """

def analizar_con_ia_directo(texto_o_imagenes, categoria_prompt="GENERAL", es_imagen=False):
    nombre_modelo = obtener_modelo_dinamico()
    if not nombre_modelo.startswith("models/"): nombre_modelo = f"models/{nombre_modelo}"
    
    print(f"      📡 Enviando a {nombre_modelo} (Modo: {categoria_prompt})...")
    url = f"https://generativelanguage.googleapis.com/v1beta/{nombre_modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_race = obtener_prompt_experto(categoria_prompt)
    
    payload = {"contents": []}
    
    if es_imagen:
        parts = [{"text": prompt_race}]
        for img_path in texto_o_imagenes:
            with open(img_path, "rb") as image_file:
                b64_data = base64.b64encode(image_file.read()).decode('utf-8')
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_data}})
        payload["contents"].append({"parts": parts})
    else:
        full_text = f"{prompt_race}\n\nDOCUMENTO A ANALIZAR:\n{texto_o_imagenes[:100000]}"
        payload["contents"].append({"parts": [{"text": full_text}]})

    # --- LÓGICA DE REINTENTO (RETRY) PARA ERRORES 503/429 ---
    max_retries = 3
    for intento in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            
            elif response.status_code in [503, 429, 500]:
                # Error de servidor o cuota -> ESPERAR Y REINTENTAR
                wait_time = (intento + 1) * 5 # Espera 5s, 10s, 15s...
                print(f"      ⚠️ Error {response.status_code}. Google saturado. Reintentando en {wait_time}s...")
                time.sleep(wait_time)
                continue # Volver a probar
            
            else:
                return f"Error API {response.status_code}: {response.text[:100]}"
                
        except Exception as e:
            print(f"      ⚠️ Excepción conexión: {e}. Reintentando...")
            time.sleep(5)
            continue

    return "Error IA: Servicio no disponible tras varios intentos (503)."

def procesar_documento(ruta_archivo, categoria_prompt):
    ext = ruta_archivo.lower().split('.')[-1]
    texto_completo = ""
    print(f"      📖 Leyendo doc ({categoria_prompt})...")

    if ext in ['doc', 'docx']:
        texto_completo = extraer_texto_word(ruta_archivo)
    elif ext == 'pdf':
        try:
            with pdfplumber.open(ruta_archivo) as pdf:
                for p in pdf.pages:
                    t = p.extract_text()
                    if t: texto_completo += t + "\n"
        except: pass
    
    if len(texto_completo) < 500 and ext == 'pdf':
        print("      👁️ Doc Escaneado. Activando OCR Total (Sin límites)...")
        try:
            imagenes = convert_from_path(ruta_archivo) 
            rutas_imgs = []
            for i, img in enumerate(imagenes):
                img = img.resize((1000, 1400)) 
                tmp_path = os.path.join(DOWNLOAD_DIR, f"temp_{i}.jpg")
                img.save(tmp_path, 'JPEG', quality=80)
                rutas_imgs.append(tmp_path)
            
            res = analizar_con_ia_directo(rutas_imgs, categoria_prompt, es_imagen=True)
            for r in rutas_imgs: 
                try: os.remove(r)
                except: pass
            return res
        except Exception as e: return f"Error OCR Masivo: {e}"
        
    elif len(texto_completo) < 50:
        return "⚠️ Archivo vacío."
    else:
        return analizar_con_ia_directo(texto_completo, categoria_prompt, es_imagen=False)

def restaurar_ubicacion(driver):
    try:
        try:
            pestana = driver.find_element(By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos")
            pestana.click()
            time.sleep(3)
        except:
            driver.execute_script("try{document.getElementById('frmBuscador:idTabBuscador_lbl').click();}catch(e){}")
            time.sleep(3)

        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            if "2025" in obtener_texto_seguro(s):
                val = driver.execute_script("return arguments[0].value", s)
                if val != "2025":
                    driver.execute_script("arguments[0].value = '2025'; arguments[0].dispatchEvent(new Event('change'));", s)
                    time.sleep(3)
                break
        
        print("      🔄 Refrescando búsqueda...")
        try: driver.execute_script("document.getElementById('tbBuscador:idFormBuscarProceso:btnBuscarSel').click();")
        except: driver.execute_script("document.querySelector('.btnBuscar_buscadorProcesos').click();")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
        return True
    except: return False

def main():
    print("Iniciando Robot 56.0 (PROMPTS RACE + ANTI-503)...")
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
        time.sleep(5)
        restaurar_ubicacion(driver)
        obtener_modelo_dinamico() 
        
        pag = 1
        while True:
            print(f"--- ⛏️ PÁGINA {pag} ---")
            filas_iniciales = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            if not filas_iniciales: break
            num_filas = len(filas_iniciales)

            for i in range(num_filas):
                try:
                    if i > 0: restaurar_ubicacion(driver)
                    
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
                    
                    tipo_proceso, categoria_ia = clasificar_proceso(nom, desc)
                    print(f"👉 {i+1}/{num_filas}: {nom[:15]}... [{categoria_ia}]")

                    snip="-"; cui="-"
                    try:
                        l=row.find_element(By.CSS_SELECTOR, "[id$=':graCodSnip']")
                        if l.is_displayed(): snip=driver.execute_script("return arguments[0].textContent", l)
                    except: pass
                    
                    celda_acciones = cols[-1]
                    botones = celda_acciones.find_elements(By.TAG_NAME, "a")
                    btn_ficha = None
                    if len(botones) >= 2: btn_ficha = botones[1]
                    elif len(botones) == 1: btn_ficha = botones[0]
                    
                    if btn_ficha:
                        forzar_click(driver, btn_ficha)
                        time.sleep(6)
                        pdf_st = "Sin Archivo"; analisis = "Sin Doc"
                        
                        try:
                            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")): 
                                try: os.remove(f)
                                except: pass
                            
                            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID,"tbFicha:dtDocumentos_data")))
                            filas_docs = driver.find_elements(By.CSS_SELECTOR, "#tbFicha\\:dtDocumentos_data tr")
                            mejor_link = None; mejor_prio = 0
                            
                            for fd in filas_docs:
                                try:
                                    enlaces = fd.find_elements(By.CSS_SELECTOR, "a[onclick*='descargaDocGeneral']")
                                    if not enlaces: continue
                                    lnk = enlaces[0]
                                    txt = obtener_texto_seguro(fd).upper()
                                    prio = 0
                                    if "BASES" in txt: prio = 4
                                    elif "TDR" in txt: prio = 3
                                    elif fd.find_elements(By.CSS_SELECTOR, "img[src*='pdf']"): prio = 2
                                    elif fd.find_elements(By.CSS_SELECTOR, "img[src*='word']"): prio = 1
                                    if prio >= mejor_prio: mejor_prio = prio; mejor_link = lnk
                                except: pass
                            
                            if mejor_link:
                                print(f"   ⬇️ Descargando...")
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
                                    analisis = procesar_documento(f_path, categoria_ia)
                                    print(f"   🧠 IA: Resumen generado.")
                                else: print("   ❌ Timeout")
                            else: print("   ⚠️ Sin docs")

                        except Exception as e: print(f"   ErrDocs: {e}")

                        rep = f"{analisis}"
                        payload = {
                            "fecha_real": fecha, 
                            "desc": f"{nom}\n{desc}", 
                            "entidad": entidad, 
                            "pdf": pdf_st, 
                            "analisis": rep, 
                            "snip": snip, 
                            "cui": cui,
                            "tipo": tipo_proceso
                        }
                        requests.post(WEBHOOK_URL, json=payload)
                        
                        try: 
                            b = driver.find_element(By.XPATH, "//button[contains(text(),'Regresar')]")
                            forzar_click(driver, b)
                        except: driver.execute_script("window.history.back();")
                        
                    else: print("⚠️ Sin botón ficha")
                    
                except Exception as e: 
                    restaurar_ubicacion(driver)
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
