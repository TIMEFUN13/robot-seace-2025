import os
import re
import time
import requests
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

def enviar_telegram_simple(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': mensaje}
    try: requests.post(url, data=data)
    except: pass

def forzar_click(driver, elemento):
    driver.execute_script("arguments[0].click();", elemento)

def main():
    print("Iniciando Robot 13.0 (Corrección Final)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # User Agent estándar
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. NAVEGACIÓN
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        
        # Cambiar Pestaña
        try:
            pestana = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos")))
            forzar_click(driver, pestana)
            time.sleep(5)
        except:
            print("⚠️ No pude cambiar pestaña por texto, intentando ID...")
            driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
            time.sleep(5)

        # Año 2025
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        selects = driver.find_elements(By.TAG_NAME, "select")
        for s in selects:
            if "2025" in s.get_attribute("textContent"):
                try:
                    Select(s).select_by_visible_text("2025")
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", s)
                    break
                except: continue
        time.sleep(5)

        # Buscar
        print("Buscando...")
        id_btn = "tbBuscador:idFormBuscarProceso:btnBuscarSel"
        try:
            btn = driver.find_element(By.ID, id_btn)
            forzar_click(driver, btn)
        except:
            btns = driver.find_elements(By.CSS_SELECTOR, ".btnBuscar_buscadorProcesos")
            if btns: forzar_click(driver, btns[0])
        
        print("Esperando tabla (20s)...")
        time.sleep(20)

        # 2. LECTURA DE PAGINACIÓN (LOOP DE ESPERA)
        total_paginas = 1
        intentos = 0
        texto_footer = ""
        
        print("Leyendo número de páginas...")
        while intentos < 5:
            try:
                # Usamos textContent para leer texto aunque esté medio oculto
                footer = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-bottom")
                texto_footer = footer.get_attribute("textContent")
                
                if texto_footer and "Página" in texto_footer:
                    print(f"Texto encontrado: '{texto_footer}'")
                    break
                else:
                    print("Texto vacío, esperando...")
                    time.sleep(2)
                    intentos += 1
            except:
                time.sleep(2)
                intentos += 1

        # Extraer número
        match = re.search(r'/\s*(\d+)', texto_footer)
        if match:
            total_paginas = int(match.group(1))
            print(f"✅ TOTAL PÁGINAS REAL: {total_paginas}")
        else:
            print(f"⚠️ No pude leer el número final. Texto visto: '{texto_footer}'. Asumo 1 página.")

        # --- BUCLE ---
        pagina_actual = 1
        procesos_totales = 0
        
        while pagina_actual <= total_paginas:
            print(f"--- PÁGINA {pagina_actual}/{total_paginas} ---")
            
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            
            if not filas: break

            datos_lote = []
            for fila in filas:
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    if len(celdas) > 6:
                        entidad = celdas[1].text
                        fecha_pub = celdas[2].text
                        nomenclatura = celdas[3].text
                        objeto = celdas[5].text
                        descripcion = celdas[6].text
                        
                        datos_lote.append({
                            "desc": f"{nomenclatura}\n{descripcion}",
                            "entidad": entidad,
                            "pdf": "Ver Link",
                            "analisis": objeto, 
                            "fecha_real": fecha_pub # CLAVE PARA TU EXCEL
                        })
                except: continue

            # ENVIAR Y VERIFICAR RESPUESTA
            print(f"Enviando {len(datos_lote)} datos a Google...")
            for dato in datos_lote:
                r = requests.post(WEBHOOK_URL, json=dato)
                # Esto imprimirá si Google aceptó el dato o dio error
                if r.status_code != 200:
                    print(f"❌ ERROR WEBHOOK: Código {r.status_code}. Revisa tu URL en GitHub Secrets.")
                    break
            
            procesos_totales += len(datos_lote)
            print(f"Acumulado: {procesos_totales}")

            if pagina_actual < total_paginas:
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
                    if "ui-state-disabled" in next_btn.get_attribute("class"): break
                    forzar_click(driver, next_btn)
                    time.sleep(8)
                    pagina_actual += 1
                except: break
            else: break

        enviar_telegram_simple(f"✅ Fin. {procesos_totales} procesos extraídos.")

    except Exception as e:
        print(f"❌ CRASH: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
