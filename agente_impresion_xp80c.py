"""
==========================================================
AGENTE DE IMPRESION ESC/POS - Escuela Villa Las Penas
Impresora: Xprinter XP-80C (80mm con autocortador)
==========================================================
Requisitos (instalar una sola vez con instalar_agente.bat):
  pip install supabase pywin32

Uso:
  pythonw agente_impresion_xp80c.py   (sin ventana de consola)
  python  agente_impresion_xp80c.py   (con consola para depuracion)
==========================================================
"""

import os
import sys
import json
import time
import datetime
import logging

# ──────────────────────────────────────────────
# CONFIGURACION DEL AGENTE
# ──────────────────────────────────────────────
DEFAULT_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
DEFAULT_SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def cargar_credenciales():
    url = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    key = os.environ.get("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)
    
    # Buscar secrets.toml si existe localmente para sobrescribir
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    secrets_paths = [
        os.path.join(base_dir, ".streamlit", "secrets.toml"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), ".streamlit", "secrets.toml"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml")
    ]
    for sp in secrets_paths:
        if os.path.exists(sp):
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("SUPABASE_URL"):
                            url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("SUPABASE_KEY"):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
            except Exception as e:
                log.error("Error al leer secrets.toml: " + str(e))
    return url, key

SUPABASE_URL, SUPABASE_KEY = cargar_credenciales()

# Nombre de la impresora en Windows (dejar "" para auto-detectar XP-80C o usar predeterminada)
NOMBRE_IMPRESORA = ""

# Intervalo de consulta en segundos
INTERVALO_SEGUNDOS = 3

# Directorio de trabajo seguro (tanto si corre como script o como .exe congelado)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

# Archivo donde se guarda el ultimo ID impreso
ESTADO_FILE = os.path.join(APP_DIR, "estado_agente.json")

# Log
LOG_FILE = os.path.join(APP_DIR, "agente_impresion.log")


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("agente")


# ──────────────────────────────────────────────
# UTILIDADES DE TEXTO
# ──────────────────────────────────────────────
def limpiar_para_ticket(texto):
    """Elimina tildes y caracteres especiales para compatibilidad con la ticketera."""
    reemplazos = {
        '\xe1': 'a', '\xe9': 'e', '\xed': 'i', '\xf3': 'o', '\xfa': 'u',
        '\xc1': 'A', '\xc9': 'E', '\xcd': 'I', '\xd3': 'O', '\xda': 'U',
        '\xf1': 'n', '\xd1': 'N', '\xfc': 'u', '\xdc': 'U',
        '\xb0': ' ', '\xa0': ' ',
    }
    txt = str(texto).strip()
    for orig, limpio in reemplazos.items():
        txt = txt.replace(orig, limpio)
    # Eliminar cualquier caracter no-ASCII restante
    txt = ''.join(c if ord(c) < 128 else '?' for c in txt)
    return txt


def truncar(texto, largo):
    """Trunca el texto al largo maximo permitido."""
    return texto[:largo] if len(texto) > largo else texto


# ──────────────────────────────────────────────
# COMANDOS ESC/POS PARA XP-80C
# ──────────────────────────────────────────────
ESC = b'\x1b'
GS  = b'\x1d'


def escpos_inicializar():
    """Reinicia la impresora al estado por defecto."""
    return ESC + b'@'


def escpos_alineacion(modo):
    """Alineacion: 'izquierda', 'centro', 'derecha'."""
    codigos = {'izquierda': 0, 'centro': 1, 'derecha': 2}
    return ESC + b'a' + bytes([codigos.get(modo, 0)])


def escpos_negrita(activa):
    return ESC + b'E' + bytes([1 if activa else 0])


def escpos_tamano(ancho=1, alto=1):
    """
    ancho, alto: 1 = normal, 2 = doble.
    GS ! n  donde n = (ancho-1)*16 + (alto-1)
    """
    ancho = max(1, min(ancho, 8))
    alto  = max(1, min(alto,  8))
    n = ((ancho - 1) << 4) | (alto - 1)
    return GS + b'!' + bytes([n])


def escpos_avanzar(lineas=3):
    """Avanza el papel N lineas."""
    return ESC + b'd' + bytes([lineas])


def escpos_cortar():
    """Corte parcial con pequeno margen extra (estandar XP-80C)."""
    return GS + b'V' + bytes([0x42, 0x05])


def construir_voucher(nombre, curso, motivo, fecha, hora):
    """
    Construye la secuencia de bytes ESC/POS para el justificativo de atraso.
    Disenado para rollo de 80mm con corte automatico.
    """
    ANCHO_MAX_DATO = 36
    escuela = "Escuela Villa Las Penas"

    nombre = limpiar_para_ticket(nombre)
    curso  = limpiar_para_ticket(curso)
    motivo = limpiar_para_ticket(motivo)

    # Dividir nombre en dos lineas si es muy largo
    nombre_lineas = []
    if len(nombre) <= ANCHO_MAX_DATO:
        nombre_lineas = [nombre]
    else:
        palabras = nombre.split()
        linea = ""
        for pal in palabras:
            if len(linea) + len(pal) + 1 <= ANCHO_MAX_DATO:
                linea += (" " + pal if linea else pal)
            else:
                nombre_lineas.append(linea)
                linea = pal
        if linea:
            nombre_lineas.append(linea)

    data = b''
    data += escpos_inicializar()

    # ENCABEZADO
    data += escpos_alineacion('centro')
    data += escpos_tamano(2, 2)
    data += escpos_negrita(True)
    data += b'JUSTIFICATIVO\n'
    data += escpos_tamano(1, 1)
    data += escpos_negrita(False)

    # Separador
    data += escpos_alineacion('izquierda')
    separador = ('-' * 32 + '\n').encode('ascii')
    data += separador

    # DATOS (tamano doble alto para mejor legibilidad)
    data += escpos_tamano(1, 2)
    data += escpos_negrita(True)

    primera_linea = True
    for linea in nombre_lineas:
        if primera_linea:
            data += ('Nombre: ' + linea + '\n').encode('ascii', errors='replace')
            primera_linea = False
        else:
            data += ('        ' + linea + '\n').encode('ascii', errors='replace')

    data += ('Curso:  ' + truncar(curso, ANCHO_MAX_DATO) + '\n').encode('ascii', errors='replace')
    data += ('Motivo: ' + truncar(motivo, ANCHO_MAX_DATO) + '\n').encode('ascii', errors='replace')
    data += ('Fecha:  ' + fecha + '\n').encode('ascii', errors='replace')
    data += ('Hora:   ' + hora + '\n').encode('ascii', errors='replace')

    data += escpos_negrita(False)
    data += escpos_tamano(1, 1)
    data += separador

    # PIE DE PAGINA
    data += escpos_alineacion('centro')
    data += escpos_negrita(True)
    data += escpos_tamano(1, 2)
    data += (escuela + '\n').encode('ascii', errors='replace')
    data += escpos_tamano(1, 1)
    data += escpos_negrita(False)

    # Avanzar y cortar
    data += escpos_avanzar(3)
    data += escpos_cortar()

    return data


# ──────────────────────────────────────────────
# IMPRESION EN WINDOWS (win32print)
# ──────────────────────────────────────────────
def obtener_nombre_impresora():
    """
    Detecta la impresora XP-80C en Windows.
    Si no la encuentra, usa la predeterminada.
    """
    import win32print

    if NOMBRE_IMPRESORA:
        return NOMBRE_IMPRESORA

    impresoras = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    )
    candidatos = ["XP-80", "XP-C80", "Xprinter", "POS-80", "80C", "Thermal", "Receipt"]
    for _, _, nombre, _ in impresoras:
        for c in candidatos:
            if c.lower() in nombre.lower():
                log.info("Impresora detectada: " + nombre)
                return nombre

    default_printer = win32print.GetDefaultPrinter()
    log.warning("XP-80C no encontrada. Usando predeterminada: '" + default_printer + "'")
    return default_printer


def imprimir_escpos(datos, nombre_impresora):
    """Envia bytes RAW a la impresora Windows. Devuelve True si tuvo exito."""
    try:
        import win32print
        hprinter = win32print.OpenPrinter(nombre_impresora)
        try:
            win32print.StartDocPrinter(hprinter, 1, ("Justificativo Atraso", None, "RAW"))
            try:
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, datos)
                win32print.EndPagePrinter(hprinter)
            finally:
                win32print.EndDocPrinter(hprinter)
        finally:
            win32print.ClosePrinter(hprinter)
        return True
    except Exception as e:
        log.error("Error al imprimir: " + str(e))
        return False


# ──────────────────────────────────────────────
# ESTADO PERSISTENTE (ultimo ID impreso)
# ──────────────────────────────────────────────
def cargar_estado():
    if os.path.exists(ESTADO_FILE):
        try:
            with open(ESTADO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"ultimo_id_impreso": 0}


def guardar_estado(estado):
    try:
        with open(ESTADO_FILE, 'w', encoding='utf-8') as f:
            json.dump(estado, f, indent=2)
    except Exception as e:
        log.error("No se pudo guardar estado: " + str(e))


# ──────────────────────────────────────────────
# CONEXION A SUPABASE (REST API NATIVA - CERO DEPENDENCIAS)
# ──────────────────────────────────────────────
import urllib.request
import urllib.error

def supabase_get(endpoint):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def test_conexion_supabase():
    try:
        supabase_get("registros?select=id&limit=1")
        return True, "OK"
    except Exception as e:
        return False, str(e)


def obtener_atrasos_nuevos(ultimo_id):
    endpoint = f"registros?tipo=eq.Atraso&id=gt.{ultimo_id}&select=id,fecha,hora,nombre,curso,motivo,tipo&order=id.asc"
    try:
        return supabase_get(endpoint)
    except Exception as e:
        log.error("Error al consultar Supabase: " + str(e))
        return []


def obtener_max_id_atraso():
    endpoint = "registros?tipo=eq.Atraso&select=id&order=id.desc&limit=1"
    try:
        data = supabase_get(endpoint)
        if data:
            return data[0].get("id", 0)
    except Exception as e:
        log.error("Error al obtener max id: " + str(e))
    return 0


# ──────────────────────────────────────────────
# BUCLE PRINCIPAL DEL AGENTE
# ──────────────────────────────────────────────
def main():
    log.info("=" * 55)
    log.info("  AGENTE DE IMPRESION ESC/POS - Escuela Villa Las Penas")
    log.info("=" * 55)
    log.info("Intervalo de consulta: " + str(INTERVALO_SEGUNDOS) + " segundos")
    log.info("Archivo de estado: " + ESTADO_FILE)

    # Detectar impresora
    try:
        nombre_impresora = obtener_nombre_impresora()
        log.info("Impresora activa: '" + nombre_impresora + "'")
    except ImportError:
        log.critical("pywin32 NO esta instalado. Ejecuta instalar_agente.bat primero.")
        sys.exit(1)
    except Exception as e:
        log.critical("Error al detectar impresora: " + str(e))
        sys.exit(1)

    # Conectar a Supabase (reintentar amigablemente si la red demora)
    while True:
        ok_sb, msg_sb = test_conexion_supabase()
        if ok_sb:
            log.info("Conexion a Supabase: OK")
            break
        else:
            log.warning("Esperando conexion con Supabase: " + msg_sb)
            time.sleep(3)

    primera_vez = not os.path.exists(ESTADO_FILE)
    estado = cargar_estado()
    if primera_vez:
        max_id = obtener_max_id_atraso()
        # En primera ejecución retrocedemos 2 atrasos para recuperar los recién ingresados
        punto_inicio = max(0, max_id - 2)
        estado["ultimo_id_impreso"] = punto_inicio
        guardar_estado(estado)
        log.info("Primera ejecucion: sincronizado desde ID=" + str(punto_inicio) + " (ultimo existente ID=" + str(max_id) + ")")
    else:
        log.info("Ultimo ID impreso: " + str(estado['ultimo_id_impreso']))

    log.info("Agente en marcha. Esperando atrasos nuevos...\n")

    while True:
        try:
            atrasos = obtener_atrasos_nuevos(estado["ultimo_id_impreso"])
            for reg in atrasos:
                rid    = reg.get("id", 0)
                nombre = str(reg.get("nombre", "ALUMNO"))
                curso  = str(reg.get("curso", "") or "")
                motivo = str(reg.get("motivo", "Atraso") or "Atraso")
                fecha  = str(reg.get("fecha", ""))
                hora   = str(reg.get("hora", ""))[:5]

                # Reformatear fecha de YYYY-MM-DD a DD/MM/YYYY
                try:
                    dt = datetime.datetime.strptime(fecha, "%Y-%m-%d")
                    fecha = dt.strftime("%d/%m/%Y")
                except Exception:
                    pass

                log.info("Imprimiendo ID=" + str(rid) + ": " + nombre + " (" + curso + ") - " + motivo)

                datos = construir_voucher(nombre, curso, motivo, fecha, hora)
                ok = imprimir_escpos(datos, nombre_impresora)

                if ok:
                    estado["ultimo_id_impreso"] = rid
                    guardar_estado(estado)
                    log.info("  -> Impresion OK. Estado actualizado a ID=" + str(rid))
                else:
                    log.error("  -> Fallo de impresion. Se reintentara en el proximo ciclo.")
                    break

        except KeyboardInterrupt:
            log.info("Agente detenido por el usuario.")
            break
        except Exception as e:
            log.error("Error inesperado en el ciclo principal: " + str(e))

        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    if "--test" in sys.argv:
        nombre_imp = obtener_nombre_impresora()
        print("Imprimiendo voucher de prueba en:", nombre_imp)
        datos = construir_voucher("ALUMNO DE PRUEBA", "4 Básico A", "Prueba de Impresion", "23/10/2026", "12:00")
        exito = imprimir_escpos(datos, nombre_imp)
        print("Resultado prueba:", "EXITOSA" if exito else "FALLIDA")
        sys.exit(0)
    main()
