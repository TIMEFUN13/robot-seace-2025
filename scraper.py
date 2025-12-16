import os
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
    print("Iniciando Robot 21.0 (Target ID Exacto)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. NAVEGACIÓN
        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
        time.sleep(8)
        
        # Pestaña
        try:
            pestana = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Buscador de Procedimientos")))
            forzar_click(driver, pestana)
            time.sleep(5)
        except:
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

        # 2. BUCLE PRINCIPAL
        pagina_actual = 1
        procesos_totales = 0
        texto_paginador_actual = "" # Guardaremos "Página: 1/34" aquí
        
        while True:
            print(f"--- PROCESANDO PÁGINA {pagina_actual} ---")
            
            # Esperar filas
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            except:
                print("⚠️ No cargaron filas. Fin.")
                break

            # Leer el texto del paginador ACTUAL para compararlo después
            try:
                # Usamos el ID exacto que me pasaste
                paginador_bottom = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
                span_texto = paginador_bottom.find_element(By.CSS_SELECTOR, ".ui-paginator-current")
                texto_paginador_actual = span_texto.text # Ej: "... Página: 1/34 ]"
                print(f"Ubicación actual: {texto_paginador_actual}")
            except:
                print("No pude leer el texto del paginador, pero seguiré.")

            # Extraer datos
            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            if not filas: break
            
            datos_lote = []
            for fila in filas:
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    if len(celdas) > 6:
                        datos_lote.append({
                            "desc": f"{celdas[3].text}\n{celdas[6].text}",
                            "entidad": celdas[1].text,
                            "pdf": "Pendiente",
                            "analisis": celdas[5].text,
                            "fecha_real": celdas[2].text
                        })
                except: continue

            print(f"Enviando {len(datos_lote)} items...")
            for dato in datos_lote:
                requests.post(WEBHOOK_URL, json=dato)
            procesos_totales += len(datos_lote)

            # 3. CAMBIO DE PÁGINA (USANDO ID EXACTO)
            try:
                # Buscamos el contenedor por su ID exacto
                contenedor = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
                # Buscamos el botón "Siguiente" dentro de ese contenedor
                next_btn = contenedor.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
                
                # Verificamos si está deshabilitado
                clases = next_btn.get_attribute("class")
                if "ui-state-disabled" in clases:
                    print("⛔ Botón gris (clase ui-state-disabled). Fin del camino.")
                    break
                
                print("Haciendo clic en Siguiente...")
                forzar_click(driver, next_btn)
                
                # --- LA VERIFICACIÓN DE ÉXITO ---
                print("Esperando que cambie el número de página...")
                cambio_detectado = False
                
                for i in range(20): # Esperamos 20 segundos
                    time.sleep(1)
                    try:
                        # Releemos el texto del paginador
                        p_bottom = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
                        nuevo_txt = p_bottom.find_element(By.CSS_SELECTOR, ".ui-paginator-current").text
                        
                        # Si el texto es diferente (Ej: cambió de 1/34 a 2/34), avanzamos
                        if nuevo_txt != texto_paginador_actual:
                            print(f"✅ ¡Cambio confirmado! Ahora en: {nuevo_txt}")
                            cambio_detectado = True
                            break
                    except: pass
                
                if cambio_detectado:
                    pagina_actual += 1
                else:
                    print("⚠️ El número de página no cambió tras el clic. Asumo fin o bloqueo.")
                    break
                    
                if pagina_actual > 100: break

            except Exception as e:
                print(f"Error en paginación: {e}")
                break

        enviar_telegram_simple(f"✅ FIN TOTAL. {procesos_totales} procesos extraídos.")

    except Exception as e:
        print(f"❌ CRASH: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
