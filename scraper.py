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
    print("Iniciando Robot 19.0 (El Vigilante de Datos)...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # User Agent para evitar bloqueos
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1920, 1080)
    
    try:
        # 1. NAVEGACIÓN Y FILTROS
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

        # 2. BUCLE INTELIGENTE
        pagina_actual = 1
        procesos_totales = 0
        
        while True:
            print(f"--- PÁGINA {pagina_actual} ---")
            
            # Esperar a que haya filas
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            except:
                print("⚠️ No hay filas. Fin.")
                break

            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            if not filas: break

            # GUARDAMOS EL PRIMER DATO COMO "HUELLA DIGITAL" DE ESTA PÁGINA
            huella_digital_actual = filas[0].text
            
            # Extraer y Enviar Datos
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
                            "pdf": "Pendiente",
                            "analisis": objeto,
                            "fecha_real": fecha_pub
                        })
                except: continue

            print(f"Enviando {len(datos_lote)} items...")
            for dato in datos_lote:
                requests.post(WEBHOOK_URL, json=dato)
            
            procesos_totales += len(datos_lote)

            # 3. CAMBIAR PÁGINA (LÓGICA EL VIGILANTE)
            try:
                # Buscamos el botón correcto (El de abajo)
                # Selector ajustado a tu imagen: .ui-paginator-bottom .ui-paginator-next
                next_btn = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-bottom .ui-paginator-next")
                
                clases = next_btn.get_attribute("class")
                if "ui-state-disabled" in clases:
                    print("⛔ Botón gris detectado. Fin del camino.")
                    break
                
                print("Haciendo CLIC en Siguiente...")
                forzar_click(driver, next_btn)
                
                # --- LA MAGIA: ESPERAR A QUE LA TABLA CAMBIE ---
                print("Vigilando que los datos cambien...")
                datos_cambiaron = False
                
                # Esperamos hasta 20 segundos chequeando cada segundo
                for i in range(20):
                    time.sleep(1)
                    try:
                        nuevas_filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
                        if not nuevas_filas: continue
                        
                        nueva_huella = nuevas_filas[0].text
                        
                        # Si la primera fila es DIFERENTE a la anterior, significa que la página cambió
                        if nueva_huella != huella_digital_actual:
                            print(f"✅ ¡Datos cambiaron! Estamos en página nueva.")
                            datos_cambiaron = True
                            break
                    except: pass
                
                if not datos_cambiaron:
                    print("⚠️ Los datos NO cambiaron después de 20s. Asumo que se acabó.")
                    break
                
                pagina_actual += 1
                if pagina_actual > 100: break # Límite seguridad
                    
            except Exception as e:
                print(f"Error paginación: {e}")
                break

        enviar_telegram_simple(f"✅ FIN TOTAL. {procesos_totales} procesos extraídos.")

    except Exception as e:
        print(f"❌ CRASH: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
