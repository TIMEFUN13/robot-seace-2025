import os
import time
import datetime
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

# ¡¡OJO AQUÍ!! 
# Pon False para descargar TODO el historial (Lento pero completo)
# Pon True para descargar SOLO lo publicado HOY (Rápido, para uso diario)
MODO_SOLO_HOY = False 

def enviar_telegram_simple(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': mensaje}
    try: requests.post(url, data=data)
    except: pass

def forzar_click(driver, elemento):
    driver.execute_script("arguments[0].click();", elemento)

def es_fecha_hoy(fecha_texto):
    """Verifica si la fecha string '16/12/2025' es igual a la fecha de hoy"""
    try:
        hoy = datetime.datetime.now().strftime("%d/%m/%Y")
        # Solo comparamos los primeros 10 caracteres (la fecha), ignoramos la hora
        return fecha_texto[:10] == hoy
    except:
        return True # Si falla, asumimos True para no perder datos

def recuperar_pagina(driver, pagina_objetivo):
    """Si el SEACE nos devuelve a la pág 1, volvemos a donde estábamos"""
    try:
        # Usamos ID exacto del paginador
        paginador = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
        txt = paginador.find_element(By.CSS_SELECTOR, ".ui-paginator-current").text
        
        import re
        match = re.search(r'Página:\s*(\d+)', txt)
        pag_actual = int(match.group(1)) if match else 1
        
        if pag_actual < pagina_objetivo:
            print(f"🔄 Recuperando posición: {pag_actual} -> {pagina_objetivo}")
            next_btn = paginador.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
            diferencia = pagina_objetivo - pag_actual
            
            # Saltamos rápido
            for _ in range(diferencia):
                forzar_click(driver, next_btn)
                time.sleep(2.5) # Un poco más rápido para recuperar
            return True
    except: pass
    return False

def main():
    print(f"Iniciando Robot 23.0 (Modo Minero | Solo Hoy: {MODO_SOLO_HOY})...")
    
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

        # 2. BUCLE MINERO
        pagina_actual = 1
        procesos_totales = 0
        
        while True:
            print(f"--- ⛏️ MINANDO PÁGINA {pagina_actual} ---")
            
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
            except:
                print("Fin de datos.")
                break

            filas = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
            num_filas = len(filas)
            print(f"Procesando {num_filas} filas...")

            for i in range(num_filas):
                try:
                    # Refrescamos filas
                    filas_refresh = driver.find_elements(By.CSS_SELECTOR, "tr[data-ri]")
                    if i >= len(filas_refresh): break
                    fila = filas_refresh[i]
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    
                    # DATOS LISTA
                    entidad = celdas[1].text
                    fecha_pub = celdas[2].text
                    nomenclatura = celdas[3].text
                    objeto = celdas[5].text
                    desc_corta = celdas[6].text
                    
                    # --- FILTRO DE EFICIENCIA ---
                    # Si MODO_SOLO_HOY está activado y la fecha no es de hoy, SALTAMOS
                    if MODO_SOLO_HOY and not es_fecha_hoy(fecha_pub):
                        print(f"⏩ Saltando proceso antiguo ({fecha_pub})")
                        continue

                    # Si pasamos el filtro, vamos a minar
                    snip = "No"
                    cui = "No"
                    
                    # Identificar botones (Lupas vs Ficha)
                    # TU DESCUBRIMIENTO: La Ficha es :grafichaSel
                    # Los otros son :graCodSnip y :graCodCUI
                    
                    # Intentamos ver si hay SNIP/CUI visibles (A veces salen iconos, a veces no)
                    # Por simplicidad, marcaremos que existen si vemos la lupa correspondiente
                    try:
                        if fila.find_elements(By.CSS_SELECTOR, "[id$=':graCodSnip']"): snip = "Sí (Ver Web)"
                        if fila.find_elements(By.CSS_SELECTOR, "[id$=':graCodCUI']"): cui = "Sí (Ver Web)"
                    except: pass
                    
                    # ENTRAR A FICHA (Buscamos la lupa correcta :grafichaSel)
                    try:
                        btn_ficha = fila.find_element(By.CSS_SELECTOR, "[id$=':grafichaSel']")
                        
                        print(f"📄 [Fila {i+1}] Entrando a Ficha ({nomenclatura})...")
                        forzar_click(driver, btn_ficha)
                        
                        # ESPERAR CARGA FICHA
                        time.sleep(5)
                        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "tbFicha:dtDocumentos_data")))
                        
                        # EXTRACCIÓN PDFs
                        pdfs_encontrados = []
                        filas_docs = driver.find_elements(By.CSS_SELECTOR, "#tbFicha\\:dtDocumentos_data tr")
                        for f_doc in filas_docs:
                            try:
                                links = f_doc.find_elements(By.TAG_NAME, "a")
                                for l in links:
                                    href = l.get_attribute("href")
                                    if href and "pdf" in href:
                                        pdfs_encontrados.append(href)
                            except: pass
                        
                        txt_pdf = "\n".join(pdfs_encontrados) if pdfs_encontrados else "Sin PDF"

                        # ENVÍO
                        payload = {
                            "fecha_real": fecha_pub,
                            "desc": f"{nomenclatura}\n{desc_corta}",
                            "entidad": entidad,
                            "pdf": txt_pdf,
                            "analisis": objeto,
                            "snip": snip,
                            "cui": cui
                        }
                        
                        r = requests.post(WEBHOOK_URL, json=payload)
                        if "DUPLICADO" in r.text:
                            print("🔹 Duplicado detectado por Excel.")
                        else:
                            print("✅ Nuevo dato guardado.")
                            
                        procesos_totales += 1
                        
                        # REGRESAR (Botón oficial)
                        print("🔙 Regresando...")
                        try:
                            btn_regresar = driver.find_element(By.XPATH, "//button[contains(text(),'Regresar')]")
                            forzar_click(driver, btn_regresar)
                        except:
                            driver.execute_script("window.history.back();")
                        
                        # Esperar lista
                        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr[data-ri]")))
                        recuperar_pagina(driver, pagina_actual)

                    except Exception as e:
                        print(f"⚠️ Error minando ficha: {e}. Intentando seguir...")
                        # Intento de recuperación básica
                        driver.get("https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml")
                        time.sleep(5)
                        continue
                        
                except Exception as e:
                    print(f"❌ Error crítico fila {i}: {e}")
                    continue

            # CAMBIO DE PÁGINA
            print(f"✅ Pág {pagina_actual} terminada.")
            try:
                # Usamos tu ID exacto
                pag_bottom = driver.find_element(By.ID, "tbBuscador:idFormBuscarProceso:dtProcesos_paginator_bottom")
                next_btn = pag_bottom.find_element(By.CSS_SELECTOR, ".ui-paginator-next")
                
                if "ui-state-disabled" in next_btn.get_attribute("class"):
                    print("🏁 Fin.")
                    break
                
                forzar_click(driver, next_btn)
                time.sleep(10)
                pagina_actual += 1
                if pagina_actual > 100: break
                
            except: break

        enviar_telegram_simple(f"✅ FIN. {procesos_totales} procesos procesados.")

    except Exception as e:
        print(f"❌ CRASH: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
