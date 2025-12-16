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
    print("Iniciando Robot 12.0 (Corrector de Paginación y Columnas)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. NAVEGACIÓN (Rutina estándar)
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        
        # Cambiar Pestaña
        try:
            pestana = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos")))
            forzar_click(driver, pestana)
            time.sleep(5)
        except:
            driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
            time.sleep(5)

        # Seleccionar Año 2025
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
        id_btn = "tbBuscador:idFormBuscarProceso:btnBuscarSel"
        try:
            btn = driver.find_element(By.ID, id_btn)
            forzar_click(driver, btn)
        except:
            btns = driver.find_elements(By.CSS_SELECTOR, ".btnBuscar_buscadorProcesos")
            if btns: forzar_click(driver, btns[0])
        
        print("Esperando tabla (20s)...")
        time.sleep(20)

        # 2. LECTURA DE PAGINACIÓN MEJORADA
        total_paginas = 1
        try:
            # En lugar de buscar una clase específica, leemos TODO el pie de página
            footer_paginador = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-bottom")
            texto_footer = footer_paginador.text # Ejemplo: "Mostrando 1 a 15... Página: 1/34"
            print(f"Texto del pie de página detectado: '{texto_footer}'")
            
            # Buscamos cualquier patrón que sea "numero / numero"
            match = re.search(r'Página:\s*\d+\s*/\s*(\d+)', texto_footer)
            if match:
                total_paginas = int(match.group(1))
                print(f"✅ ¡EUREKA! Total de páginas detectadas: {total_paginas}")
            else:
                # Intento secundario más simple (buscar el último número después de un slash)
                match_simple = re.search(r'/\s*(\d+)', texto_footer)
                if match_simple:
                    total_paginas = int(match_simple.group(1))
                    print(f"✅ Límite detectado (Método 2): {total_paginas}")
        except Exception as e:
            print(f"⚠️ Error leyendo paginación: {e}. Asumiendo 1 página.")

        # --- BUCLE DE PAGINACIÓN ---
        pagina_actual = 1
        procesos_totales = 0
        
        while pagina_actual <= total_paginas:
            print(f"--- LEYENDO PÁGINA {pagina_actual}/{total_paginas} ---")
            
            # Esperar tabla
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            
            if not filas: break

            datos_lote = []
            for fila in filas:
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    if len(celdas) > 6:
                        # MAPPING CORRECTO DE COLUMNAS
                        # Col 0: Indice
                        entidad = celdas[1].text  # Col 1: Entidad
                        fecha_pub = celdas[2].text # Col 2: Fecha Publicación
                        nomenclatura = celdas[3].text # Col 3: Nomenclatura
                        # Col 4 suele ser vacía o reinicio
                        objeto = celdas[5].text   # Col 5: Objeto (Bien, Servicio...)
                        descripcion = celdas[6].text # Col 6: Descripción
                        
                        # Limpieza de datos para el Sheet
                        datos_lote.append({
                            "desc": f"{nomenclatura}\n{descripcion}", # Descripción completa
                            "entidad": entidad, # Entidad limpia
                            "pdf": "Ver Detalle", # Aún no podemos sacar link sin entrar
                            # AQUÍ CORREGIMOS EL ERROR DE FECHAS MEZCLADAS
                            # Mandamos 'fecha_pub' a la columna que tu script de Apps Script pone en la Columna A (Fecha)
                            # Pero ojo: Tu Apps Script pone `new Date()` en la Col A.
                            # Vamos a mandar la fecha real en el campo 'analisis' o 'pdf' para que la veas.
                            "analisis": objeto # Solo el tipo de objeto, sin fecha sucia
                        })
                        
                        # TRUCO: Para que la fecha del SEACE salga en tu Excel, 
                        # vamos a modificar el Apps Script después. Por ahora, el robot enviará:
                        # Descripcion, Entidad, Link (Texto), Analisis (Objeto)
                except: continue

            # Enviar a Sheets
            for dato in datos_lote:
                # Añadimos la fecha real del SEACE al JSON para que podamos usarla
                dato['fecha_real'] = fecha_pub 
                requests.post(WEBHOOK_URL, json=dato)
                procesos_totales += 1
            
            print(f"Enviados {len(datos_lote)}. Total: {procesos_totales}")

            # Siguiente página
            if pagina_actual < total_paginas:
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
                    if "ui-state-disabled" in next_btn.get_attribute("class"): break
                    forzar_click(driver, next_btn)
                    time.sleep(10) # Tiempo para cargar
                    pagina_actual += 1
                except: break
            else: break

        enviar_telegram_simple(f"✅ Robot terminó. {procesos_totales} procesos de {total_paginas} páginas.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
