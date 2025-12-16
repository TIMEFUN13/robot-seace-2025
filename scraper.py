import os
import re # Módulo para buscar texto
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
    requests.post(url, data=data)

def main():
    print("Iniciando Robot 10.0 (Lector Inteligente de Paginación)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. CONFIGURACIÓN INICIAL Y BÚSQUEDA
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(5)
        
        # Clic en pestaña "Buscador de Procedimientos"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos"))).click()
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
        time.sleep(3)

        # Clic en Buscar
        id_btn = "tbBuscador:idFormBuscarProceso:btnBuscarSel"
        driver.find_element(By.ID, id_btn).click()
        print("Buscando... Esperando 15s...")
        time.sleep(15)

        # 2. LECTURA INTELIGENTE DEL LÍMITE DE PÁGINAS
        total_paginas = 0
        try:
            # Buscar el elemento que contiene el texto de paginación ("Página 1/X")
            paginador_texto = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-page").find_element(By.XPATH, "../..").text
            
            # Usar Expresiones Regulares para encontrar el número después de "/"
            # Busca: (un número) / (el número de páginas)
            match = re.search(r'/\s*(\d+)', paginador_texto)
            if match:
                total_paginas = int(match.group(1))
                print(f"✅ LÍMITE DETECTADO: El robot leerá {total_paginas} páginas.")
            else:
                total_paginas = 1 # Si no encuentra el patrón, asume que solo hay 1 página
                print("⚠️ No se pudo detectar el límite de páginas. Asumiendo 1 página.")
        except Exception as e:
            print(f"Error al leer el paginador: {e}")
            total_paginas = 1
        
        # --- BUCLE DE PAGINACIÓN ---
        pagina_actual = 1
        procesos_totales = 0
        
        while pagina_actual <= total_paginas:
            print(f"--- Procesando PÁGINA {pagina_actual} de {total_paginas} ---")
            
            # Esperar a que la tabla cargue (la tabla de resultados tiene el ID tbBuscador:idFormBuscarProceso:dataTableResultados)
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "tbBuscador:idFormBuscarProceso:dataTableResultados"))
            )
            
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            
            if not filas:
                print("No se encontraron filas de resultados en esta página.")
                break

            datos_lote = [] 

            for fila in filas:
                try:
                    # EXTRAER DATOS COLUMNA POR COLUMNA
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    if len(celdas) > 5:
                        entidad = celdas[1].text
                        fecha = celdas[2].text
                        nomenclatura = celdas[3].text
                        objeto = celdas[5].text
                        descripcion = celdas[6].text
                        
                        datos_lote.append({
                            "desc": f"{nomenclatura} - {descripcion}", 
                            "entidad": entidad,
                            "pdf": "Pendiente",
                            "analisis": f"{objeto} | Pub: {fecha}"
                        })
                except Exception as e:
                    print(f"Error leyendo una fila: {e}")
                    continue

            # ENVIAR LOTE A GOOGLE SHEETS
            for dato in datos_lote:
                requests.post(WEBHOOK_URL, json=dato)
                procesos_totales += 1
            
            print(f"Enviados {len(datos_lote)} procesos al Excel. Acumulado: {procesos_totales}")

            # --- AVANZAR A LA SIGUIENTE PÁGINA ---
            if pagina_actual < total_paginas:
                try:
                    btn_siguiente = driver.find_elements(By.CSS_SELECTOR, ".ui-paginator-next")
                    
                    if btn_siguiente and "ui-state-disabled" not in btn_siguiente[0].get_attribute("class"):
                        # Usamos Javascript para asegurar el clic del paginador
                        driver.execute_script("arguments[0].click();", btn_siguiente[0])
                        print("Avanzando...")
                        time.sleep(8) 
                        pagina_actual += 1
                    else:
                        print("Última página alcanzada (botón deshabilitado).")
                        break
                except Exception as e:
                    print(f"Error al cambiar página: {e}. Finalizando bucle.")
                    break
            else:
                break # Si pagina_actual == total_paginas, salimos

        enviar_telegram_simple(f"✅ ¡Misión Cumplida! Se extrajeron {procesos_totales} procesos de {total_paginas} páginas.")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        # Intenta tomar captura en caso de error crítico
        try:
            driver.save_screenshot("crash.png")
            enviar_telegram_simple(f"Crash: {e}. Revisa la captura en el log.")
        except:
            enviar_telegram_simple(f"Crash: {e}. No se pudo tomar captura.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
