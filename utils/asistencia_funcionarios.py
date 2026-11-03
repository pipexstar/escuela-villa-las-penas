"""
utils/asistencia_funcionarios.py — Módulo de Control de Asistencia para Funcionarios
Integrado con Supabase (PostgreSQL) para la Escuela Villa Las Peñas.
"""

import os
import io
import hmac
import hashlib
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
import qrcode
import base64
import toml
from supabase import create_client


TABLA_EVENTOS = "asistencia_funcionarios_eventos"
SECRET_KEY_ASISTENCIA = "eavlp_control_asistencia_secret_2026"

_supabase_cache = None


def obtener_supabase_seguro():
    """Obtiene el cliente de Supabase, compatible tanto dentro como fuera de Streamlit."""
    global _supabase_cache
    if _supabase_cache is not None:
        return _supabase_cache

    # 1. Intentar por st.secrets si estamos en contexto de Streamlit activo
    try:
        if hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
            from utils.database import get_supabase_client
            _supabase_cache = get_supabase_client()
            return _supabase_cache
    except Exception:
        pass

    # 2. Fallback leyendo directamente el archivo secrets.toml
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sec_path = os.path.join(base_dir, ".streamlit", "secrets.toml")
        if os.path.exists(sec_path):
            sec = toml.load(sec_path)
            _supabase_cache = create_client(sec["SUPABASE_URL"], sec["SUPABASE_KEY"])
            return _supabase_cache
    except Exception as e:
        print(f"[asistencia] Fallback supabase error: {e}")

    from utils.database import get_supabase_client
    _supabase_cache = get_supabase_client()
    return _supabase_cache


# ─────────────────────────────────────────────────────────────────────────────
# SEGURIDAD CRIPTOGRÁFICA Y QR DINÁMICO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_firma(funcionario_id: str, fecha_yyyymmdd: str) -> str:
    """Calcula la firma HMAC-SHA256 para verificar la autenticidad del QR diario."""
    key_str = SECRET_KEY_ASISTENCIA
    try:
        if hasattr(st, "secrets") and "QR_SECRET_KEY" in st.secrets:
            key_str = st.secrets["QR_SECRET_KEY"]
    except Exception:
        pass
    key = key_str.encode("utf-8")
    msg = f"{funcionario_id.strip()}:{fecha_yyyymmdd.strip()}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]


def generar_payload(funcionario_id: str, fecha_yyyymmdd: str = None) -> str:
    """Genera el texto que codifica el QR: FUNCIONARIO:{rut}:{fecha}:{firma}"""
    if not fecha_yyyymmdd:
        fecha_yyyymmdd = date.today().strftime("%Y%m%d")
    else:
        fecha_yyyymmdd = str(fecha_yyyymmdd).replace("-", "")
    firma = calcular_firma(funcionario_id, fecha_yyyymmdd)
    return f"FUNCIONARIO:{funcionario_id.strip()}:{fecha_yyyymmdd}:{firma}"


def verificar_payload(payload: str) -> tuple[bool, str, dict]:
    """
    Verifica un código QR escaneado:
    1. Formato válido
    2. Fecha = hoy (evita pantallazos de días pasados)
    3. Firma digital auténtica
    """
    if not payload:
        return False, "Código QR vacío.", {}

    partes = str(payload).strip().split(":")
    if len(partes) < 3 or partes[0].upper() != "FUNCIONARIO":
        return False, "Código QR no reconocido por el sistema.", {}

    funcionario_id = partes[1].strip()
    fecha_qr = partes[2].strip().replace("-", "")
    fecha_hoy = date.today().strftime("%Y%m%d")

    if fecha_qr != fecha_hoy:
        fecha_qr_fmt = f"{fecha_qr[:4]}-{fecha_qr[4:6]}-{fecha_qr[6:]}" if len(fecha_qr) == 8 else fecha_qr
        return False, f"Código QR expirado (fecha del QR: {fecha_qr_fmt}, hoy: {date.today()}). Debe generar el QR de hoy.", {}

    if len(partes) >= 4:
        firma_qr = partes[3].strip()
        firma_esperada = calcular_firma(funcionario_id, fecha_qr)
        if not hmac.compare_digest(firma_qr, firma_esperada):
            return False, "Código QR alterado o firma criptográfica no válida.", {}

    return True, "QR válido", {"funcionario_id": funcionario_id, "fecha": fecha_qr}


def generar_qr_data_url(funcionario_id: str) -> str:
    """Genera una imagen QR en Base64 para mostrar en pantalla."""
    payload = generar_payload(funcionario_id)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


# ─────────────────────────────────────────────────────────────────────────────
# OPERACIONES DE BASE DE DATOS (SUPABASE)
# ─────────────────────────────────────────────────────────────────────────────

def verificar_tabla_eventos_existe() -> bool:
    """Comprueba si la tabla de eventos existe en Supabase."""
    try:
        client = obtener_supabase_seguro()
        client.table(TABLA_EVENTOS).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def registrar_evento_asistencia(funcionario_id: str, tipo_deseado: str = "auto") -> dict:
    """
    Registra entrada o salida en Supabase aplicando la regla de negocio:
    - 1 ENTRADA y 1 SALIDA por funcionario al día.
    - Si ya marcó entrada, está 'EN RECINTO' (protege contra salida accidental si < 20 min).
    - Una vez registrada la salida, la jornada del día queda completada.
    """
    funcionario_id = funcionario_id.strip()
    client = obtener_supabase_seguro()

    # 1. Validar que el funcionario existe y está activo
    try:
        resp_f = client.table("funcionarios").select("rut, nombre, rol, estado").eq("rut", funcionario_id).limit(1).execute()
        if not resp_f.data:
            return {"ok": False, "mensaje": f"Funcionario con RUT {funcionario_id} no encontrado en la nómina.", "funcionario": None}
        funcionario = resp_f.data[0]
        if str(funcionario.get("estado", "")).lower() == "inactivo":
            return {"ok": False, "mensaje": f"El funcionario {funcionario['nombre']} figura como INACTIVO.", "funcionario": funcionario}
    except Exception as e:
        return {"ok": False, "mensaje": f"Error verificando funcionario en Supabase: {e}", "funcionario": None}

    # 2. Consultar eventos de HOY para este funcionario
    hoy_iso = date.today().isoformat()
    try:
        resp_evs = client.table(TABLA_EVENTOS).select("*")\
            .eq("funcionario_id", funcionario_id)\
            .gte("timestamp", f"{hoy_iso}T00:00:00")\
            .lte("timestamp", f"{hoy_iso}T23:59:59")\
            .order("timestamp", desc=False).execute()
        eventos_hoy = resp_evs.data or []
    except Exception as e:
        return {"ok": False, "mensaje": f"Error consultando registros en Supabase: {e}. ¿Está creada la tabla '{TABLA_EVENTOS}'?", "funcionario": funcionario}

    entrada_hoy = next((e for e in eventos_hoy if e["tipo"] == "entrada"), None)
    salida_hoy = next((e for e in reversed(eventos_hoy) if e["tipo"] == "salida"), None)

    # Protección anti-rebote (10 segundos)
    if eventos_hoy:
        ultimo = eventos_hoy[-1]
        try:
            ts_str = str(ultimo["timestamp"]).replace("Z", "+00:00")
            dt_ultimo = datetime.fromisoformat(ts_str).replace(tzinfo=None)
            dif_seg = (datetime.now() - dt_ultimo).total_seconds()
            if dif_seg < 10:
                return {
                    "ok": False,
                    "mensaje": f"Marcaje muy reciente ({int(dif_seg)}s). Espere unos segundos.",
                    "anti_rebote": True,
                    "funcionario": funcionario,
                    "evento": ultimo,
                }
        except Exception:
            pass

    modo = tipo_deseado.lower() if tipo_deseado else "auto"

    # REGLA 1: Jornada de hoy ya completada
    if entrada_hoy and salida_hoy:
        t_in = str(entrada_hoy["timestamp"])[11:19]
        t_out = str(salida_hoy["timestamp"])[11:19]
        return {
            "ok": False,
            "mensaje": f"Jornada de hoy completada. Entrada: {t_in} — Salida: {t_out}.",
            "jornada_completada": True,
            "funcionario": funcionario,
            "evento": salida_hoy,
        }

    # REGLA 2: No tiene entrada hoy
    if not entrada_hoy:
        if modo == "salida":
            return {
                "ok": False,
                "mensaje": "No tienes una entrada registrada hoy para marcar salida.",
                "funcionario": funcionario,
            }
        tipo_final = "entrada"

    # REGLA 3: Ya tiene entrada hoy (está en el colegio)
    else:
        t_in = str(entrada_hoy["timestamp"])[11:19]
        try:
            ts_in_clean = str(entrada_hoy["timestamp"]).replace("Z", "+00:00")
            dt_in = datetime.fromisoformat(ts_in_clean).replace(tzinfo=None)
            minutos = (datetime.now() - dt_in).total_seconds() / 60.0
        except Exception:
            minutos = 999

        if modo == "entrada":
            return {
                "ok": False,
                "mensaje": f"Ya registraste tu entrada hoy a las {t_in}. Estado: EN RECINTO.",
                "ya_en_recinto": True,
                "funcionario": funcionario,
                "evento": entrada_hoy,
            }
        elif modo == "salida":
            tipo_final = "salida"
        else: # auto
            if minutos < 20:
                return {
                    "ok": False,
                    "mensaje": f"Ya estás en el colegio (Entrada: {t_in}). Para retirarte ahora selecciona 'Forzar Salida'.",
                    "ya_en_recinto": True,
                    "funcionario": funcionario,
                    "evento": entrada_hoy,
                }
            else:
                tipo_final = "salida"

    # 3. Guardar registro en Supabase
    ahora_dt = datetime.now()
    ahora_iso = ahora_dt.isoformat(timespec="seconds")
    try:
        nuevo_evento = {
            "funcionario_id": funcionario_id,
            "tipo": tipo_final,
            "timestamp": ahora_iso,
        }
        res_ins = client.table(TABLA_EVENTOS).insert(nuevo_evento).execute()
        evento_guardado = res_ins.data[0] if res_ins.data else nuevo_evento

        hora_bonita = ahora_dt.strftime("%H:%M:%S")
        msg = (
            f"¡Bienvenido/a! ENTRADA registrada a las {hora_bonita}."
            if tipo_final == "entrada"
            else f"¡Hasta pronto! SALIDA registrada a las {hora_bonita}. Jornada finalizada."
        )
        return {
            "ok": True,
            "tipo": tipo_final,
            "mensaje": msg,
            "funcionario": funcionario,
            "evento": evento_guardado,
        }
    except Exception as e:
        return {"ok": False, "mensaje": f"Error insertando evento en Supabase: {e}", "funcionario": funcionario}


def procesar_escaneo_qr_supabase(payload: str, tipo_deseado: str = "auto") -> dict:
    """Valida el QR firmado y ejecuta el registro en Supabase."""
    valido, msg_val, datos = verificar_payload(payload)
    if not valido:
        return {"ok": False, "mensaje": msg_val, "funcionario": None, "evento": None}
    return registrar_evento_asistencia(datos["funcionario_id"], tipo_deseado=tipo_deseado)


def listar_eventos_asistencia(fecha_desde: date = None, fecha_hasta: date = None, funcionario_id: str = None) -> list:
    """Consulta el historial de eventos en Supabase filtrado por rango de fechas."""
    client = obtener_supabase_seguro()
    try:
        q = client.table(TABLA_EVENTOS).select("*")
        if fecha_desde:
            q = q.gte("timestamp", f"{fecha_desde.isoformat()}T00:00:00")
        if fecha_hasta:
            q = q.lte("timestamp", f"{fecha_hasta.isoformat()}T23:59:59")
        if funcionario_id:
            q = q.eq("funcionario_id", funcionario_id.strip())
        res = q.order("timestamp", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"[asistencia_funcionarios] Error al listar eventos: {e}")
        return []


def construir_planilla_asistencia(eventos: list, funcionarios_dict: dict) -> list:
    """
    Agrupa eventos crudos en filas claras de jornada:
    Fecha, RUT, Nombre, Rol, Hora Entrada, Hora Salida, Estado
    """
    grupos = {}
    for ev in eventos:
        fid = ev["funcionario_id"]
        ts = str(ev.get("timestamp") or "")
        fec = ts[:10]
        grupos.setdefault((fid, fec), []).append(ev)

    filas = []
    for (fid, fec), lista in grupos.items():
        lista.sort(key=lambda x: str(x.get("timestamp") or ""))
        f_info = funcionarios_dict.get(fid, {})
        nom = f_info.get("nombre", fid)
        rol = f_info.get("rol", "Funcionario")

        e_in = next((e for e in lista if e["tipo"] == "entrada"), None)
        e_out = next((e for e in reversed(lista) if e["tipo"] == "salida"), None)

        h_in = str(e_in["timestamp"])[11:19] if e_in else ""
        h_out = str(e_out["timestamp"])[11:19] if e_out else ""

        if h_in and h_out:
            estado = "Jornada Completa"
        elif h_in and not h_out:
            estado = "En Recinto"
        else:
            estado = "Solo Salida"

        filas.append({
            "Fecha": fec,
            "RUT": fid,
            "Nombre": nom,
            "Rol": rol,
            "Hora de Entrada": h_in,
            "Hora de Salida": h_out,
            "Estado": estado,
            "_sort": f"{fec} {h_in or h_out}"
        })

    filas.sort(key=lambda x: x["_sort"], reverse=True)
    for f in filas:
        f.pop("_sort", None)
    return filas
