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
    try:
        requests.post(url, data=data)
    except:
        pass

def forzar_click(driver, elemento):
    """Función auxiliar para hacer clic sí o sí usando JavaScript"""
    driver.execute_script("arguments[0].click();", elemento)

def main():
    print("Iniciando Robot 11.0 (Tanque con Paginación)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. ENTRAR
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8) # Más tiempo inicial
        
        # 2. CAMBIAR PESTAÑA (Modo Seguro)
        print("Intentando cambiar pestaña...")
        try:
            pestana = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos"))
            )
            forzar_click(driver, pestana)
            print("✅ Pestaña clickeada (JS).")
            time.sleep(8)
        except Exception as e:
            print(f"⚠️ Falla pestaña: {e}. Intentando por ID...")
            try:
                driver.execute_script("document.getElementById('frmBuscador:idTabBuscador_lbl').click();")
                time.sleep(8)
            except:
                print("❌ No se pudo cambiar de pestaña. Esto podría fallar.")

        # 3. SELECCIONAR AÑO 2025 (Modo Seguro)
        print("Buscando año 2025...")
        # Desbloquear selects ocultos
        driver.execute_script("var s = document.getElementsByTagName('select'); for(var i=0; i<s.length; i++){ s[i].style.display = 'block'; }")
        
        selects = driver.find_elements(By.TAG_NAME, "select")
        anio_ok = False
        for s in selects:
            if "2025" in s.get_attribute("textContent"):
                try:
                    Select(s).select_by_visible_text("2025")
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", s)
                    print("✅ Año 2025 seleccionado.")
                    anio_ok = True
                    break
                except: continue
        
        if not anio_ok:
            print("⚠️ No encontré el selector de año, seguiré igual por si acaso.")
        
        time.sleep(5)

        # 4. CLIC EN BUSCAR (Modo Francotirador)
        print("Buscando botón...")
        id_btn = "tbBuscador:idFormBuscarProceso:btnBuscarSel"
        try:
            # Esperamos a que el botón exista en el DOM, aunque no sea interactable
            btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, id_btn)))
            forzar_click(driver, btn)
            print("✅ Clic forzado en Buscar.")
        except:
            print("⚠️ Botón por ID no encontrado. Buscando por clase...")
            botones = driver.find_elements(By.CSS_SELECTOR, ".btnBuscar_buscadorProcesos")
            if botones:
                forzar_click(driver, botones[0])
            else:
                print("❌ No encontré ningún botón de buscar.")

        print("Esperando tabla de resultados (20s)...")
        time.sleep(20)

        # 5. LECTURA INTELIGENTE DE PÁGINAS
        total_paginas = 1
        try:
            # Buscamos el texto "Página: 1/X"
            # Usamos un selector CSS genérico para el paginador de abajo
            paginadores = driver.find_elements(By.CLASS_NAME, "ui-paginator-current")
            if paginadores:
                texto_pag = paginadores[0].text # Ejemplo: "( Página: 1/34 )"
                print(f"Texto paginador encontrado: {texto_pag}")
                
                match = re.search(r'/\s*(\d+)', texto_pag)
                if match:
                    total_paginas = int(match.group(1))
                    print(f"✅ LÍMITE DETECTADO: {total_paginas} páginas.")
            else:
                print("⚠️ No vi el texto de paginación. Asumo 1 página.")
        except Exception as e:
            print(f"Error leve leyendo paginador: {e}")

        # --- BUCLE DE PAGINACIÓN ---
        pagina_actual = 1
        procesos_totales = 0
        
        while pagina_actual <= total_paginas:
            print(f"--- LEYENDO PÁGINA {pagina_actual}/{total_paginas} ---")
            
            # Esperar tabla
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]"))
                )
            except:
                print("⚠️ No cargaron filas en esta página.")
            
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            
            if not filas:
                print("Fin de los datos o error de carga.")
                break

            datos_lote = []
            for fila in filas:
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    if len(celdas) > 6:
                        # Extraemos datos limpiamente
                        entidad = celdas[1].text
                        fecha = celdas[2].text
                        nomenclatura = celdas[3].text
                        objeto = celdas[5].text
                        descripcion = celdas[6].text
                        
                        datos_lote.append({
                            "desc": f"{nomenclatura} - {descripcion}", 
                            "entidad": entidad,
                            "pdf": "Pendiente",
                            "analisis": f"{objeto} | {fecha}"
                        })
                except: continue

            # Enviar a Google Sheets
            for dato in datos_lote:
                requests.post(WEBHOOK_URL, json=dato)
                procesos_totales += 1
            
            print(f"Enviados {len(datos_lote)} procesos. Total acumulado: {procesos_totales}")

            # Siguiente página
            if pagina_actual < total_paginas:
                try:
                    # Buscamos el botón "Siguiente" por su clase de icono
                    next_btns = driver.find_elements(By.CSS_SELECTOR, ".ui-paginator-next")
                    if next_btns:
                        # Verificar si está deshabilitado
                        clases = next_btns[0].get_attribute("class")
                        if "ui-state-disabled" in clases:
                            print("Botón siguiente deshabilitado. Fin.")
                            break
                        
                        forzar_click(driver, next_btns[0])
                        print("Avanzando de página...")
                        time.sleep(10) # Tiempo generoso para carga
                        pagina_actual += 1
                    else:
                        break
                except Exception as e:
                    print(f"Error cambiando página: {e}")
                    break
            else:
                break

        enviar_telegram_simple(f"✅ Robot finalizado. Se extrajeron {procesos_totales} procesos de {total_paginas} páginas.")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        try:
            driver.save_screenshot("crash.png")
        except: pass
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
