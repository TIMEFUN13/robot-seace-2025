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
    print("Iniciando Robot 16.0 (Modo Paciencia)...")
    
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

        # 2. BUCLE INFINITO
        pagina_actual = 1
        procesos_totales = 0
        
        while True:
            print(f"--- PROCESANDO PÁGINA {pagina_actual} ---")
            
            try:
                # Esperar filas
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
                # PAUSA ESTRATÉGICA: Dar tiempo al paginador para que se actualice
                time.sleep(3) 
            except:
                print("⚠️ No hay filas o tardó mucho. Terminando.")
                break

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
                            "fecha_real": fecha_pub
                        })
                except: continue

            print(f"Enviando {len(datos_lote)} items...")
            for dato in datos_lote:
                requests.post(WEBHOOK_URL, json=dato)
            
            procesos_totales += len(datos_lote)

            # 3. VERIFICACIÓN DOBLE DEL BOTÓN SIGUIENTE
            print("Verificando botón Siguiente...")
            boton_activo_encontrado = False
            
            # Intentamos 3 veces ver si el botón se activa
            for intento in range(3):
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, ".ui-paginator-bottom .ui-paginator-next")
                    clases = next_btn.get_attribute("class")
                    
                    if "ui-state-disabled" not in clases:
                        # ¡EUREKA! El botón está vivo
                        print(f"✅ Botón activo encontrado (Intento {intento+1}).")
                        forzar_click(driver, next_btn)
                        boton_activo_encontrado = True
                        break # Salimos del mini-bucle de intentos
                    else:
                        print(f"Botón parece gris (Intento {intento+1}). Esperando 3 seg...")
                        time.sleep(3)
                except Exception as e:
                    print(f"Error leyendo botón: {e}")
                    time.sleep(3)
            
            if boton_activo_encontrado:
                print("Avanzando a siguiente página...")
                time.sleep(10) # Tiempo generoso para cargar la nueva tabla
                pagina_actual += 1
                if pagina_actual > 100: 
                    print("Límite de seguridad 100 alcanzado.")
                    break
            else:
                print("⛔ El botón siguió gris después de varios intentos. FIN REAL.")
                break

        enviar_telegram_simple(f"✅ FIN. {procesos_totales} procesos en {pagina_actual} páginas.")

    except Exception as e:
        print(f"❌ CRASH: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
