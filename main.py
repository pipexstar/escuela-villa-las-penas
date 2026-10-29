import streamlit as st
import pandas as pd
import datetime
import base64
import os
import io
import time
import re
from utils.database import get_sheets, get_asistencia_sheet, get_config_sheet, get_preacta_sheet, get_desarrollo_personal_sheet, get_cursos_sheet
from decimal import Decimal, ROUND_HALF_UP

# Configuración inicial (Debe ser el primer comando de Streamlit)
st.set_page_config(page_title="Dashboard Escolar", page_icon="🏫", layout="wide")

def redondear_nota(valor, decimales=1):
    """
    Redondeo estándar educacional (ROUND_HALF_UP / Decreto 67 de Evaluación Escolar).
    Aproxima 0.05 o superior a la décima superior (ej: 6.25 -> 6.3, 4.45 -> 4.5).
    Reemplaza el 'banker's rounding' nativo de Python que truncaba 6.25 a 6.2.
    """
    if valor is None:
        return 0.0
    try:
        val_float = float(valor)
        d = Decimal(f"{val_float:.6f}")
        factor = Decimal('10') ** -decimales
        return float(d.quantize(factor, rounding=ROUND_HALF_UP))
    except Exception:
        return float(valor)

def nota_a_concepto(val):
    """
    Convierte cualquier valor cuantitativo (ej: 7.0, 6.5, 5.0) o cualitativo a la escala conceptual oficial chilena:
    - 6.0 a 7.0 -> MB (Muy Bueno)
    - 5.0 a 5.9 -> B (Bueno)
    - 4.0 a 4.9 -> S (Suficiente)
    - 1.0 a 3.9 -> I (Insuficiente)
    Si ya es un concepto válido (I, S, B, MB) lo preserva limpio en mayúscula.
    """
    if val is None:
        return ""
    s = str(val).strip().upper()
    if not s or s in ("—", "-", "NONE", "NAN", "NULL"):
        return ""
    if s in ("MB", "B", "S", "I"):
        return s
    if "MUY BUENO" in s: return "MB"
    if "BUENO" in s: return "B"
    if "SUFICIENTE" in s: return "S"
    if "INSUFICIENTE" in s: return "I"
    try:
        num = float(s.replace(',', '.'))
        if 10.0 <= num <= 70.0:
            num = num / 10.0
        if num >= 6.0: return "MB"
        if num >= 5.0: return "B"
        if num >= 4.0: return "S"
        if num >= 1.0: return "I"
    except Exception:
        pass
    return s

def concepto_a_numero_db(val):
    """
    Convierte un concepto oficial (MB, B, S, I) a su valor numérico estándar representativo
    para almacenar en columnas de base de datos de tipo 'numeric':
    - MB -> 7.0
    - B  -> 5.5
    - S  -> 4.5
    - I  -> 3.0
    """
    if val is None or str(val).strip() in ("", "-", "None", "nan"):
        return None
    c = str(val).strip().upper()
    if c == "MB": return 7.0
    if c == "B": return 5.5
    if c == "S": return 4.5
    if c == "I": return 3.0
    try:
        n = float(c.replace(',', '.'))
        return n if 1.0 <= n <= 7.0 else None
    except Exception:
        return None

def apply_clean_theme():
    """
    Aplica el diseño limpio y minimalista solicitado:
    - Escala compacta estilo SaaS/ERP (aprovecha la pantalla sin scroll innecesario)
    - Fondo blanco y tarjetas sutiles
    - Tipografía ajustada y controlada
    - Inputs y selectores de menor altura
    - Detalles en el verde institucional (#008F39)
    """
    st.markdown("""
    <style>
    /* Fondo principal blanco */
    .stApp {
        background-color: #FFFFFF;
    }

    /* Ocultar barra flotante de herramientas en todas las tablas (descarga, búsqueda, pantalla completa) */
    [data-testid="stDataFrameToolbar"] {
        display: none !important;
    }

    /* Barra superior transparente para no tapar contenido pero manteniendo accesible el botón de abrir la barra lateral */
    header[data-testid="stHeader"] {
        background: transparent !important;
        color: inherit !important;
        height: 2.5rem !important;
        pointer-events: none;
    }
    header[data-testid="stHeader"] button,
    [data-testid="stSidebarCollapseButton"],
    button[data-testid="baseButton-header"],
    button[data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        pointer-events: auto !important;
        visibility: visible !important;
        display: inline-flex !important;
        opacity: 1 !important;
        z-index: 999999 !important;
    }

    .main .block-container, [data-testid="block-container"], [data-testid="stMainBlockContainer"] {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 98% !important;
    }
    
    /* Encabezados y títulos compactos con respiro para que no se corten */
    h1 {
        font-size: 1.45rem !important;
        font-weight: 700 !important;
        color: #1a5c32 !important;
        margin-top: 0 !important;
        margin-bottom: 0.35rem !important;
        line-height: 1.4 !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
        overflow: visible !important;
    }
    h2 {
        font-size: 1.20rem !important;
        font-weight: 600 !important;
        color: #222222 !important;
        margin-top: 0.4rem !important;
        margin-bottom: 0.3rem !important;
        line-height: 1.35 !important;
        padding: 2px 0 !important;
    }
    h3 {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        color: #333333 !important;
        margin-top: 0.3rem !important;
        margin-bottom: 0.2rem !important;
        line-height: 1.3 !important;
    }

    /* Separadores sutiles y cercanos */
    hr {
        margin: 0.4rem 0 0.8rem 0 !important;
        border-color: #f0f0f0 !important;
    }

    /* Estilos para el contenedor tipo Tarjeta (st.container con border=True) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px;
        border: 1px solid #EBEBEB;
        background-color: #FFFFFF;
        box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.03);
        transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out, border-color 0.15s;
        text-align: center;
        padding: 6px 8px !important;
    }
    
    /* Efecto al pasar el cursor (Hover) con el verde de la escuela */
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        box-shadow: 0px 4px 10px rgba(0, 143, 57, 0.08);
        border-color: #008F39; 
    }
    
    /* Tipografía compacta y de altura fija para títulos de las tarjetas del dashboard */
    .modulo-card-title {
        color: #1e293b;
        font-weight: 600;
        font-size: 0.84rem;
        margin: 0 !important;
        line-height: 1.25;
        height: 42px !important;
        min-height: 42px !important;
        max-height: 42px !important;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        overflow: hidden;
    }

    /* Subtítulos o descripciones con altura uniforme */
    .modulo-card-sub {
        color: #64748b;
        font-size: 0.72rem;
        line-height: 1.2;
        height: 32px !important;
        min-height: 32px !important;
        max-height: 32px !important;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        overflow: hidden;
        margin: 0 0 6px 0 !important;
        padding: 0 2px !important;
    }

    /* Contenedor bloqueado con exactamente la misma altura que los botones (34px) */
    .modulo-card-locked {
        width: 100%;
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 500;
        color: #94a3b8;
        background-color: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 6px;
        box-sizing: border-box;
        margin: 0 !important;
        padding: 0 4px !important;
    }
    
    /* Estilo minimalista y uniforme para botones */
    .stButton>button {
        width: 100%;
        height: 34px !important;
        min-height: 34px !important;
        padding: 2px 10px !important;
        font-size: 0.84rem !important;
        line-height: 1.3 !important;
        background-color: transparent;
        color: #008F39;
        border: 1.5px solid #008F39;
        border-radius: 6px;
        font-weight: 600;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease;
    }
    
    .stButton>button:hover {
        background-color: #008F39;
        color: #FFFFFF;
        border: 1.5px solid #008F39;
    }

    /* Botones primarios */
    .stButton>button[kind="primary"], .stButton>button[data-testid="baseButton-primary"] {
        background-color: #008F39 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stButton>button[kind="primary"]:hover, .stButton>button[data-testid="baseButton-primary"]:hover {
        background-color: #006b2b !important;
    }

    /* Botón de escape/volver más sobrio, cómodo y sin cortes */
    .btn-volver-container .stButton>button {
        height: 34px !important;
        min-height: 34px !important;
        padding: 2px 12px !important;
        font-size: 0.82rem !important;
        border-color: #718096 !important;
        color: #4A5568 !important;
        background-color: #F7FAFC !important;
    }
    .btn-volver-container .stButton>button:hover {
        background-color: #4A5568 !important;
        color: #FFFFFF !important;
        border-color: #4A5568 !important;
    }

    /* Reducción de altura y márgenes de inputs y selectboxes */
    div[data-testid="stTextInput"] input, 
    div[data-testid="stDateInput"] input,
    div[data-testid="stSelectbox"] div[role="combobox"] {
        min-height: 32px !important;
        height: 32px !important;
        font-size: 0.85rem !important;
        padding-top: 2px !important;
        padding-bottom: 2px !important;
        border-radius: 6px !important;
    }
    div[data-testid="stWidgetLabel"] p {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        margin-bottom: 2px !important;
        color: #333333 !important;
    }

    /* Bloqueo de edición manual en listas desplegables (stSelectbox) */
    div[data-testid="stSelectbox"] input {
        caret-color: transparent !important;
        cursor: pointer !important;
        user-select: none !important;
        -webkit-user-select: none !important;
    }
    div[data-testid="stSelectbox"] div[role="combobox"] {
        cursor: pointer !important;
    }

    /* Espaciado más compacto entre filas verticales de Streamlit */
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Inyectar el CSS
apply_clean_theme()

# ==========================================
# GESTIÓN OFICIAL DE FECHA Y HORA CHILE
# ==========================================
def obtener_ahora_chile() -> datetime.datetime:
    """Devuelve la fecha y hora oficial de Chile (America/Santiago con soporte horario verano/invierno)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("America/Santiago"))
    except Exception:
        # Fallback inteligente si zoneinfo o tzdata no están disponibles
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        m = utc_now.month
        # Regla general Chile continental: UTC-4 en invierno (mayo a agosto inclusive), UTC-3 en verano
        if 5 <= m <= 8:
            offset_hours = -4
        elif m == 4:
            offset_hours = -4 if utc_now.day >= 7 else -3
        elif m == 9:
            offset_hours = -3 if utc_now.day >= 7 else -4
        else:
            offset_hours = -3
        return utc_now.astimezone(datetime.timezone(datetime.timedelta(hours=offset_hours)))

# Keep-alive heartbeat silencioso en cliente para evitar suspensión de pestañas
try:
    import streamlit.components.v1 as _comp_v1
    _comp_v1.html("""
    <script>
    if (!window._stKeepAliveRunning) {
        window._stKeepAliveRunning = true;
        setInterval(function() {
            try {
                var el = document.getElementById('st-keepalive-ping');
                if (!el) {
                    el = document.createElement('div');
                    el.id = 'st-keepalive-ping';
                    el.style.display = 'none';
                    document.body.appendChild(el);
                }
                el.innerText = Date.now().toString();
            } catch(e) {}
        }, 30000);
    }
    </script>
    """, height=0, width=0)
except Exception:
    pass

# =========================================================================
# GESTIÓN CENTRALIZADA DE ROLES Y MATRIZ DE PERMISOS DE MÓDULOS
# =========================================================================
ROLES_TODOS = ["Director", "Jefe UTP", "Profesor", "Inspector", "Administrador Total", "Secretaria"]
ROLES_CONFIGURABLES = ["Director", "Jefe UTP", "Profesor", "Inspector", "Secretaria"]

MODULOS_SISTEMA = [
    {"id": "atraso", "titulo": "Registro Atraso", "sub": "Ingreso y comprobantes"},
    {"id": "retiro", "titulo": "Registro Retiro", "sub": "Salidas anticipadas"},
    {"id": "asistencia", "titulo": "Asistencia", "sub": "Control diario escolar"},
    {"id": "notas", "titulo": "Carga de Notas", "sub": "Registro y promedios"},
    {"id": "desarrollo_personal", "titulo": "Desarrollo Personal", "sub": "Informe y observaciones"},
    {"id": "asignaciones", "titulo": "Asignación Docente", "sub": "Asignaturas y docentes"},
    {"id": "preacta", "titulo": "Preacta Anual", "sub": "Promoción Decreto 67"},
    {"id": "informes", "titulo": "Informes y Certificados", "sub": "Notas y certificados"},
    {"id": "alumnos", "titulo": "Alumnos", "sub": "Fichas y nómina escolar"},
    {"id": "cursos", "titulo": "Cursos", "sub": "Catálogo y jefaturas"},
    {"id": "funcionarios", "titulo": "Funcionarios", "sub": "Personal y accesos"},
    {"id": "configuracion", "titulo": "Configuración", "sub": "Colegio, firmas y fechas"}
]

TODOS_MODULOS_IDS = [m["id"] for m in MODULOS_SISTEMA]

DEFAULT_PERMISOS_ROLES = {
    "Director": TODOS_MODULOS_IDS.copy(),
    "Jefe UTP": TODOS_MODULOS_IDS.copy(),
    "Profesor": ["notas", "asistencia", "informes", "desarrollo_personal"],
    "Inspector": ["atraso", "retiro", "asistencia", "alumnos"],
    "Secretaria": ["alumnos", "funcionarios", "retiro", "atraso", "informes"]
}

def normalizar_nombre_rol(rol_raw):
    """Estandariza cualquier variante del rol a su denominación oficial."""
    r = str(rol_raw or "").strip().lower()
    if "admin" in r:
        return "Administrador Total"
    if "director" in r:
        return "Director"
    if "utp" in r:
        return "Jefe UTP"
    if "profesor" in r or "docente" in r:
        return "Profesor"
    if "inspector" in r:
        return "Inspector"
    if "secretari" in r:
        return "Secretaria"
    return str(rol_raw or "").strip().title()

def obtener_matriz_permisos(sheet_config=None):
    """Carga la matriz de permisos desde sheet_config o usa DEFAULT_PERMISOS_ROLES."""
    import json
    if sheet_config:
        try:
            records = sheet_config.get_all_records()
            for r in records:
                k = str(r.get("Clave", "")).strip()
                if k == "matriz_permisos_roles":
                    val = str(r.get("Valor", "")).strip()
                    if val:
                        matriz_guardada = json.loads(val)
                        matriz_completa = {}
                        for r_cfg in ROLES_CONFIGURABLES:
                            if r_cfg in matriz_guardada:
                                matriz_completa[r_cfg] = matriz_guardada[r_cfg]
                            else:
                                matriz_completa[r_cfg] = DEFAULT_PERMISOS_ROLES.get(r_cfg, []).copy()
                        return matriz_completa
        except Exception:
            pass
    return {k: v.copy() for k, v in DEFAULT_PERMISOS_ROLES.items()}

def rol_tiene_permiso(rol_usuario, modulo_id, matriz_permisos=None):
    """Evalúa si un rol tiene acceso a un módulo determinado."""
    if not rol_usuario:
        return False
    rol_norm = normalizar_nombre_rol(rol_usuario)
    if rol_norm == "Administrador Total":
        return True
    if matriz_permisos is None:
        matriz_permisos = DEFAULT_PERMISOS_ROLES
    permisos_rol = matriz_permisos.get(rol_norm, DEFAULT_PERMISOS_ROLES.get(rol_norm, []))
    return modulo_id in permisos_rol

# ==========================================
# FUNCIÓN DE LIMPIEZA UNIVERSAL
# ==========================================
def limpiar_universal_ticketera(texto):
    reemplazos = {
        'á': 'A', 'é': 'E', 'í': 'I', 'ó': 'O', 'ú': 'U',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'N', 'Ñ': 'N', 'ü': 'U', 'Ü': 'U',
        '°': ' '
    }
    txt = str(texto)
    for original, limpio in reemplazos.items():
        txt = txt.replace(original, limpio)
    return txt.upper().strip()

# =========================================================================
# LÓGICA CENTRALIZADA DE CURSOS INSTITUCIONALES (CERO DUPLICADOS)
# =========================================================================
def normalizar_cadena_curso(texto):
    if not texto: return ""
    t = str(texto).strip().lower()
    t = t.replace('°', '').replace('º', '').replace('.', '')
    t = t.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    return " ".join(t.split())

def extraer_clave_curso(texto):
    """Devuelve tupla (nivel_norm, letra_norm) para deduplicación estricta."""
    norm = normalizar_cadena_curso(texto)
    partes = norm.split()
    if not partes:
        return ("", "a")
    if len(partes) > 1 and partes[-1] in ['a', 'b', 'c', 'd']:
        nivel = " ".join(partes[:-1])
        letra = partes[-1]
    else:
        nivel = norm
        letra = "a"

    # Erradicar Prekinder y Kinder convirtiéndolos obligatoriamente a NT1 y NT2
    if any(x in nivel for x in ['prekinder', 'pre-kinder', 'pre kinder', 'prek', 'pre-k']):
        nivel = "nt1"
    elif any(x in nivel for x in ['kinder', 'kndr']) and 'pre' not in nivel:
        nivel = "nt2"
    elif nivel in ['nt 1', 'nt-1', 'transicion 1', 'primer nivel de transicion']:
        nivel = "nt1"
    elif nivel in ['nt 2', 'nt-2', 'transicion 2', 'segundo nivel de transicion']:
        nivel = "nt2"

    return (nivel, letra)

def calza_nombre_curso(c_al, c_sel):
    if not c_al or not c_sel: return False
    if str(c_sel).strip() == "🔍 Todos los Cursos": return True
    return extraer_clave_curso(c_al) == extraer_clave_curso(c_sel)

NIVELES_ORDEN_PEDAGOGICO = ["nt1", "nt2", "1 basico", "2 basico", "3 basico", "4 basico", "5 basico", "6 basico", "7 basico", "8 basico"]

def orden_curso_sistema(nom_c):
    k = extraer_clave_curso(nom_c)
    idx_n = NIVELES_ORDEN_PEDAGOGICO.index(k[0]) if k[0] in NIVELES_ORDEN_PEDAGOGICO else 90
    return (idx_n, k[1])

def obtener_cursos_oficiales_sistema():
    """
    Obtiene la lista oficial, única y ordenada de cursos directamente desde el módulo de Cursos (Google Sheets).
    Asegura que todos los módulos (Informes, Desarrollo Personal, Alumnos, Notas, etc.) utilicen la misma fuente de verdad.
    """
    if 'cursos_oficiales_cache' in st.session_state and st.session_state.cursos_oficiales_cache:
        return list(st.session_state.cursos_oficiales_cache)

    cursos_encontrados = []
    try:
        sheet_c = get_cursos_sheet()
        if sheet_c:
            recs = sheet_c.get_all_records()
            if recs:
                df_c = pd.DataFrame(recs)
                if not df_c.empty:
                    df_c.columns = [str(c).strip() for c in df_c.columns]
                    col_n = next((c for c in df_c.columns if 'nomb' in c.lower() or 'curs' in c.lower()), 'Nombre')
                    col_l = next((c for c in df_c.columns if 'let' in c.lower()), 'Letra')
                    col_est = next((c for c in df_c.columns if 'est' in c.lower()), None)
                    if col_est:
                        df_c = df_c[df_c[col_est].astype(str).str.lower() != 'inactivo']

                    for _, r in df_c.iterrows():
                        nom = str(r.get(col_n, '')).strip()
                        let = str(r.get(col_l, 'A')).strip() or 'A'
                        if nom:
                            k = extraer_clave_curso(nom)
                            if k[0] == 'nt1':
                                nom_final = f"NT1 {let.upper()}"
                            elif k[0] == 'nt2':
                                nom_final = f"NT2 {let.upper()}"
                            elif not nom.endswith(let):
                                nom_final = f"{nom} {let.upper()}".strip()
                            else:
                                nom_final = nom
                            cursos_encontrados.append(nom_final)
    except Exception:
        pass

    if not cursos_encontrados:
        cursos_encontrados = [
            "NT1 A", "NT2 A",
            "1° Básico A", "2° Básico A", "3° Básico A", "4° Básico A",
            "5° Básico A", "6° Básico A", "7° Básico A", "8° Básico A"
        ]

    # Deduplicar preservando clave canónica
    dict_unicos = {}
    for c in cursos_encontrados:
        k = extraer_clave_curso(c)
        if k not in dict_unicos:
            dict_unicos[k] = c

    cursos_ordenados = sorted(list(dict_unicos.values()), key=orden_curso_sistema)
    st.session_state.cursos_oficiales_cache = cursos_ordenados
    return list(cursos_ordenados)

def obtener_profesor_jefe_curso(nom_curso, sheet_asignaciones=None):
    """
    Obtiene el nombre del Profesor(a) Jefe del curso directamente desde Cursos.
    """
    if not nom_curso:
        return "NO ASIGNADO"

    # 1. Buscar en catálogo de Cursos (fuente principal y oficial)
    try:
        sheet_c = get_cursos_sheet()
        if sheet_c:
            recs_c = sheet_c.get_all_records()
            for rc in recs_c:
                nom_c = str(rc.get("Nombre", "")).strip()
                if calza_nombre_curso(nom_c, nom_curso):
                    pj = str(rc.get("Profesor_Jefe", "")).strip()
                    if pj and pj != "— Sin Asignar —":
                        return pj
    except Exception:
        pass

    # 2. Respaldo en Asignaciones de Jefatura si existiese
    if sheet_asignaciones:
        try:
            recs_asig = sheet_asignaciones.get_all_records()
            for ra in recs_asig:
                if calza_nombre_curso(ra.get("Curso", ""), nom_curso) and str(ra.get("Asignatura", "")).strip().upper() == "JEFATURA":
                    prof_n = str(ra.get("Nombre_Profesor", "")).strip()
                    if prof_n and prof_n != "— Sin Asignar —":
                        return prof_n
        except Exception:
            pass

    return "NO ASIGNADO"

# ==========================================
# FUNCIÓN UNIVERSAL DE INSIGNIA
# ==========================================
def renderizar_insignia_universal():
    """
    La insignia institucional ahora reside de forma permanente y elegante en la barra lateral (sidebar),
    evitando cortes en pantallas y despejando el área de trabajo en los módulos.
    """
    pass


# Control de Versiones Estructurales para Evitar Caché Corrupto
APP_VERSION = "4.1"
if 'app_version' not in st.session_state or st.session_state.app_version != APP_VERSION:
    # Limpiamos todo el estado de sesión si hay cambios estructurales
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.app_version = APP_VERSION

# Inicializar estado de navegación sincronizado con la URL (query_params)
param_mod = st.query_params.get("m", "home")
if 'current_module' not in st.session_state:
    st.session_state.current_module = param_mod if param_mod else 'home'
    st.session_state['_previous_module'] = None
else:
    # Si la URL tiene un módulo distinto (por ejemplo botón Atrás/Adelante del navegador)
    if param_mod and param_mod != st.session_state.current_module:
        st.session_state['_previous_module'] = st.session_state.current_module
        st.session_state.current_module = param_mod

# ── Persistencia de Sesión de Usuario (Token en URL) ────────────────────────
def _generar_token_sesion(u_dict):
    try:
        raw = f"{u_dict['rut']}###{u_dict['nombre']}###{u_dict['rol']}###{u_dict['pin']}###{u_dict.get('estado','Activo')}"
        return base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8')
    except Exception:
        return ""

def _decodificar_token_sesion(token_str):
    try:
        raw = base64.urlsafe_b64decode(token_str.encode('utf-8')).decode('utf-8')
        partes = raw.split("###")
        if len(partes) >= 4:
            return {
                "rut": partes[0],
                "nombre": partes[1],
                "rol": partes[2],
                "pin": partes[3],
                "estado": partes[4] if len(partes) > 4 else "Activo"
            }
    except Exception:
        pass
    return None

if 'user' not in st.session_state:
    st.session_state.user = None

tok = st.query_params.get("u", "")
if tok and (st.session_state.user is None):
    u_recup = _decodificar_token_sesion(tok)
    if u_recup:
        st.session_state.user = u_recup

def navigate(module_name):
    """Navega a un módulo y actualiza la URL del navegador manteniendo la sesión."""
    _NOTAS_KEYS = [
        'notas_curso_sel', 'notas_asig_sel', 'notas_sem_seg',
        'notas_grilla_cargada', 'notas_curso_activo', 'notas_asig_activa', 'notas_sem_activo'
    ]
    # Si se sale del módulo de notas, limpiar toda la grilla
    if module_name != 'notas':
        for _k in _NOTAS_KEYS:
            st.session_state.pop(_k, None)
    st.session_state['_previous_module'] = st.session_state.get('current_module')
    st.session_state.current_module = module_name
    try:
        st.query_params["m"] = module_name
        if st.session_state.get('user'):
            st.query_params["u"] = _generar_token_sesion(st.session_state.user)
    except Exception:
        pass

def render_sidebar_auth():
    import os
    import base64
    rutas = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "insignia.png"),
        "insignia.png",
        "C:/SistemaEscolar/insignia.png"
    ]
    ruta_directa = next((r for r in rutas if os.path.exists(r)), None)
    if ruta_directa:
        try:
            with open(ruta_directa, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            st.sidebar.markdown(
                f"""
                <div style="text-align: center; padding: 10px 0 6px 0;">
                    <img src="data:image/png;base64,{img_b64}"
                         alt="Escuela Villa Las Peñas"
                         style="max-height: 90px; width: auto; object-fit: contain; display: inline-block;">
                </div>
                """,
                unsafe_allow_html=True
            )
        except Exception:
            pass

    st.sidebar.markdown("<h3 style='text-align:center;color:#1a5c32;font-size:1.15rem;margin:2px 0 10px 0;'>Escuela Villa Las Peñas</h3>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
    if st.session_state.user is None:
        st.sidebar.markdown(
            "<div style='text-align:center;color:#666;font-size:0.82rem;padding:6px;background:#f9fafb;border-radius:6px;border:1px solid #e5e7eb;'>"
            "🔒 <b>Sistema Bloqueado</b><br>Ingresa tus credenciales en la pantalla principal para acceder a los módulos.</div>",
            unsafe_allow_html=True
        )
    else:
        u = st.session_state.user
        st.sidebar.success(f"👤 **{u['nombre']}**\n\n🎭 **Rol:** `{u['rol']}`")
        
        with st.sidebar.expander("🔑 Cambiar Mi Clave"):
            with st.form("form_cambio_clave_user"):
                c_act = st.text_input("Clave Actual:", type="password", max_chars=4)
                c_nueva = st.text_input("Nueva Clave (4 dig):", type="password", max_chars=4)
                c_conf = st.text_input("Repetir Nueva Clave:", type="password", max_chars=4)
                b_cambio = st.form_submit_button("Actualizar Clave")
                
                if b_cambio:
                    if c_act != u['pin']:
                        st.error("La clave actual no coincide.")
                    elif len(c_nueva) != 4 or not c_nueva.isdigit():
                        st.error("La clave debe tener 4 números.")
                    elif c_nueva != c_conf:
                        st.error("Las nuevas claves no coinciden.")
                    else:
                        _, _, _, sheet_funcionarios, _ = get_sheets()
                        if sheet_funcionarios:
                            try:
                                cell = sheet_funcionarios.find(str(u['rut']))
                                if cell:
                                    sheet_funcionarios.update_cell(cell.row, 4, str(c_nueva))
                                    st.session_state.user['pin'] = str(c_nueva)
                                    st.success("✅ ¡Clave modificada exitosamente!")
                                    st.rerun()
                                else:
                                    st.error("No se encontró el registro de usuario.")
                            except Exception as e:
                                st.error(f"Error al guardar: {e}")

        if st.sidebar.button("🚪 Cerrar Sesión", key="btn_logout_user"):
            st.session_state.user = None
            st.session_state.current_module = 'home'
            try:
                st.query_params.clear()
            except Exception:
                pass
            # Limpiar cachés sensibles de la sesión
            for k in list(st.session_state.keys()):
                if k not in ['app_version', 'current_module']:
                    del st.session_state[k]
            st.session_state.user = None
            st.rerun()

# Inyectar barra lateral de autenticación
render_sidebar_auth()

# ---------------------------------------------------------
# PORTAL DE LOGIN CENTRALIZADO (SI NO HAY SESIÓN ACTIVA)
# ---------------------------------------------------------
if st.session_state.user is None:
    # No hay usuario autenticado: se renderizará el portal de login abajo y se detendrá la ejecución
    pass

    st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
    col_l1, col_login, col_l3 = st.columns([1.5, 2.8, 1.5])
    
    with col_login:
        with st.container(border=True):
            st.markdown(
                """
                <div style='text-align:center;padding:10px 0 6px 0;'>
                    <h2 style='color:#1a5c32;margin-bottom:2px;font-size:1.35rem;'>🏫 Escuela Villa Las Peñas</h2>
                    <p style='color:#666;font-size:0.84rem;margin-top:0;'>Portal de Acceso Institucional</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("<hr style='margin:4px 0 14px 0;border-color:#edf2f7;'>", unsafe_allow_html=True)
            
            with st.form("form_login_central"):
                rut_in = st.text_input("RUT o Nombre de Usuario:", placeholder="Ej: 12345678-9 o admin").strip()
                pin_in = st.text_input("Clave de Acceso (PIN 4 dígitos):", type="password", max_chars=4, placeholder="••••").strip()
                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                btn_ingresar = st.form_submit_button("🔐 Ingresar al Sistema", type="primary", use_container_width=True)

                if btn_ingresar:
                    if not rut_in or not pin_in:
                        st.error("⚠️ Por favor ingresa tu RUT / Usuario y Clave.")
                    else:
                        with st.spinner("Validando credenciales..."):
                            _, _, _, sheet_funcionarios, _ = get_sheets()
                            if sheet_funcionarios:
                                try:
                                    recs = sheet_funcionarios.get_all_records()
                                    df_f = pd.DataFrame(recs)
                                    if not df_f.empty:
                                        df_f['RUT_NORM'] = df_f['RUT'].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()
                                        search_rut = rut_in.replace('.', '').strip().lower()
                                        match = df_f[(df_f['RUT_NORM'] == search_rut) & (df_f['PIN'].astype(str).str.strip() == pin_in)]
                                        
                                        if not match.empty:
                                            row = match.iloc[0]
                                            if str(row.get('Estado', 'Activo')).strip().lower() == 'inactivo':
                                                st.error("⚠️ Usuario inactivo. Consulta con el Administrador.")
                                            else:
                                                st.session_state.user = {
                                                    "rut": str(row['RUT']).strip(),
                                                    "nombre": str(row['Nombre']).strip(),
                                                    "rol": str(row['Rol']).strip(),
                                                    "pin": str(row['PIN']).strip(),
                                                    "estado": str(row.get('Estado', 'Activo')).strip()
                                                }
                                                try:
                                                    st.query_params["u"] = _generar_token_sesion(st.session_state.user)
                                                except Exception:
                                                    pass
                                                st.success(f"¡Bienvenido/a {row['Nombre']}!")
                                                st.rerun()
                                        else:
                                            st.error("❌ RUT o Clave incorrectos.")
                                    else:
                                        st.error("No hay base de funcionarios registrada.")
                                except Exception as e:
                                    st.error(f"Error al verificar credenciales: {e}")
                            else:
                                st.error("❌ No hay conexión con la base de datos.")

            pass
    st.stop()

# ---------------------------------------------------------
# ---------------------------------------------------------
# MÓDULOS DE REPORTES INSTITUCIONALES (ATRASOS Y RETIROS)
# ---------------------------------------------------------

def parse_fecha_flexible(val):
    """Parsea fechas en diversos formatos estándar (DD-MM-YYYY, YYYY-MM-DD, etc.)."""
    if not val or pd.isna(val): return None
    if isinstance(val, datetime.date): return val
    if isinstance(val, datetime.datetime): return val.date()
    val_clean = str(val).strip()
    if val_clean.lower() in ('', 'nan', 'none', '—'): return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(val_clean.split()[0], fmt).date()
        except Exception:
            pass
    return None

def extraer_fechas_alumno(r_alu, f_inicio_oficial=None):
    """
    Extrae de forma robusta la fecha de ingreso (matricula o alta) y fecha de baja de un alumno.
    Soporta variaciones de nombre de columna con o sin tildes.
    Si la fecha de matricula/alta es posterior al inicio del semestre 1, se marca como ingreso tardio.
    """
    import unicodedata
    if not isinstance(r_alu, dict):
        try:
            r_alu = r_alu.to_dict()
        except Exception:
            r_alu = dict(r_alu)

    def norm_key(k):
        return ''.join(c for c in unicodedata.normalize('NFD', str(k).lower()) if unicodedata.category(c) != 'Mn')

    # 1. Buscar fecha de baja / retiro
    f_baja = None
    es_retirado = False
    for k, v in r_alu.items():
        k_n = norm_key(k)
        if ('baja' in k_n or 'retir' in k_n) and 'motiv' not in k_n and 'nac' not in k_n:
            val_b = str(v).strip()
            if val_b and val_b.lower() not in ('', 'nan', 'none', '-', 'nat', 'null'):
                parsed = parse_fecha_flexible(val_b)
                if parsed is not None:
                    es_retirado = True
                    f_baja = parsed
                    break

    # 2. Buscar fecha de matricula y fecha de alta / ingreso
    # Primero: búsqueda directa por nombre exacto (DB y display, con/sin tildes)
    # Esto garantiza detección correcta independiente del orden del dict
    f_mat = None
    f_alta = None

    # Nombres YA normalizados (sin tildes, minúsculas) — deben coincidir con norm_key(clave)
    _NOMBRES_MATRICULA = {
        'fecha_matricula',   # columna DB
        'fecha matricula',   # display normalizado (norm_key('Fecha Matrícula'))
        'fechamatricula',
        'f_matricula',
        'fec_matricula',
    }
    _NOMBRES_ALTA = {
        'fecha_ingreso',     # columna DB
        'fecha_alta',        # alternativa DB
        'fecha ingreso',     # display normalizado
        'fecha alta',        # display normalizado (norm_key('Fecha Alta'))
        'fechaingreso',
        'fechaalta',
        'f_ingreso',
        'f_alta',
        'fecha incorporacion',
    }

    for k, v in r_alu.items():
        k_n = norm_key(k)
        if k_n in _NOMBRES_MATRICULA:
            parsed = parse_fecha_flexible(v)
            if parsed is not None:
                f_mat = parsed
        elif k_n in _NOMBRES_ALTA:
            parsed = parse_fecha_flexible(v)
            if parsed is not None:
                f_alta = parsed

    # Fallback: si no se encontraron por nombre exacto, usar heurística de subcadenas
    if f_mat is None and f_alta is None:
        for k, v in r_alu.items():
            k_n = norm_key(k)
            if 'baja' in k_n or 'retir' in k_n or 'nac' in k_n:
                continue
            if 'fec' in k_n or 'date' in k_n or 'alta' in k_n or 'ingres' in k_n or 'incorpor' in k_n or 'matr' in k_n:
                parsed = parse_fecha_flexible(v)
                if parsed is None:
                    continue
                if 'matr' in k_n and f_mat is None:
                    f_mat = parsed
                elif ('alta' in k_n or 'ingres' in k_n or 'incorpor' in k_n) and f_alta is None:
                    f_alta = parsed

    # 3. Determinar fecha de ingreso al anio escolar (posterior al inicio oficial)
    anio_escolar = f_inicio_oficial.year if f_inicio_oficial else None
    f_ingreso = None

    if f_mat and f_inicio_oficial and f_mat > f_inicio_oficial:
        f_ingreso = f_mat
    elif f_alta and f_inicio_oficial and f_alta > f_inicio_oficial:
        f_ingreso = f_alta
    elif f_mat:
        f_ingreso = f_mat
    elif f_alta:
        f_ingreso = f_alta

    # Fallback: buscar en TODAS las columnas de fecha un valor del anio escolar > inicio oficial
    if f_ingreso is None and f_inicio_oficial and anio_escolar:
        candidatas = []
        for k, v in r_alu.items():
            k_n = norm_key(k)
            if 'baja' in k_n or 'retir' in k_n or 'nac' in k_n:
                continue
            parsed = parse_fecha_flexible(v)
            if parsed and parsed.year == anio_escolar and parsed > f_inicio_oficial:
                candidatas.append(parsed)
        if candidatas:
            f_ingreso = min(candidatas)

    # 4. Determinar fecha de inicio efectiva para el conteo de asistencia
    es_ingreso_tardio = False
    if f_inicio_oficial:
        if f_ingreso and f_ingreso > f_inicio_oficial:
            f_inicio_efectiva = f_ingreso
            es_ingreso_tardio = True
        else:
            f_inicio_efectiva = f_inicio_oficial
    else:
        f_inicio_efectiva = f_ingreso if f_ingreso else None

    return {
        "f_ingreso": f_ingreso,
        "f_inicio_efectiva": f_inicio_efectiva,
        "es_ingreso_tardio": es_ingreso_tardio,
        "f_baja": f_baja,
        "es_retirado": es_retirado
    }

def cargar_datos_configuracion_reportes():
    """Carga los parámetros institucionales oficiales desde la tabla de Configuración."""
    conf_data = {}
    try:
        sc_conf = get_config_sheet()
        if sc_conf:
            recs = sc_conf.get_all_records()
            for rc in recs:
                k = str(rc.get('clave', rc.get('Clave', ''))).strip().lower()
                v = str(rc.get('valor', rc.get('Valor', ''))).strip()
                if k: conf_data[k] = v
    except Exception:
        pass

    def parse_fecha(val_str, fallback):
        if not val_str: return fallback
        val_clean = str(val_str).strip()
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.datetime.strptime(val_clean.split()[0], fmt).date()
            except Exception:
                pass
        return fallback

    hoy = datetime.date.today()
    anio = hoy.year

    nombre_colegio = conf_data.get("nombre_colegio", "ESCUELA VILLA LAS PEÑAS").upper()
    rbd = conf_data.get("rbd", conf_data.get("rbd_colegio", "4410-5"))
    ciudad = conf_data.get("ciudad", "Mulchén")
    region = conf_data.get("region", "BÍOBÍO")
    nombre_director = conf_data.get("nombre_director", "CÉSAR JULIÁN ROA SOTO").upper()
    firma_b64 = conf_data.get("firma_director_b64", "")

    # Fechas oficiales de semestre desde configuración (con inicio de clases 04-03-2026)
    s1_ini = parse_fecha(conf_data.get("semestre_1_inicio"), datetime.date(anio, 3, 4))
    s1_fin = parse_fecha(conf_data.get("semestre_1_fin"), datetime.date(anio, 6, 18))
    s2_ini = parse_fecha(conf_data.get("semestre_2_inicio"), datetime.date(anio, 7, 6))
    s2_fin = parse_fecha(conf_data.get("semestre_2_fin"), datetime.date(anio, 12, 11))

    return {
        "nombre_colegio": nombre_colegio,
        "rbd": rbd,
        "ciudad": ciudad,
        "region": region,
        "nombre_director": nombre_director,
        "firma_b64": firma_b64,
        "s1_ini": s1_ini,
        "s1_fin": s1_fin,
        "s2_ini": s2_ini,
        "s2_fin": s2_fin
    }


def calcular_asistencia_estudiante(r_alu, df_asist_all, curso_alumno=None, periodo='anual', config_inst=None):
    """
    Calcula de forma exacta, uniforme e institucional la asistencia de un alumno para un periodo:
    - periodo: 's1' (1er Semestre), 's2' (2do Semestre) o 'anual' (Ano Completo).
    - Aplica fechas oficiales de inicio/fin de semestres institucionales.
    - Excluye estrictamente el receso escolar de invierno (vacaciones de invierno).
    - Excluye dias marcados como 'sin_clases' o 'sc'.
    - Respeta la fecha de matricula/ingreso efectiva si el alumno ingreso con posterioridad al inicio oficial.
    - Respeta la fecha de retiro/baja si el alumno se retiro antes del fin de periodo.
    - Devuelve dict con:
        dias_clase: total dias de clases que le correspondia asistir al estudiante en el periodo
        dias_asist: dias que efectivamente asistio
        dias_inasist: dias de inasistencia registrados
        pct_asist: porcentaje numerico float (ej: 98.1)
        pct_asist_fmt: porcentaje formateado chileno con coma (ej: '98,11')
        f_inicio_efectiva: date de inicio de conteo
        es_ingreso_tardio: bool
        es_retirado: bool
        f_baja: date o None
    """
    import unicodedata
    if not isinstance(r_alu, dict):
        try:
            r_alu = r_alu.to_dict()
        except Exception:
            r_alu = dict(r_alu)

    if curso_alumno is None:
        for k in r_alu.keys():
            if 'curs' in str(k).lower():
                curso_alumno = str(r_alu[k]).strip()
                break

    n_lista = None
    if '_ord' in r_alu:
        try:
            n_lista = int(r_alu['_ord'])
        except Exception:
            pass
    if n_lista is None:
        for k in r_alu.keys():
            k_l = str(k).lower()
            if any(x in k_l for x in ['list', 'orden', 'n°', 'nro']) and 'curs' not in k_l:
                try:
                    val_o = r_alu[k]
                    if val_o is not None and str(val_o).strip() != '':
                        n_lista = int(float(str(val_o).strip()))
                        break
                except Exception:
                    pass
    if n_lista is None:
        n_lista = 1

    hoy = datetime.date.today()
    s1_ini = config_inst.get('s1_ini', datetime.date(hoy.year, 3, 4)) if config_inst else datetime.date(hoy.year, 3, 4)
    s1_fin = config_inst.get('s1_fin', datetime.date(hoy.year, 6, 18)) if config_inst else datetime.date(hoy.year, 6, 18)
    s2_ini = config_inst.get('s2_ini', datetime.date(hoy.year, 7, 6)) if config_inst else datetime.date(hoy.year, 7, 6)
    s2_fin = config_inst.get('s2_fin', datetime.date(hoy.year, 12, 11)) if config_inst else datetime.date(hoy.year, 12, 11)

    f_info = extraer_fechas_alumno(r_alu, s1_ini)
    f_inicio_efectiva = f_info['f_inicio_efectiva'] or s1_ini
    f_baja_alu = f_info['f_baja']
    es_ingreso_tardio = f_info['es_ingreso_tardio']
    es_retirado = f_info['es_retirado']

    dias_clase = 0
    dias_inasist = 0

    if df_asist_all is not None and not df_asist_all.empty:
        col_c_y = next((c for c in df_asist_all.columns if 'curs' in c.lower()), 'Curso')
        col_f_y = next((c for c in df_asist_all.columns if any(x in c.lower() for x in ['fecha', 'fec', 'dia'])), 'Fecha')
        col_d_y = next((c for c in df_asist_all.columns if any(x in c.lower() for x in ['dato', 'ina', 'aus', 'asis'])), 'Datos')
        col_t_y = next((c for c in df_asist_all.columns if 'tipo' in c.lower()), None)

        if curso_alumno:
            df_curso = df_asist_all[df_asist_all[col_c_y].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, curso_alumno))]
        else:
            df_curso = df_asist_all

        for _, ra in df_curso.iterrows():
            if col_t_y and str(ra.get(col_t_y, '')).strip().lower() == 'sin_clases':
                continue
            dat_a = str(ra.get(col_d_y, '')).strip().lower()
            if dat_a in ('sc', 'borrar', ''):
                continue

            f_dia = parse_fecha_flexible(str(ra.get(col_f_y, '')).strip())
            if not f_dia:
                continue

            es_en_s1 = (s1_ini <= f_dia <= s1_fin) if (s1_ini and s1_fin) else False
            es_en_s2 = (s2_ini <= f_dia <= s2_fin) if (s2_ini and s2_fin) else False

            per_norm = str(periodo).strip().lower()
            if per_norm in ('s1', '1', '1er semestre', 'semestre 1'):
                if not es_en_s1:
                    continue
            elif per_norm in ('s2', '2', '2do semestre', 'semestre 2'):
                if not es_en_s2:
                    continue
            else:
                # Periodo Anual: solo dias oficiales de S1 o S2 (excluye vacaciones de invierno)
                if not (es_en_s1 or es_en_s2):
                    continue

            if f_dia < f_inicio_efectiva:
                continue
            if f_baja_alu and f_dia > f_baja_alu:
                continue

            dias_clase += 1
            if dat_a == 'todos' or str(n_lista) in [p.strip() for p in dat_a.split('-')]:
                dias_inasist += 1

    dias_asist = max(0, dias_clase - dias_inasist)
    pct_asist = round(dias_asist / dias_clase * 100, 1) if dias_clase > 0 else 100.0
    pct_asist_fmt = f"{(dias_asist / dias_clase * 100):.2f}".replace('.', ',') if dias_clase > 0 else "100,00"

    return {
        "dias_clase": dias_clase,
        "dias_asist": dias_asist,
        "dias_inasist": dias_inasist,
        "pct_asist": pct_asist,
        "pct_asist_fmt": pct_asist_fmt,
        "f_inicio_efectiva": f_inicio_efectiva,
        "es_ingreso_tardio": es_ingreso_tardio,
        "es_retirado": es_retirado,
        "f_baja": f_baja_alu
    }


def normalizar_fecha_chilena(val):
    """Convierte cualquier formato de fecha a formato estándar chileno DD/MM/AAAA."""
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none', '—', ''):
        return '—'
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(s.split()[0], fmt)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            pass
    return s


def fecha_a_iso_comp(val):
    """Convierte una fecha a formato YYYY-MM-DD para comparación estricta en filtros."""
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none', '—', ''):
        return '1900-01-01'
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(s.split()[0], fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return s


def estandarizar_motivo_general(val):
    """Estandariza los motivos de atraso y retiro a la nomenclatura institucional."""
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none', '—', ''):
        return 'Sin Motivo Especificado'
    s_low = s.lower()
    if 'personal' in s_low or 'tramite' in s_low or 'trámite' in s_low:
        return 'Personal'
    if 'enferm' in s_low or 'malestar' in s_low:
        return 'Enfermedad / Malestar'
    if 'dormid' in s_low or 'quedo dorm' in s_low:
        return 'Se quedó dormido/a'
    if 'medic' in s_low or 'dental' in s_low or 'doctor' in s_low or 'salud' in s_low or 'control' in s_low:
        return 'Hora médica/dental'
    if 'transporte' in s_low or 'furgon' in s_low or 'vehiculo' in s_low or 'micro' in s_low or 'locomocion' in s_low:
        return 'Problema de transporte'
    if 'clima' in s_low or 'lluvia' in s_low or 'temporal' in s_low:
        return 'Clima / Lluvia intensa'
    return s


def resolver_curso_estandar(c_raw, rut_raw, alu_curso_map):
    """Obtiene el curso oficial actual del alumno por RUT, o normaliza el texto antiguo."""
    rut_norm = str(rut_raw).replace('.', '').strip().upper()
    if rut_norm in alu_curso_map and alu_curso_map[rut_norm]:
        return alu_curso_map[rut_norm]

    c_s = str(c_raw).strip()
    if not c_s or c_s.lower() in ('nan', 'none', '—', ''):
        return '—'

    k = extraer_clave_curso(c_s)
    let = k[1].upper() if k[1] else 'A'
    if k[0] == 'nt1': return f"NT1 {let}"
    if k[0] == 'nt2': return f"NT2 {let}"
    for num in range(1, 9):
        if f"{num} basico" in k[0] or k[0].startswith(str(num)):
            return f"{num}° Básico {let}"
    return c_s


def renderizar_reporte_atrasos(sheet_alumnos, sheet_registros):
    st.markdown("### 📊 Reporte y Estadísticas de Atrasos")
    st.caption("Consolidado para Dirección. Monitorea reiteraciones, estadísticas por curso y emite el informe formal en PDF.")

    if not sheet_registros:
        st.error("No se pudo conectar con la base de datos de registros.")
        return

    try:
        conf = cargar_datos_configuracion_reportes()
        recs_reg = sheet_registros.get_all_records()
        df_reg_all = pd.DataFrame(recs_reg) if recs_reg else pd.DataFrame()

        # Mapa oficial de alumnos para cruzar curso y nombre real por RUT
        df_alu_map = pd.DataFrame(sheet_alumnos.get_all_records()) if sheet_alumnos else pd.DataFrame()
        alu_curso_map = {}
        alu_nom_map = {}
        if not df_alu_map.empty:
            df_alu_map.columns = [str(c).strip() for c in df_alu_map.columns]
            c_r = next((c for c in df_alu_map.columns if 'rut' in c.lower()), 'RUT')
            c_n = next((c for c in df_alu_map.columns if 'nomb' in c.lower()), 'Nombre')
            c_c = next((c for c in df_alu_map.columns if 'curs' in c.lower()), 'Curso')
            for _, row_a in df_alu_map.iterrows():
                r_k = str(row_a[c_r]).replace('.', '').strip().upper()
                c_k = str(row_a[c_c]).strip()
                n_k = str(row_a[c_n]).replace('\xa0', ' ').strip()
                if r_k:
                    alu_curso_map[r_k] = c_k
                    alu_nom_map[r_k] = n_k

        # Cursos oficiales del sistema (fuente única de verdad)
        cursos_oficiales = obtener_cursos_oficiales_sistema()

        if df_reg_all.empty:
            st.info("ℹ️ Aún no existen registros de atrasos en el sistema.")
            return

        df_reg_all.columns = [str(c).strip() for c in df_reg_all.columns]
        c_tipo = next((c for c in df_reg_all.columns if 'tipo' in c.lower()), None)
        if c_tipo:
            df_atrasos = df_reg_all[df_reg_all[c_tipo].astype(str).str.strip().str.lower() == 'atraso'].copy()
        else:
            df_atrasos = df_reg_all.copy()

        if df_atrasos.empty:
            st.info("ℹ️ No hay atrasos registrados en el sistema.")
            return

        # Normalizar columnas
        col_f = next((c for c in df_atrasos.columns if 'fech' in c.lower()), 'Fecha')
        col_h = next((c for c in df_atrasos.columns if 'hora' in c.lower()), 'Hora')
        col_nom = next((c for c in df_atrasos.columns if 'nomb' in c.lower()), 'Nombre')
        col_r = next((c for c in df_atrasos.columns if 'rut' in c.lower()), 'RUT')
        col_m = next((c for c in df_atrasos.columns if 'moti' in c.lower()), 'Motivo')
        col_cur = next((c for c in df_atrasos.columns if 'curs' in c.lower()), 'Curso')

        df_atrasos['RUT_Clean'] = df_atrasos[col_r].astype(str).str.strip()
        df_atrasos['Fecha_ISO'] = df_atrasos[col_f].apply(fecha_a_iso_comp)
        df_atrasos['Fecha_Chilena'] = df_atrasos[col_f].apply(normalizar_fecha_chilena)
        df_atrasos['Hora_Clean'] = df_atrasos[col_h].astype(str).str.strip()
        df_atrasos['Motivo_Clean'] = df_atrasos[col_m].apply(estandarizar_motivo_general) if col_m in df_atrasos.columns else "Sin Motivo Especificado"

        def obtener_nombre(row):
            n_raw = str(row[col_nom]).strip()
            if n_raw and n_raw.lower() not in ('nan', 'none'): return n_raw
            r_k = str(row['RUT_Clean']).replace('.', '').strip().upper()
            return alu_nom_map.get(r_k, 'Sin Nombre')

        df_atrasos['Nombre_Final'] = df_atrasos.apply(obtener_nombre, axis=1)
        df_atrasos['Curso_Final'] = df_atrasos.apply(
            lambda r: resolver_curso_estandar(r.get(col_cur, ''), r['RUT_Clean'], alu_curso_map), axis=1
        )

        # --- SECCIÓN DE FILTROS ---
        with st.expander("🔍 Filtros de Búsqueda y Rango Temporal", expanded=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns([1.6, 1.3, 1.4, 1.4])

            with f_col1:
                opciones_periodo = [
                    "Mes Actual",
                    "Hoy (Día Actual)",
                    "Primer Semestre (Inicio de Clases)",
                    "Segundo Semestre",
                    "Año Escolar Completo",
                    "Rango Personalizado"
                ]
                filtro_periodo = st.selectbox("📅 Período:", opciones_periodo, key="rep_atraso_periodo_sel_v2")
                hoy_dt = obtener_ahora_chile().date()

                if filtro_periodo == "Mes Actual":
                    f_desde = datetime.date(hoy_dt.year, hoy_dt.month, 1)
                    f_hasta = hoy_dt
                elif filtro_periodo == "Hoy (Día Actual)":
                    f_desde = hoy_dt
                    f_hasta = hoy_dt
                elif filtro_periodo == "Primer Semestre (Inicio de Clases)":
                    f_desde = conf["s1_ini"]
                    f_hasta = conf["s1_fin"]
                elif filtro_periodo == "Segundo Semestre":
                    f_desde = conf["s2_ini"]
                    f_hasta = conf["s2_fin"]
                elif filtro_periodo == "Año Escolar Completo":
                    f_desde = conf["s1_ini"]
                    f_hasta = conf["s2_fin"]
                else:
                    c_d1, c_d2 = st.columns(2)
                    with c_d1:
                        f_desde = st.date_input("Desde:", value=conf["s1_ini"], key="rep_atraso_f_desde")
                    with c_d2:
                        f_hasta = st.date_input("Hasta:", value=hoy_dt, key="rep_atraso_f_hasta")

            with f_col2:
                cursos_filtro = ["Todos los Cursos"] + cursos_oficiales
                sel_curso_rep = st.selectbox("📚 Curso:", cursos_filtro, key="rep_atraso_curso_sel")

            with f_col3:
                txt_alumno_rep = st.text_input(
                    "👤 Alumno (Nombre o RUT):",
                    placeholder="Buscar por nombre o RUT...",
                    key="rep_atraso_alumno_txt"
                ).strip().lower()

            with f_col4:
                motivos_disponibles = sorted(list(set(df_atrasos['Motivo_Clean'].dropna().unique())))
                sel_motivo_rep = st.selectbox(
                    "📌 Motivo:",
                    ["Todos los Motivos"] + [m for m in motivos_disponibles if m and m != "—"],
                    key="rep_atraso_motivo_sel"
                )

        # --- APLICAR FILTROS ---
        df_filtrado = df_atrasos.copy()

        f_desde_s = f_desde.strftime("%Y-%m-%d")
        f_hasta_s = f_hasta.strftime("%Y-%m-%d")
        df_filtrado = df_filtrado[
            (df_filtrado['Fecha_ISO'] >= f_desde_s) &
            (df_filtrado['Fecha_ISO'] <= f_hasta_s)
        ]

        if sel_curso_rep != "Todos los Cursos":
            df_filtrado = df_filtrado[df_filtrado['Curso_Final'] == sel_curso_rep]

        if txt_alumno_rep:
            df_filtrado = df_filtrado[
                df_filtrado['Nombre_Final'].str.lower().str.contains(txt_alumno_rep) |
                df_filtrado['RUT_Clean'].str.lower().str.contains(txt_alumno_rep)
            ]

        if sel_motivo_rep != "Todos los Motivos":
            df_filtrado = df_filtrado[df_filtrado['Motivo_Clean'] == sel_motivo_rep]

        df_filtrado = df_filtrado.sort_values(by=['Fecha_ISO', 'Hora_Clean'], ascending=[False, False])

        # --- TARJETAS DE MÉTRICAS (KPIs) ---
        total_atrasos_filt = len(df_filtrado)
        alumnos_unicos = df_filtrado['RUT_Clean'].nunique() if not df_filtrado.empty else 0

        # Casos con reiteración
        if not df_filtrado.empty:
            conteo_alumnos = df_filtrado.groupby(['RUT_Clean', 'Nombre_Final', 'Curso_Final']).size().reset_index(name='Total')
            alumnos_reiterados = conteo_alumnos[conteo_alumnos['Total'] >= 3]
            cant_reiterados = len(alumnos_reiterados)

            cursos_validos = df_filtrado[df_filtrado['Curso_Final'] != '—']
            curso_top = cursos_validos['Curso_Final'].mode().iloc[0] if not cursos_validos.empty else "—"
        else:
            conteo_alumnos = pd.DataFrame()
            alumnos_reiterados = pd.DataFrame()
            cant_reiterados = 0
            curso_top = "—"

        st.write("")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("Total Atrasos", f"{total_atrasos_filt}")
        with kpi2:
            st.metric("Alumnos Afectados", f"{alumnos_unicos}")
        with kpi3:
            st.metric("Reiteración (≥3)", f"{cant_reiterados}", delta="Prioridad Citación" if cant_reiterados > 0 else None, delta_color="inverse")
        with kpi4:
            st.metric("Curso con Mayor Registro", f"{curso_top}")

        # Alerta Directiva de Reiteración
        if cant_reiterados > 0:
            with st.container(border=True):
                st.warning(f"⚠️ **Alerta Dirección:** Existen **{cant_reiterados} alumno(s)** con 3 o más atrasos acumulados en este período.")
                cols_reit = st.columns(min(cant_reiterados, 3))
                for idx_c, (_, r_reit) in enumerate(alumnos_reiterados.iterrows()):
                    with cols_reit[idx_c % len(cols_reit)]:
                        st.markdown(f"**{r_reit['Nombre_Final']}**<br>📚 {r_reit['Curso_Final']}<br>🔴 **{r_reit['Total']} atrasos acumulados**", unsafe_allow_html=True)

        st.write("---")

        if df_filtrado.empty:
            st.info("💡 No se encontraron atrasos registrados en el rango de fechas seleccionado.")
            return

        # --- VISTAS: TABLA Y REPORTE IMPRIMIBLE ---
        tab_tabla, tab_imprimible = st.tabs(["📋 Listado Detallado", "🖨️ Informe Oficial Imprimible / PDF"])

        with tab_tabla:
            st.markdown(f"**Registros encontrados:** `{len(df_filtrado)}` atrasos")
            df_mostrar = df_filtrado[['Fecha_Chilena', 'Hora_Clean', 'Nombre_Final', 'Curso_Final', 'RUT_Clean', 'Motivo_Clean']].copy()
            df_mostrar.columns = ['Fecha', 'Hora', 'Alumno', 'Curso', 'RUT', 'Motivo']

            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True,
                height=380
            )

            csv_data = df_mostrar.to_csv(index=False, sep=";").encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar Planilla Excel (CSV)",
                data=csv_data,
                file_name=f"Reporte_Atrasos_{f_desde.strftime('%d-%m-%Y')}_al_{f_hasta.strftime('%d-%m-%Y')}.csv",
                mime="text/csv",
                key="btn_csv_atrasos"
            )

            # --- SECCIÓN: ANULAR / ELIMINAR REGISTRO POR ERROR ---
            with st.expander("🗑️ Anular / Eliminar Registro de Atraso por Error", expanded=False):
                st.caption("Si se cometió una equivocación al marcar un atraso, puedes anularlo aquí. Esta acción lo eliminará de la base de datos.")
                
                # Crear diccionario de opciones con información legible
                opciones_del = {}
                for idx_row, r_del in df_filtrado.iterrows():
                    reg_id = r_del.get('_id', idx_row)
                    etiqueta = f"🗓️ {r_del['Fecha_Chilena']} {r_del['Hora_Clean']} — {r_del['Nombre_Final']} ({r_del['Curso_Final']}) | Motivo: {r_del['Motivo_Clean']}"
                    opciones_del[etiqueta] = r_del

                if opciones_del:
                    sel_etiqueta = st.selectbox(
                        "Selecciona el atraso a anular:",
                        options=list(opciones_del.keys()),
                        key="sel_del_atraso"
                    )
                    r_a_borrar = opciones_del[sel_etiqueta]
                    
                    c_del1, c_del2 = st.columns([3, 1.2])
                    with c_del1:
                        confirmar_check = st.checkbox(
                            f"Confirmar anulación del atraso de **{r_a_borrar['Nombre_Final']}**",
                            key="chk_confirm_del_atraso"
                        )
                    with c_del2:
                        btn_del_atraso = st.button(
                            "🗑️ Eliminar Definitivamente",
                            type="primary",
                            disabled=not confirmar_check,
                            key="btn_ejecutar_del_atraso",
                            use_container_width=True
                        )

                    if btn_del_atraso:
                        try:
                            # Si tiene _id primario de PostgreSQL
                            if '_id' in r_a_borrar and r_a_borrar['_id']:
                                sheet_registros.delete_by_id(r_a_borrar['_id'])
                            else:
                                sheet_registros.delete_records({
                                    'rut': r_a_borrar[col_r],
                                    'fecha': r_a_borrar[col_f],
                                    'hora': r_a_borrar[col_h],
                                    'tipo': 'Atraso'
                                })
                            st.toast(f"✅ Atraso de {r_a_borrar['Nombre_Final']} eliminado exitosamente.", icon="🗑️")
                            st.success(f"✅ Se ha eliminado correctamente el atraso de **{r_a_borrar['Nombre_Final']}** del **{r_a_borrar['Fecha_Chilena']}**.")
                            time.sleep(1.2)
                            st.rerun()
                        except Exception as e_del:
                            st.error(f"❌ Error al anular el registro: {e_del}")
                else:
                    st.info("No hay registros en la vista actual para anular.")

        with tab_imprimible:
            st.markdown("##### Vista Previa de Documento Oficial")
            st.caption("Usa el botón para abrir el diálogo de impresión del navegador y guardar directamente en **PDF**.")

            insignia_b64 = ""
            if os.path.exists("insignia.png"):
                try:
                    with open("insignia.png", "rb") as f_ins:
                        insignia_b64 = base64.b64encode(f_ins.read()).decode()
                except Exception:
                    pass

            img_ins_tag = f'<img src="data:image/png;base64,{insignia_b64}" style="width:75px;height:auto;" />' if insignia_b64 else ''

            filas_html = ""
            for idx_r, (_, r_fila) in enumerate(df_filtrado.iterrows(), 1):
                bg_fila = "#f9fafb" if idx_r % 2 == 0 else "#ffffff"
                filas_html += f"""
                <tr style="background-color:{bg_fila};">
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;">{idx_r}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;white-space:nowrap;">{r_fila['Fecha_Chilena']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;white-space:nowrap;">{r_fila['Hora_Clean']}</td>
                    <td style="padding:5px 8px;border-bottom:1px solid #e5e7eb;font-size:0.78rem;font-weight:600;">{r_fila['Nombre_Final']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;">{r_fila['Curso_Final']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;white-space:nowrap;">{r_fila['RUT_Clean']}</td>
                    <td style="padding:5px 8px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;color:#4b5563;">{r_fila['Motivo_Clean']}</td>
                </tr>
                """

            hoy_str = hoy_dt.strftime("%d/%m/%Y")
            rango_str = f"Desde {f_desde.strftime('%d/%m/%Y')} hasta {f_hasta.strftime('%d/%m/%Y')}"
            curso_filtro_str = sel_curso_rep if sel_curso_rep != "Todos los Cursos" else "Todos los Cursos del Establecimiento"

            firma_img_tag = f'<img src="data:image/png;base64,{conf["firma_b64"]}" style="height:62px;display:block;margin:0 auto 2px auto;" />' if conf["firma_b64"] else '<div style="height:50px;"></div>'

            html_informe_atrasos = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: letter portrait;
                    margin: 12mm 14mm 12mm 14mm;
                }}
                @media print {{
                    body {{ background: #fff !important; margin: 0 !important; padding: 0 !important; }}
                    .no-print {{ display: none !important; }}
                    .doc-container {{ border: none !important; box-shadow: none !important; padding: 0 !important; width: 100% !important; }}
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    color: #111827;
                    background-color: #f3f4f6;
                    margin: 0;
                    padding: 12px;
                }}
                .doc-container {{
                    background: #ffffff;
                    max-width: 820px;
                    margin: 0 auto;
                    padding: 24px 30px;
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
                }}
                .btn-imprimir {{
                    background-color: #008F39;
                    color: white;
                    padding: 10px 22px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 700;
                    font-size: 0.90rem;
                    cursor: pointer;
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 16px;
                    transition: background 0.2s;
                }}
                .btn-imprimir:hover {{
                    background-color: #00732e;
                }}
                .header-doc {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    border-bottom: 2px solid #008F39;
                    padding-bottom: 10px;
                    margin-bottom: 14px;
                }}
                .header-left {{
                    display: flex;
                    align-items: center;
                    gap: 16px;
                }}
                .school-name {{
                    margin: 0;
                    color: #008F39;
                    font-size: 1.25rem;
                    font-weight: 800;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .doc-title {{
                    margin: 3px 0 0 0;
                    color: #1f2937;
                    font-size: 1.02rem;
                    font-weight: 700;
                    letter-spacing: 0.3px;
                }}
                .school-sub {{
                    margin: 3px 0 0 0;
                    color: #6b7280;
                    font-size: 0.77rem;
                }}
                .header-right {{
                    text-align: right;
                    font-size: 0.76rem;
                    color: #6b7280;
                }}
                .metadata-box {{
                    display: grid;
                    grid-template-columns: 2fr 1.2fr 1fr;
                    background: #f9fafb;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 8px 14px;
                    margin-bottom: 14px;
                    font-size: 0.78rem;
                }}
                .table-rep {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 8px;
                }}
                .table-rep th {{
                    background-color: #f3f4f6;
                    color: #1f2937;
                    font-size: 0.73rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    padding: 6px 6px;
                    border-top: 1px solid #d1d5db;
                    border-bottom: 2px solid #9ca3af;
                    text-align: left;
                }}
                .signatures {{
                    display: flex;
                    justify-content: center;
                    margin-top: 40px;
                    padding-top: 15px;
                }}
                .sig-box {{
                    text-align: center;
                    width: 290px;
                    font-size: 0.78rem;
                    color: #1f2937;
                }}
                .sig-line {{
                    border-top: 1px solid #4b5563;
                    margin-top: 4px;
                    margin-bottom: 6px;
                }}
            </style>
            </head>
            <body>
            <div class="doc-container">
                <div class="no-print" style="text-align: right;">
                    <button class="btn-imprimir" onclick="window.print()">
                        🖨️ Imprimir / Guardar en PDF
                    </button>
                </div>

                <div class="header-doc">
                    <div class="header-left">
                        {img_ins_tag}
                        <div>
                            <div class="school-name">{conf['nombre_colegio']}</div>
                            <div class="doc-title">INFORME DE ATRASOS ESCOLARES</div>
                            <div class="school-sub">RBD: {conf['rbd']} &nbsp;|&nbsp; Comuna: {conf['ciudad']} &nbsp;|&nbsp; Región del {conf['region']}</div>
                        </div>
                    </div>
                    <div class="header-right">
                        <div><b>Fecha Emisión:</b> {hoy_str}</div>
                        <div><b>Año Lectivo:</b> {hoy_dt.year}</div>
                    </div>
                </div>

                <div class="metadata-box">
                    <div><b>Período Analizado:</b> {rango_str}</div>
                    <div><b>Curso:</b> {curso_filtro_str}</div>
                    <div style="text-align:right;"><b>Total Atrasos:</b> {total_atrasos_filt}</div>
                </div>

                <table class="table-rep">
                    <thead>
                        <tr>
                            <th style="width:30px;text-align:center;">#</th>
                            <th style="width:75px;text-align:center;">Fecha</th>
                            <th style="width:60px;text-align:center;">Hora</th>
                            <th>Alumno</th>
                            <th style="width:85px;text-align:center;">Curso</th>
                            <th style="width:85px;text-align:center;">RUT</th>
                            <th>Motivo del Atraso</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_html}
                    </tbody>
                </table>

                <div class="signatures">
                    <div class="sig-box">
                        {firma_img_tag}
                        <div class="sig-line"></div>
                        <b>{conf['nombre_director']}</b><br>
                        <span>Director</span><br>
                        <span style="font-size:0.72rem;color:#6b7280;">{conf['nombre_colegio']}</span>
                    </div>
                </div>
            </div>
            </body>
            </html>
            """
            import streamlit.components.v1 as components
            components.html(html_informe_atrasos, height=750, scrolling=True)

    except Exception as e_rep:
        st.error(f"Error al generar reporte de atrasos: {e_rep}")


def renderizar_reporte_retiros(sheet_alumnos, sheet_registros):
    st.markdown("### 📊 Reporte y Estadísticas de Salidas Anticipadas / Retiros")
    st.caption("Consolidado para Dirección. Monitorea retiros anticipados, apoderados autorizados y emite el informe formal en PDF.")

    if not sheet_registros:
        st.error("No se pudo conectar con la base de datos de registros.")
        return

    try:
        conf = cargar_datos_configuracion_reportes()
        recs_reg = sheet_registros.get_all_records()
        df_reg_all = pd.DataFrame(recs_reg) if recs_reg else pd.DataFrame()

        # Mapa oficial de alumnos para cruzar curso y nombre real por RUT
        df_alu_map = pd.DataFrame(sheet_alumnos.get_all_records()) if sheet_alumnos else pd.DataFrame()
        alu_curso_map = {}
        alu_nom_map = {}
        if not df_alu_map.empty:
            df_alu_map.columns = [str(c).strip() for c in df_alu_map.columns]
            c_r = next((c for c in df_alu_map.columns if 'rut' in c.lower()), 'RUT')
            c_n = next((c for c in df_alu_map.columns if 'nomb' in c.lower()), 'Nombre')
            c_c = next((c for c in df_alu_map.columns if 'curs' in c.lower()), 'Curso')
            for _, row_a in df_alu_map.iterrows():
                r_k = str(row_a[c_r]).replace('.', '').strip().upper()
                c_k = str(row_a[c_c]).strip()
                n_k = str(row_a[c_n]).replace('\xa0', ' ').strip()
                if r_k:
                    alu_curso_map[r_k] = c_k
                    alu_nom_map[r_k] = n_k

        # Cursos oficiales del sistema (fuente única de verdad)
        cursos_oficiales = obtener_cursos_oficiales_sistema()

        if df_reg_all.empty:
            st.info("ℹ️ Aún no existen registros de salidas anticipadas en el sistema.")
            return

        df_reg_all.columns = [str(c).strip() for c in df_reg_all.columns]
        c_tipo = next((c for c in df_reg_all.columns if 'tipo' in c.lower()), None)
        if c_tipo:
            df_retiros = df_reg_all[df_reg_all[c_tipo].astype(str).str.strip().str.lower() == 'retiro'].copy()
        else:
            df_retiros = df_reg_all.copy()

        if df_retiros.empty:
            st.info("ℹ️ No hay retiros anticipados registrados hasta la fecha.")
            return

        # Normalizar columnas
        col_f = next((c for c in df_retiros.columns if 'fech' in c.lower()), 'Fecha')
        col_h = next((c for c in df_retiros.columns if 'hora' in c.lower()), 'Hora')
        col_nom = next((c for c in df_retiros.columns if 'nomb' in c.lower()), 'Nombre')
        col_r = next((c for c in df_retiros.columns if 'rut' in c.lower()), 'RUT')
        col_m = next((c for c in df_retiros.columns if 'moti' in c.lower()), 'Motivo')
        col_apod = next((c for c in df_retiros.columns if 'apod' in c.lower()), 'Apoderado')
        col_vinc = next((c for c in df_retiros.columns if 'vinc' in c.lower() or 'paren' in c.lower()), 'Vinculo')
        col_cur = next((c for c in df_retiros.columns if 'curs' in c.lower()), 'Curso')

        df_retiros['RUT_Clean'] = df_retiros[col_r].astype(str).str.strip()
        df_retiros['Fecha_ISO'] = df_retiros[col_f].apply(fecha_a_iso_comp)
        df_retiros['Fecha_Chilena'] = df_retiros[col_f].apply(normalizar_fecha_chilena)
        df_retiros['Hora_Clean'] = df_retiros[col_h].astype(str).str.strip()
        df_retiros['Motivo_Clean'] = df_retiros[col_m].apply(estandarizar_motivo_general) if col_m in df_retiros.columns else "Sin Motivo Especificado"
        df_retiros['Apoderado_Clean'] = df_retiros[col_apod].astype(str).str.strip() if col_apod in df_retiros.columns else "—"
        df_retiros['Vinculo_Clean'] = df_retiros[col_vinc].astype(str).str.strip() if col_vinc in df_retiros.columns else "—"

        def obtener_nombre(row):
            n_raw = str(row[col_nom]).strip()
            if n_raw and n_raw.lower() not in ('nan', 'none'): return n_raw
            r_k = str(row['RUT_Clean']).replace('.', '').strip().upper()
            return alu_nom_map.get(r_k, 'Sin Nombre')

        df_retiros['Nombre_Final'] = df_retiros.apply(obtener_nombre, axis=1)
        df_retiros['Curso_Final'] = df_retiros.apply(
            lambda r: resolver_curso_estandar(r.get(col_cur, ''), r['RUT_Clean'], alu_curso_map), axis=1
        )

        # --- SECCIÓN DE FILTROS ---
        with st.expander("🔍 Filtros de Búsqueda y Rango Temporal", expanded=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns([1.6, 1.3, 1.4, 1.4])

            with f_col1:
                opciones_periodo = [
                    "Mes Actual",
                    "Hoy (Día Actual)",
                    "Primer Semestre (Inicio de Clases)",
                    "Segundo Semestre",
                    "Año Escolar Completo",
                    "Rango Personalizado"
                ]
                filtro_periodo = st.selectbox("📅 Período:", opciones_periodo, key="rep_retiro_periodo_sel_v2")
                hoy_dt = obtener_ahora_chile().date()

                if filtro_periodo == "Mes Actual":
                    f_desde = datetime.date(hoy_dt.year, hoy_dt.month, 1)
                    f_hasta = hoy_dt
                elif filtro_periodo == "Hoy (Día Actual)":
                    f_desde = hoy_dt
                    f_hasta = hoy_dt
                elif filtro_periodo == "Primer Semestre (Inicio de Clases)":
                    f_desde = conf["s1_ini"]
                    f_hasta = conf["s1_fin"]
                elif filtro_periodo == "Segundo Semestre":
                    f_desde = conf["s2_ini"]
                    f_hasta = conf["s2_fin"]
                elif filtro_periodo == "Año Escolar Completo":
                    f_desde = conf["s1_ini"]
                    f_hasta = conf["s2_fin"]
                else:
                    c_d1, c_d2 = st.columns(2)
                    with c_d1:
                        f_desde = st.date_input("Desde:", value=conf["s1_ini"], key="rep_retiro_f_desde")
                    with c_d2:
                        f_hasta = st.date_input("Hasta:", value=hoy_dt, key="rep_retiro_f_hasta")

            with f_col2:
                cursos_filtro = ["Todos los Cursos"] + cursos_oficiales
                sel_curso_rep = st.selectbox("📚 Curso:", cursos_filtro, key="rep_retiro_curso_sel")

            with f_col3:
                txt_alumno_rep = st.text_input(
                    "👤 Alumno o Apoderado:",
                    placeholder="Nombre, RUT o apoderado...",
                    key="rep_retiro_alumno_txt"
                ).strip().lower()

            with f_col4:
                motivos_disponibles = sorted(list(set(df_retiros['Motivo_Clean'].dropna().unique())))
                sel_motivo_rep = st.selectbox(
                    "📌 Motivo:",
                    ["Todos los Motivos"] + [m for m in motivos_disponibles if m and m != "—"],
                    key="rep_retiro_motivo_sel"
                )

        # --- APLICAR FILTROS ---
        df_filtrado = df_retiros.copy()

        f_desde_s = f_desde.strftime("%Y-%m-%d")
        f_hasta_s = f_hasta.strftime("%Y-%m-%d")
        df_filtrado = df_filtrado[
            (df_filtrado['Fecha_ISO'] >= f_desde_s) &
            (df_filtrado['Fecha_ISO'] <= f_hasta_s)
        ]

        if sel_curso_rep != "Todos los Cursos":
            df_filtrado = df_filtrado[df_filtrado['Curso_Final'] == sel_curso_rep]

        if txt_alumno_rep:
            df_filtrado = df_filtrado[
                df_filtrado['Nombre_Final'].str.lower().str.contains(txt_alumno_rep) |
                df_filtrado['RUT_Clean'].str.lower().str.contains(txt_alumno_rep) |
                df_filtrado['Apoderado_Clean'].str.lower().str.contains(txt_alumno_rep)
            ]

        if sel_motivo_rep != "Todos los Motivos":
            df_filtrado = df_filtrado[df_filtrado['Motivo_Clean'] == sel_motivo_rep]

        df_filtrado = df_filtrado.sort_values(by=['Fecha_ISO', 'Hora_Clean'], ascending=[False, False])

        # --- TARJETAS DE MÉTRICAS (KPIs) ---
        total_retiros_filt = len(df_filtrado)
        alumnos_unicos = df_filtrado['RUT_Clean'].nunique() if not df_filtrado.empty else 0

        # Casos con reiteración
        if not df_filtrado.empty:
            conteo_alumnos = df_filtrado.groupby(['RUT_Clean', 'Nombre_Final', 'Curso_Final']).size().reset_index(name='Total')
            alumnos_reiterados = conteo_alumnos[conteo_alumnos['Total'] >= 3]
            cant_reiterados = len(alumnos_reiterados)

            cursos_validos = df_filtrado[df_filtrado['Curso_Final'] != '—']
            curso_top = cursos_validos['Curso_Final'].mode().iloc[0] if not cursos_validos.empty else "—"
        else:
            conteo_alumnos = pd.DataFrame()
            alumnos_reiterados = pd.DataFrame()
            cant_reiterados = 0
            curso_top = "—"

        st.write("")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("Total Retiros", f"{total_retiros_filt}")
        with kpi2:
            st.metric("Alumnos Retirados", f"{alumnos_unicos}")
        with kpi3:
            st.metric("Reiteración (≥3)", f"{cant_reiterados}", delta="Atención" if cant_reiterados > 0 else None, delta_color="inverse")
        with kpi4:
            st.metric("Curso con Más Salidas", f"{curso_top}")

        # Alerta Directiva de Reiteración
        if cant_reiterados > 0:
            with st.container(border=True):
                st.warning(f"⚠️ **Alerta Dirección:** Existen **{cant_reiterados} alumno(s)** con 3 o más salidas anticipadas acumuladas en este período.")
                cols_reit = st.columns(min(cant_reiterados, 3))
                for idx_c, (_, r_reit) in enumerate(alumnos_reiterados.iterrows()):
                    with cols_reit[idx_c % len(cols_reit)]:
                        st.markdown(f"**{r_reit['Nombre_Final']}**<br>📚 {r_reit['Curso_Final']}<br>🔴 **{r_reit['Total']} retiros registrados**", unsafe_allow_html=True)

        st.write("---")

        if df_filtrado.empty:
            st.info("💡 No se encontraron retiros con los filtros seleccionados.")
            return

        # --- VISTAS: TABLA Y REPORTE IMPRIMIBLE ---
        tab_tabla, tab_imprimible = st.tabs(["📋 Listado Detallado", "🖨️ Informe Oficial Imprimible / PDF"])

        with tab_tabla:
            st.markdown(f"**Registros encontrados:** `{len(df_filtrado)}` salidas anticipadas")
            df_mostrar = df_filtrado[[
                'Fecha_Chilena', 'Hora_Clean', 'Nombre_Final', 'Curso_Final',
                'RUT_Clean', 'Motivo_Clean', 'Apoderado_Clean', 'Vinculo_Clean'
            ]].copy()
            df_mostrar.columns = ['Fecha', 'Hora', 'Alumno', 'Curso', 'RUT', 'Motivo', 'Apoderado que Retira', 'Parentesco']

            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True,
                height=380
            )

            csv_data = df_mostrar.to_csv(index=False, sep=";").encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar Base en CSV (Excel)",
                data=csv_data,
                file_name=f"Reporte_Retiros_{f_desde.strftime('%d-%m-%Y')}_al_{f_hasta.strftime('%d-%m-%Y')}.csv",
                mime="text/csv",
                key="btn_csv_retiros"
            )

            # --- SECCIÓN: ANULAR / ELIMINAR REGISTRO POR ERROR ---
            with st.expander("🗑️ Anular / Eliminar Registro de Retiro por Error", expanded=False):
                st.caption("Si se cometió una equivocación al registrar una salida anticipada, puedes anularla aquí. Esta acción eliminará el registro de la base de datos.")
                
                opciones_del = {}
                for idx_row, r_del in df_filtrado.iterrows():
                    reg_id = r_del.get('_id', idx_row)
                    etiqueta = f"🗓️ {r_del['Fecha_Chilena']} {r_del['Hora_Clean']} — {r_del['Nombre_Final']} ({r_del['Curso_Final']}) | Retira: {r_del['Apoderado_Clean']} ({r_del['Vinculo_Clean']})"
                    opciones_del[etiqueta] = r_del

                if opciones_del:
                    sel_etiqueta = st.selectbox(
                        "Selecciona la salida a anular:",
                        options=list(opciones_del.keys()),
                        key="sel_del_retiro"
                    )
                    r_a_borrar = opciones_del[sel_etiqueta]
                    
                    c_del1, c_del2 = st.columns([3, 1.2])
                    with c_del1:
                        confirmar_check = st.checkbox(
                            f"Confirmar anulación del retiro de **{r_a_borrar['Nombre_Final']}**",
                            key="chk_confirm_del_retiro"
                        )
                    with c_del2:
                        btn_del_retiro = st.button(
                            "🗑️ Eliminar Definitivamente",
                            type="primary",
                            disabled=not confirmar_check,
                            key="btn_ejecutar_del_retiro",
                            use_container_width=True
                        )

                    if btn_del_retiro:
                        try:
                            # Si tiene _id primario de PostgreSQL
                            if '_id' in r_a_borrar and r_a_borrar['_id']:
                                sheet_registros.delete_by_id(r_a_borrar['_id'])
                            else:
                                sheet_registros.delete_records({
                                    'rut': r_a_borrar[col_r],
                                    'fecha': r_a_borrar[col_f],
                                    'hora': r_a_borrar[col_h],
                                    'tipo': 'Retiro'
                                })
                            st.toast(f"✅ Salida anticipada de {r_a_borrar['Nombre_Final']} eliminada exitosamente.", icon="🗑️")
                            st.success(f"✅ Se ha eliminado correctamente el retiro de **{r_a_borrar['Nombre_Final']}** del **{r_a_borrar['Fecha_Chilena']}**.")
                            time.sleep(1.2)
                            st.rerun()
                        except Exception as e_del:
                            st.error(f"❌ Error al anular el registro: {e_del}")
                else:
                    st.info("No hay registros en la vista actual para anular.")

        with tab_imprimible:
            st.markdown("##### Vista Previa de Documento Oficial")
            st.caption("Usa el botón para abrir el diálogo de impresión del navegador y guardar directamente en **PDF**.")

            insignia_b64 = ""
            if os.path.exists("insignia.png"):
                try:
                    with open("insignia.png", "rb") as f_ins:
                        insignia_b64 = base64.b64encode(f_ins.read()).decode()
                except Exception:
                    pass

            img_ins_tag = f'<img src="data:image/png;base64,{insignia_b64}" style="width:75px;height:auto;" />' if insignia_b64 else ''

            filas_html = ""
            for idx_r, (_, r_fila) in enumerate(df_filtrado.iterrows(), 1):
                bg_fila = "#f9fafb" if idx_r % 2 == 0 else "#ffffff"
                filas_html += f"""
                <tr style="background-color:{bg_fila};">
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;">{idx_r}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;white-space:nowrap;">{r_fila['Fecha_Chilena']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;white-space:nowrap;">{r_fila['Hora_Clean']}</td>
                    <td style="padding:5px 7px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;font-weight:600;">{r_fila['Nombre_Final']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;">{r_fila['Curso_Final']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;white-space:nowrap;">{r_fila['RUT_Clean']}</td>
                    <td style="padding:5px 7px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;color:#374151;">{r_fila['Motivo_Clean']}</td>
                    <td style="padding:5px 7px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;font-weight:600;">{r_fila['Apoderado_Clean']}</td>
                    <td style="text-align:center;padding:5px 6px;border-bottom:1px solid #e5e7eb;font-size:0.73rem;">{r_fila['Vinculo_Clean']}</td>
                </tr>
                """

            hoy_str = hoy_dt.strftime("%d/%m/%Y")
            rango_str = f"Desde {f_desde.strftime('%d/%m/%Y')} hasta {f_hasta.strftime('%d/%m/%Y')}"
            curso_filtro_str = sel_curso_rep if sel_curso_rep != "Todos los Cursos" else "Todos los Cursos del Establecimiento"

            firma_img_tag = f'<img src="data:image/png;base64,{conf["firma_b64"]}" style="height:62px;display:block;margin:0 auto 2px auto;" />' if conf["firma_b64"] else '<div style="height:50px;"></div>'

            html_informe_retiros = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: letter landscape;
                    margin: 10mm 12mm 10mm 12mm;
                }}
                @media print {{
                    body {{ background: #fff !important; margin: 0 !important; padding: 0 !important; }}
                    .no-print {{ display: none !important; }}
                    .doc-container {{ border: none !important; box-shadow: none !important; padding: 0 !important; width: 100% !important; max-width: 100% !important; }}
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    color: #111827;
                    background-color: #f3f4f6;
                    margin: 0;
                    padding: 12px;
                }}
                .doc-container {{
                    background: #ffffff;
                    max-width: 960px;
                    margin: 0 auto;
                    padding: 24px 30px;
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
                }}
                .btn-imprimir {{
                    background-color: #008F39;
                    color: white;
                    padding: 10px 22px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 700;
                    font-size: 0.90rem;
                    cursor: pointer;
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 16px;
                    transition: background 0.2s;
                }}
                .btn-imprimir:hover {{
                    background-color: #00732e;
                }}
                .header-doc {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    border-bottom: 2px solid #008F39;
                    padding-bottom: 10px;
                    margin-bottom: 14px;
                }}
                .header-left {{
                    display: flex;
                    align-items: center;
                    gap: 16px;
                }}
                .school-name {{
                    margin: 0;
                    color: #008F39;
                    font-size: 1.25rem;
                    font-weight: 800;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .doc-title {{
                    margin: 3px 0 0 0;
                    color: #1f2937;
                    font-size: 1.02rem;
                    font-weight: 700;
                    letter-spacing: 0.3px;
                }}
                .school-sub {{
                    margin: 3px 0 0 0;
                    color: #6b7280;
                    font-size: 0.77rem;
                }}
                .header-right {{
                    text-align: right;
                    font-size: 0.76rem;
                    color: #6b7280;
                }}
                .metadata-box {{
                    display: grid;
                    grid-template-columns: 2fr 1.2fr 1fr;
                    background: #f9fafb;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 8px 14px;
                    margin-bottom: 14px;
                    font-size: 0.78rem;
                }}
                .table-rep {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 8px;
                }}
                .table-rep th {{
                    background-color: #f3f4f6;
                    color: #1f2937;
                    font-size: 0.72rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    padding: 6px 6px;
                    border-top: 1px solid #d1d5db;
                    border-bottom: 2px solid #9ca3af;
                    text-align: left;
                }}
                .signatures {{
                    display: flex;
                    justify-content: center;
                    margin-top: 40px;
                    padding-top: 15px;
                }}
                .sig-box {{
                    text-align: center;
                    width: 290px;
                    font-size: 0.78rem;
                    color: #1f2937;
                }}
                .sig-line {{
                    border-top: 1px solid #4b5563;
                    margin-top: 4px;
                    margin-bottom: 6px;
                }}
            </style>
            </head>
            <body>
            <div class="doc-container">
                <div class="no-print" style="text-align: right;">
                    <button class="btn-imprimir" onclick="window.print()">
                        🖨️ Imprimir / Guardar en PDF
                    </button>
                </div>

                <div class="header-doc">
                    <div class="header-left">
                        {img_ins_tag}
                        <div>
                            <div class="school-name">{conf['nombre_colegio']}</div>
                            <div class="doc-title">INFORME DE SALIDAS ANTICIPADAS Y RETIROS</div>
                            <div class="school-sub">RBD: {conf['rbd']} &nbsp;|&nbsp; Comuna: {conf['ciudad']} &nbsp;|&nbsp; Región del {conf['region']}</div>
                        </div>
                    </div>
                    <div class="header-right">
                        <div><b>Fecha Emisión:</b> {hoy_str}</div>
                        <div><b>Año Lectivo:</b> {hoy_dt.year}</div>
                    </div>
                </div>

                <div class="metadata-box">
                    <div><b>Período Analizado:</b> {rango_str}</div>
                    <div><b>Curso:</b> {curso_filtro_str}</div>
                    <div style="text-align:right;"><b>Total Retiros:</b> {total_retiros_filt}</div>
                </div>

                <table class="table-rep">
                    <thead>
                        <tr>
                            <th style="width:30px;text-align:center;">#</th>
                            <th style="width:75px;text-align:center;">Fecha</th>
                            <th style="width:55px;text-align:center;">Hora</th>
                            <th>Alumno</th>
                            <th style="width:85px;text-align:center;">Curso</th>
                            <th style="width:85px;text-align:center;">RUT</th>
                            <th>Motivo</th>
                            <th>Apoderado que Retira</th>
                            <th style="width:80px;text-align:center;">Vínculo</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_html}
                    </tbody>
                </table>

                <div class="signatures">
                    <div class="sig-box">
                        {firma_img_tag}
                        <div class="sig-line"></div>
                        <b>{conf['nombre_director']}</b><br>
                        <span>Director</span><br>
                        <span style="font-size:0.72rem;color:#6b7280;">{conf['nombre_colegio']}</span>
                    </div>
                </div>
            </div>
            </body>
            </html>
            """
            import streamlit.components.v1 as components
            components.html(html_informe_retiros, height=750, scrolling=True)

    except Exception as e_rep:
        st.error(f"Error al generar reporte de retiros: {e_rep}")

# ---------------------------------------------------------
# # LÓGICA DE RENDERIZADO (USUARIO AUTENTICADO)
# ---------------------------------------------------------

sheet_config_global = get_config_sheet()
matriz_permisos_global = obtener_matriz_permisos(sheet_config_global)
rol_user_actual = str(st.session_state.user.get('rol', '') if st.session_state.get('user') else '').strip()
es_admin_total  = normalizar_nombre_rol(rol_user_actual) == "Administrador Total"

# Seguridad de navegación directa por rol
if st.session_state.current_module != 'home':
    if not rol_tiene_permiso(rol_user_actual, st.session_state.current_module, matriz_permisos_global):
        renderizar_insignia_universal()
        st.error(f"🔒 Acceso restringido: El rol '{rol_user_actual}' no tiene permisos para acceder al módulo '{st.session_state.current_module}'.")
        st.info("Comunícate con el Administrador del establecimiento para solicitar acceso a este módulo.")
        if st.button("🏠 Volver al Menú Principal", use_container_width=True):
            navigate('home')
            st.rerun()
        st.stop()

if st.session_state.current_module == 'home':
    # Insignia Institucional Centrada
    renderizar_insignia_universal()

    # Título Principal del Dashboard
    st.markdown("<h2 style='text-align:center;color:#1a5c32;margin-top:0px;margin-bottom:4px;font-size:1.6rem;'>🏫 Escuela Villa Las Peñas</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;color:#555;font-size:0.9rem;margin-bottom:12px;'>Bienvenido/a <b>{st.session_state.user['nombre']}</b> &nbsp;·&nbsp; Rol: <span style='background:#eaf5ee;color:#008F39;padding:2px 8px;border-radius:4px;font-weight:600;font-size:0.8rem;'>{st.session_state.user['rol']}</span></p>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0 16px 0;border-color:#e0e0e0;'>", unsafe_allow_html=True)

    # Estilos de precisión para garantizar tamaño idéntico en todas las tarjetas
    st.markdown("""
    <style>
    /* Tarjetas del dashboard: altura y porte estrictamente idénticos */
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
        height: 146px !important;
        min-height: 146px !important;
        max-height: 146px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        padding: 8px 8px 10px 8px !important;
        box-sizing: border-box !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        gap: 0px !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stElementContainer"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Cuadrícula compacta, simétrica y equilibrada: 6 columnas en Fila 1 y 6 columnas en Fila 2
    st.markdown("<div style='font-size:0.8rem;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>⚡ Gestión Diaria y Pedagógica</div>", unsafe_allow_html=True)
    r1_c1, r1_c2, r1_c3, r1_c4, r1_c5, r1_c6 = st.columns(6)

    with r1_c1:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>⏱️ Registro Atraso</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Ingreso y comprobantes</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'atraso', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_atraso", use_container_width=True):
                    navigate('atraso'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r1_c2:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>🚪 Registro Retiro</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Salidas anticipadas</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'retiro', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_retiro", use_container_width=True):
                    navigate('retiro'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r1_c3:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>📅 Asistencia</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Control diario escolar</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'asistencia', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_asistencia", use_container_width=True):
                    navigate('asistencia'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r1_c4:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>📝 Carga de Notas</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Registro y promedios</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'notas', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_notas", use_container_width=True):
                    navigate('notas'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r1_c5:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>🌱 Desarrollo Personal</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Informe y observaciones</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'desarrollo_personal', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_desarrollo_personal", use_container_width=True):
                    navigate('desarrollo_personal'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r1_c6:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>📚 Asignación Docente</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Asignaturas y docentes</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'asignaciones', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_asignaciones", use_container_width=True):
                    navigate('asignaciones'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown("<div style='font-size:0.8rem;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;'>⚙️ Cierre, Certificados y Administración</div>", unsafe_allow_html=True)
    r2_c1, r2_c2, r2_c3, r2_c4, r2_c5, r2_c6 = st.columns(6)

    with r2_c1:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>📊 Preacta Anual</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Promoción Decreto 67</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'preacta', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_preacta", use_container_width=True):
                    navigate('preacta'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r2_c2:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>📑 Informes y Certificados</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Notas y certificados</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'informes', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_informes_notas", use_container_width=True):
                    navigate('informes'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r2_c3:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>👥 Alumnos</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Fichas y nómina escolar</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'alumnos', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_alumnos", use_container_width=True):
                    navigate('alumnos'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r2_c4:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>🏫 Cursos</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Catálogo y jefaturas</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'cursos', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_cursos", use_container_width=True):
                    navigate('cursos'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r2_c5:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>👔 Funcionarios</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Personal y accesos</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'funcionarios', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_funcionarios", use_container_width=True):
                    navigate('funcionarios'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)

    with r2_c6:
        with st.container(border=True):
            st.markdown("<div class='modulo-card-title'>⚙️ Configuración</div>", unsafe_allow_html=True)
            st.markdown("<div class='modulo-card-sub'>Colegio, firmas y fechas</div>", unsafe_allow_html=True)
            if rol_tiene_permiso(rol_user_actual, 'configuracion', matriz_permisos_global):
                if st.button("Abrir Módulo", key="btn_configuracion", use_container_width=True):
                    navigate('configuracion'); st.rerun()
            else:
                st.markdown("<div class='modulo-card-locked'>🔒 Sin acceso</div>", unsafe_allow_html=True)


elif st.session_state.current_module == 'atraso':
    # 1. Insignia Institucional Centrada
    renderizar_insignia_universal()

    # 2. Cabecera del Módulo con botón de escape rápido
    col_titulo, col_escape = st.columns([3.5, 1])
    with col_titulo:
        st.title("⏰ Registro de Atrasos")
    with col_escape:
        st.write("") # Espaciador para bajar levemente el botón
        if st.button("🏠 Volver", key="btn_escape_sup_atraso", use_container_width=True):
            st.session_state.alumno_seleccionado_atraso = None
            navigate('home')
            st.rerun()
    st.write("---")
    
    sheet_alumnos, sheet_registros, sheet_notas, sheet_funcionarios, sheet_asignaciones = get_sheets()

    tab_reg_atraso, tab_rep_atraso = st.tabs(["📝 Registrar Atraso", "📊 Reportes y Estadísticas"])

    with tab_reg_atraso:

        if sheet_alumnos:
            try:
                df_alumnos = pd.DataFrame(sheet_alumnos.get_all_records())

                if not df_alumnos.empty:
                    import unicodedata
                    import streamlit.components.v1 as components

                    def normalizar_texto(texto):
                        t = str(texto).replace('\xa0', ' ')
                        t = "".join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
                        return " ".join(t.lower().split())

                    # Estandarizar columnas de manera ultra-robusta (para soportar singular/plural, mayúsculas/minúsculas)
                    df_alumnos.columns = [str(c).strip() for c in df_alumnos.columns]
                    col_nombre = next((c for c in df_alumnos.columns if 'nomb' in c.lower()), 'NOMBRES')
                    col_curso = next((c for c in df_alumnos.columns if 'curs' in c.lower()), 'CURSO')
                    col_rut = next((c for c in df_alumnos.columns if 'rut' in c.lower()), 'RUT')

                    # Variable de control para saber si ya se guardó
                    if "ultimo_rut_scroll_atraso" not in st.session_state:
                        st.session_state.ultimo_rut_scroll_atraso = None

                    # Confirmación de registro de atraso
                    if st.session_state.get('ultimo_voucher_atraso'):
                        voucher = st.session_state.pop('ultimo_voucher_atraso')
                        v_nom = voucher.get('nombre', 'ALUMNO')
                        v_cur = voucher.get('curso', '—')
                        st.success(f"✅ ¡Atraso registrado para **{v_nom}** ({v_cur})! Justificativo emitido a la ticketera.")

                    # Buscador normal
                    if "ver_busqueda_atraso" not in st.session_state:
                        st.session_state.ver_busqueda_atraso = 0
                    key_input_atraso = f"txt_busqueda_atraso_{st.session_state.ver_busqueda_atraso}"
                    busqueda_input = st.text_input("RUT, Apellido o Nombre del Alumno:", placeholder="Escriba para buscar...", key=key_input_atraso).strip()

                    if "alumno_seleccionado_atraso" not in st.session_state:
                        st.session_state.alumno_seleccionado_atraso = None

                    if 'ultimo_input_atraso' not in st.session_state:
                        st.session_state.ultimo_input_atraso = ""
                    if busqueda_input != st.session_state.ultimo_input_atraso:
                        st.session_state.alumno_seleccionado_atraso = None
                        st.session_state.ultimo_input_atraso = busqueda_input

                    # Filtro y ordenamiento por relevancia
                    if busqueda_input and col_nombre in df_alumnos.columns:
                        termino = normalizar_texto(busqueda_input)

                        # Función interna ultra-blindada para celda única de nombre completo
                        def calza_filtro_estricto(nombre_completo, rut_alumno):
                            nombre_norm = normalizar_texto(nombre_completo)
                            rut_norm = normalizar_texto(str(rut_alumno))

                            if termino in rut_norm:
                                return True

                            # Si buscan múltiples palabras juntas, permitimos coincidencia de subcadena directa
                            if len(termino.split()) > 1:
                                return termino in nombre_norm

                            palabras = nombre_norm.split()
                            if not palabras:
                                return False

                            for i, palabra in enumerate(palabras):
                                if len(palabras) >= 4:
                                    if i == 1 or i == (len(palabras) - 1):
                                        if not palabra.startswith(termino): 
                                            continue 

                                if palabra.startswith(termino):
                                    return True
                            return False

                        # Filtrado estricto
                        mask_filtrado = df_alumnos.apply(lambda x: calza_filtro_estricto(x[col_nombre], x[col_rut]), axis=1)
                        df_filtrado = df_alumnos[mask_filtrado].copy()

                        if not df_filtrado.empty:
                            st.write("### 👥 Seleccione al alumno correcto:")
                            df_filtrado['NOMBRES_NORM'] = df_filtrado[col_nombre].apply(normalizar_texto)
                            df_filtrado['EMPIEZA_CON'] = df_filtrado['NOMBRES_NORM'].str.startswith(termino)
                            df_filtrado = df_filtrado.sort_values(by=['EMPIEZA_CON', col_nombre], ascending=[False, True])

                            for idx, fila in df_filtrado.iterrows():
                                v_nombre = fila[col_nombre]
                                v_curso = fila.get(col_curso, 'N/A')
                                v_rut = fila.get(col_rut, 'N/A')

                                label_boton = f"👤 {v_nombre}  |  📌 {v_curso}  |  🆔 {v_rut}"
                                if st.button(label_boton, key=f"btn_alumno_{v_rut}_{idx}", use_container_width=True):
                                    st.session_state.alumno_seleccionado_atraso = {
                                        'nombre': v_nombre,
                                        'curso': v_curso,
                                        'rut': v_rut
                                    }
                        else:
                            st.warning("⚠️ No se encontraron alumnos con ese término.")
                    else:
                        st.info("💡 Ingrese un término arriba para desplegar los alumnos.")

                    if st.session_state.alumno_seleccionado_atraso is not None:
                        alumno = st.session_state.alumno_seleccionado_atraso

                        # Marcador de destino invisible para Atrasos
                        st.markdown("<div id='formulario_control_atraso'></div>", unsafe_allow_html=True)

                        # Inyección de Scroll limpia usando st.empty() para forzar refresco
                        placeholder_scroll = st.empty()
                        with placeholder_scroll:
                            components.html(
                                f"""
                                <script>
                                    // RUT: {alumno['rut']}
                                    window.parent.document.getElementById('formulario_control_atraso').scrollIntoView({{behavior: 'smooth'}});
                                </script>
                                """,
                                height=0,
                            )

                        st.markdown("---")
                        with st.container(border=True):
                            st.success("### Ficha de Confirmación")
                            st.write(f"**Nombre:** {alumno['nombre']}")
                            st.write(f"**Curso:** {alumno['curso']}")
                            st.write(f"**RUT:** {alumno['rut']}")
                            st.write("---")

                            # Selector de Motivos Estandarizado
                            opciones_motivos = ["Seleccione un motivo...", "Personal", "Se quedó dormido/a", "Hora médica/dental", "Problema de transporte", "Clima / Lluvia intensa", "Otro (Especificar)"]
                            motivo_seleccionado = st.selectbox("Motivo del atraso:", opciones_motivos, key="select_motivo_atraso")

                            motivo_final = ""
                            if motivo_seleccionado == "Otro (Especificar)":
                                motivo_final = st.text_input("Escriba el motivo específico:", key="txt_motivo_atraso_otro").strip()
                            elif motivo_seleccionado != "Seleccione un motivo...":
                                motivo_final = motivo_seleccionado

                            # Habilitar/Deshabilitar botón de confirmación
                            deshabilitar_boton = (motivo_seleccionado == "Seleccione un motivo...") or (motivo_seleccionado == "Otro (Especificar)" and not motivo_final)

                            if st.button("Confirmar Registro de Atraso", type="primary", key="btn_guardar_atraso_botones", disabled=deshabilitar_boton):
                                if sheet_registros:
                                    ahora = obtener_ahora_chile()

                                    # Asegurar encabezados si la hoja está vacía
                                    if not sheet_registros.row_values(1):
                                        sheet_registros.append_row(["Fecha", "Hora", "RUT", "Nombre", "Tipo", "Motivo", "Apoderado", "Vinculo", "Curso"])

                                    curso_alumno_final = alumno.get('curso', '')
                                    sheet_registros.append_row([
                                        ahora.strftime("%Y-%m-%d"),
                                        ahora.strftime("%H:%M:%S"),
                                        alumno['rut'],
                                        alumno['nombre'],
                                        "Atraso",
                                        motivo_final,
                                        "",
                                        "",
                                        curso_alumno_final
                                    ])

                                    # Notificar al teléfono del apoderado si está suscrito
                                    try:
                                        from utils.notifications import notificar_apoderados_rut
                                        notificar_apoderados_rut(
                                            rut=alumno['rut'],
                                            titulo="🔔 Escuela Villa Las Peñas",
                                            mensaje=f"Atraso registrado: {alumno['nombre']} ingresó a las {ahora.strftime('%H:%M')} hrs. Motivo: {motivo_final}."
                                        )
                                    except Exception:
                                        pass

                                    # Guardar datos del justificativo térmico de 8x8 cm
                                    st.session_state.ultimo_voucher_atraso = {
                                        'nombre': str(alumno['nombre']).strip().upper(),
                                        'curso': str(curso_alumno_final).strip(),
                                        'motivo': motivo_final,
                                        'fecha': ahora.strftime("%d/%m/%Y"),
                                        'hora': ahora.strftime("%H:%M")
                                    }
                                    st.session_state.alumno_seleccionado_atraso = None
                                    st.session_state.ultimo_rut_scroll_atraso = None
                                    st.session_state.ver_busqueda_atraso = st.session_state.get('ver_busqueda_atraso', 0) + 1
                                    st.rerun()
                                else:
                                    st.error("Error al guardar en la base de datos.")
                else:
                    st.warning("La base de datos de alumnos está vacía.")
            except Exception as e:
                if "Rerun" in type(e).__name__ or "ScriptControl" in type(e).__name__:
                    raise e
                st.error(f"Error inesperado: {e}")
        else:
            st.error("Error al conectar con la base de datos.")

        st.write("")
        if True:
            if st.button("⬅️ Volver al Dashboard Principal", key="btn_volver_atraso_botones"):
                st.session_state.alumno_seleccionado_atraso = None
                st.session_state.ultimo_rut_scroll_atraso = None
                navigate('home')
                st.rerun()



    with tab_rep_atraso:
        renderizar_reporte_atrasos(sheet_alumnos, sheet_registros)


elif st.session_state.current_module == 'retiro':
    # 1. Insignia Institucional Centrada
    renderizar_insignia_universal()

    # 2. Cabecera del Módulo con botón de escape rápido
    col_titulo, col_escape = st.columns([3.5, 1])
    with col_titulo:
        st.title("🚶‍♂️ Salida Anticipada / Retiro de Alumnos")
    with col_escape:
        st.write("") # Espaciador para bajar levemente el botón
        if st.button("🏠 Volver", key="btn_escape_sup_retiro", use_container_width=True):
            st.session_state.alumno_seleccionado_retiro = None
            st.session_state.pop("txt_nombre_apoderado", None)
            navigate('home')
            st.rerun()
    st.write("---")
    
    sheet_alumnos, sheet_registros, sheet_notas, sheet_funcionarios, sheet_asignaciones = get_sheets()

    tab_reg_retiro, tab_rep_retiro = st.tabs(["📝 Registrar Retiro", "📊 Reportes y Estadísticas"])

    with tab_reg_retiro:

        if sheet_alumnos:
            try:
                df_alumnos = pd.DataFrame(sheet_alumnos.get_all_records())

                if not df_alumnos.empty:
                    import unicodedata
                    import streamlit.components.v1 as components

                    def normalizar_texto(texto):
                        t = str(texto).replace('\xa0', ' ')
                        t = "".join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
                        return " ".join(t.lower().split())

                    # Estandarizar columnas del Sheets de manera ultra-robusta
                    df_alumnos.columns = [str(c).strip() for c in df_alumnos.columns]
                    col_nombre = next((c for c in df_alumnos.columns if 'nomb' in c.lower()), 'NOMBRES')
                    col_curso = next((c for c in df_alumnos.columns if 'curs' in c.lower()), 'CURSO')
                    col_rut = next((c for c in df_alumnos.columns if 'rut' in c.lower()), 'RUT')

                    if "ultimo_rut_scroll_retiro" not in st.session_state:
                        st.session_state.ultimo_rut_scroll_retiro = None

                    # Notificación de éxito si se acaba de registrar un retiro
                    if st.session_state.get('mensaje_exito_retiro'):
                        st.success(st.session_state.pop('mensaje_exito_retiro'))

                    if True:
                        # Flujo normal de búsqueda
                        if "ver_busqueda_retiro" not in st.session_state:
                            st.session_state.ver_busqueda_retiro = 0
                        key_input_retiro = f"txt_busqueda_retiro_{st.session_state.ver_busqueda_retiro}"
                        busqueda_input = st.text_input("RUT, Apellido o Nombre del Alumno a retirar:", placeholder="Escriba para buscar...", key=key_input_retiro).strip()

                        if "alumno_seleccionado_retiro" not in st.session_state:
                            st.session_state.alumno_seleccionado_retiro = None

                        if 'ultimo_input_retiro' not in st.session_state:
                            st.session_state.ultimo_input_retiro = ""
                        if busqueda_input != st.session_state.ultimo_input_retiro:
                            st.session_state.alumno_seleccionado_retiro = None
                            st.session_state.ultimo_input_retiro = busqueda_input
                            st.session_state.pop("txt_nombre_apoderado", None)

                        # Búsqueda global y ordenamiento por relevancia
                        if busqueda_input and col_nombre in df_alumnos.columns:
                            termino = normalizar_texto(busqueda_input)

                            # Función interna ultra-blindada para celda única de nombre completo
                            def calza_filtro_estricto(nombre_completo, rut_alumno):
                                nombre_norm = normalizar_texto(nombre_completo)
                                rut_norm = normalizar_texto(str(rut_alumno))

                                if termino in rut_norm:
                                    return True

                                # Si buscan múltiples palabras juntas, permitimos coincidencia de subcadena directa
                                if len(termino.split()) > 1:
                                    return termino in nombre_norm

                                palabras = nombre_norm.split()
                                if not palabras:
                                    return False

                                for i, palabra in enumerate(palabras):
                                    if len(palabras) >= 4:
                                        if i == 1 or i == (len(palabras) - 1):
                                            if not palabra.startswith(termino): 
                                                continue 

                                    if palabra.startswith(termino):
                                        return True
                                return False

                            # Filtrado estricto
                            mask_filtrado = df_alumnos.apply(lambda x: calza_filtro_estricto(x[col_nombre], x[col_rut]), axis=1)
                            df_filtrado = df_alumnos[mask_filtrado].copy()

                            if not df_filtrado.empty:
                                st.write("### 👥 Seleccione al alumno que se retira:")
                                df_filtrado['NOMBRES_NORM'] = df_filtrado[col_nombre].apply(normalizar_texto)
                                df_filtrado['EMPIEZA_CON'] = df_filtrado['NOMBRES_NORM'].str.startswith(termino)
                                df_filtrado = df_filtrado.sort_values(by=['EMPIEZA_CON', col_nombre], ascending=[False, True])

                                for idx, fila in df_filtrado.iterrows():
                                    v_nombre = fila[col_nombre]
                                    v_curso = fila.get(col_curso, 'N/A')
                                    v_rut = fila.get(col_rut, 'N/A')

                                    label_boton = f"👤 {v_nombre}  |  📌 {v_curso}  |  🆔 {v_rut}"
                                    if st.button(label_boton, key=f"btn_retiro_{v_rut}_{idx}", use_container_width=True):
                                        st.session_state.alumno_seleccionado_retiro = {
                                            'nombre': v_nombre,
                                            'curso': v_curso,
                                            'rut': v_rut
                                        }
                                        st.session_state.pop("txt_nombre_apoderado", None)
                                        st.rerun()
                            else:
                                st.warning("⚠️ No se encontraron alumnos con ese término.")
                        else:
                            st.info("💡 Ingrese un término arriba para desplegar los alumnos de forma segura.")

                        # 2. FICHA DE RETIRO (Se activa al seleccionar un alumno)
                        if st.session_state.alumno_seleccionado_retiro is not None:
                            alumno = st.session_state.alumno_seleccionado_retiro

                            # Marcador de destino para el autoscroll
                            st.markdown("<div id='formulario_control_retiro'></div>", unsafe_allow_html=True)

                            # Inyección de Scroll limpia usando st.empty() para forzar refresco
                            placeholder_scroll_ret = st.empty()
                            with placeholder_scroll_ret:
                                components.html(
                                    f"""
                                    <script>
                                        // RUT: {alumno['rut']}
                                        window.parent.document.getElementById('formulario_control_retiro').scrollIntoView({{behavior: 'smooth'}});
                                    </script>
                                    """,
                                    height=0,
                                )

                            st.markdown("---")
                            with st.container(border=True):
                                st.success("### 📋 Ficha de Control de Retiro")
                                st.write(f"**Nombre Alumno:** {alumno['nombre']}")
                                st.write(f"**Curso:** {alumno['curso']}")
                                st.write(f"**RUT:** {alumno['rut']}")

                                # Succión de Espacio Bajo el RUT
                                st.markdown(
                                    """
                                    <div style="margin-bottom: -50px; line-height: 0; font-size: 0;">&nbsp;</div>
                                    """, 
                                    unsafe_allow_html=True
                                )

                                # Inputs Estandarizados y Blindaje
                                import re

                                opciones_retiro = [
                                    "Seleccione un motivo...",
                                    "Personal",
                                    "Enfermedad / Malestar",
                                    "Hora médica/dental",
                                    "Otro (Especificar)"
                                ]
                                motivo_raw = st.selectbox("Motivo del Retiro Anticipado:", opciones_retiro, key="select_motivo_retiro", index=0)

                                if not motivo_raw:
                                    motivo_seleccionado = opciones_retiro[0]
                                else:
                                    motivo_seleccionado = motivo_raw

                                motivo_final = ""
                                if motivo_seleccionado == "Otro (Especificar)":
                                    motivo_final = st.text_input("Escriba el motivo específico del retiro:", key="txt_motivo_retiro_otro").strip()
                                elif motivo_seleccionado != "Seleccione un motivo...":
                                    motivo_final = motivo_seleccionado

                                # Campo de nombre de apoderado con validación segura
                                nombre_apoderado = st.text_input("Nombre Completo del Apoderado:", key="txt_nombre_apoderado").strip()
                                nombre_tiene_digitos = any(char.isdigit() for char in nombre_apoderado)
                                if nombre_tiene_digitos:
                                    st.error("⚠️ Solo se permiten letras en el nombre del apoderado.")

                                opciones_parentesco = [
                                    "Seleccione parentesco...",
                                    "Mamá",
                                    "Papá",
                                    "Abuela/o",
                                    "Hermana/o",
                                    "Tía/o",
                                    "Otro (Especificar)"
                                ]
                                parentesco_raw = st.selectbox("Parentesco o Relación con el alumno:", opciones_parentesco, key="select_parentesco_retiro", index=0)

                                if not parentesco_raw:
                                    parentesco_seleccionado = opciones_parentesco[0]
                                else:
                                    parentesco_seleccionado = parentesco_raw

                                parentesco_final = ""
                                if parentesco_seleccionado == "Otro (Especificar)":
                                    raw_parentesco_otro = st.text_input("Escriba la relación específica (Ej: Furgon, Vecino):", key="txt_parentesco_otro").strip()
                                    parentesco_final = re.sub(r'[0-9]', '', raw_parentesco_otro).strip()
                                    if re.search(r'\d', raw_parentesco_otro):
                                        st.error("⚠️ Solo se permiten letras en la relación.")
                                elif parentesco_seleccionado != "Seleccione parentesco...":
                                    parentesco_final = parentesco_seleccionado

                                campos_incompletos = (motivo_seleccionado == "Seleccione un motivo...") or \
                                                     (motivo_seleccionado == "Otro (Especificar)" and not motivo_final) or \
                                                     (not nombre_apoderado) or \
                                                     nombre_tiene_digitos or \
                                                     (parentesco_seleccionado == "Seleccione parentesco...") or \
                                                     (parentesco_seleccionado == "Otro (Especificar)" and not parentesco_final)

                                if st.button("Confirmar Registro de Retiro", type="primary", key="btn_guardar_retiro_definitivo", disabled=campos_incompletos):
                                    if sheet_registros:
                                        ahora = obtener_ahora_chile()
                                        fecha_str = ahora.strftime("%Y-%m-%d")
                                        hora_str = ahora.strftime("%H:%M:%S")

                                        if not sheet_registros.row_values(1):
                                            sheet_registros.append_row(["Fecha", "Hora", "RUT", "Nombre", "Tipo", "Motivo", "Apoderado", "Vinculo", "Curso"])

                                        sheet_registros.append_row([
                                            fecha_str,
                                            hora_str,
                                            alumno['rut'],
                                            alumno['nombre'],
                                            "Retiro",
                                            motivo_final,
                                            nombre_apoderado,
                                            parentesco_final,
                                            alumno.get('curso', '')
                                        ])

                                        # Notificar al teléfono del apoderado si está suscrito
                                        try:
                                            from utils.notifications import notificar_apoderados_rut
                                            notificar_apoderados_rut(
                                                rut=alumno['rut'],
                                                titulo="🔔 Escuela Villa Las Peñas",
                                                mensaje=f"Retiro registrado: {alumno['nombre']} fue retirado/a a las {hora_str} hrs por {nombre_apoderado} ({parentesco_final}). Motivo: {motivo_final}."
                                            )
                                        except Exception:
                                            pass

                                        st.session_state.mensaje_exito_retiro = f"✅ Retiro registrado exitosamente para **{alumno['nombre']}** ({alumno.get('curso', '')}) a las **{hora_str}** hrs."
                                        st.session_state.alumno_seleccionado_retiro = None
                                        st.session_state.ultimo_rut_scroll_retiro = None
                                        st.session_state.pop("txt_nombre_apoderado", None)
                                        st.session_state.ver_busqueda_retiro = st.session_state.get('ver_busqueda_retiro', 0) + 1
                                        st.rerun()
                                    else:
                                        st.error("Error al conectar con la base de datos de registros.")

                             # El scroll se maneja al inicio de la ficha de forma reactiva por key
            except Exception as e:
                st.error(f"Error inesperado en el módulo de retiros: {e}")
        else:
            st.error("Error de conexión con la base de datos.")

        st.write("")
        if st.button("⬅️ Volver al Dashboard Principal", key="btn_volver_retiro_botones"):
            st.session_state.alumno_seleccionado_retiro = None
            st.session_state.ultimo_rut_scroll_retiro = None
            st.session_state.pop("txt_nombre_apoderado", None)
            navigate('home')
            st.rerun()


    with tab_rep_retiro:
        renderizar_reporte_retiros(sheet_alumnos, sheet_registros)


elif st.session_state.current_module == 'alumnos':
    # Insignia Institucional Centrada
    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>👥 Gestión y Edición de Alumnos</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_alumnos", use_container_width=True):
            st.session_state.pop('alumno_edit_tag', None)
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 12px 0;'>", unsafe_allow_html=True)
    
    sheet_alumnos, sheet_registros, sheet_notas, sheet_funcionarios, sheet_asignaciones = get_sheets()
    
    if not sheet_alumnos:
        st.error("❌ Error de conexión con la base de datos de Google Sheets.")
    else:
        try:
            # Manejo de caché en session_state para respetar las cuotas de Google Sheets y evitar error 429
            if 'df_alumnos_cache' not in st.session_state or st.session_state.df_alumnos_cache is None:
                registros_raw = sheet_alumnos.get_all_records()
                df_loaded = pd.DataFrame(registros_raw) if registros_raw else pd.DataFrame()
                if not df_loaded.empty:
                    df_loaded.columns = [str(c).strip() for c in df_loaded.columns]
                st.session_state.df_alumnos_cache = df_loaded

            df_alumnos_all = st.session_state.df_alumnos_cache.copy()
            
            if not df_alumnos_all.empty:
                df_alumnos_all.columns = [str(c).strip() for c in df_alumnos_all.columns]
            
            col_c = next((c for c in df_alumnos_all.columns if 'curs' in c.lower()), 'Curso')
            col_n = next((c for c in df_alumnos_all.columns if 'nomb' in c.lower()), 'Nombre')
            col_r = next((c for c in df_alumnos_all.columns if 'rut' in c.lower()), 'RUT')
            col_o = next((c for c in df_alumnos_all.columns if any(x in c.lower() for x in ['list', 'orden', 'n°', 'nro']) and 'matr' not in c.lower()), 'N° Lista')
            col_mat = next((c for c in df_alumnos_all.columns if 'matr' in c.lower() and 'fec' not in c.lower()), 'N° Matrícula')
            col_f_mat = next((c for c in df_alumnos_all.columns if 'matr' in c.lower() and ('fec' in c.lower() or 'date' in c.lower())), 'Fecha Matrícula')
            col_tel = next((c for c in df_alumnos_all.columns if 'tel' in c.lower() or 'fono' in c.lower() or 'apod' in c.lower()), 'Teléfono Apoderado')
            col_baja = next((c for c in df_alumnos_all.columns if 'baja' in c.lower() or 'retir' in c.lower()), 'Fecha Baja')
            col_alta = next((c for c in df_alumnos_all.columns if 'alta' in c.lower() or 'ingr' in c.lower()), 'Fecha Alta')
            col_nac = next((c for c in df_alumnos_all.columns if 'nac' in c.lower()), 'Fecha Nacimiento')

            # =========================================================================
            # LÓGICA DE UNIFICACIÓN Y CANONIZACIÓN DE CURSOS (CERO DUPLICADOS)
            # =========================================================================
            def normalizar_cadena_curso(texto):
                if not texto: return ""
                t = str(texto).strip().lower()
                t = t.replace('°', '').replace('º', '').replace('.', '')
                t = t.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                return " ".join(t.split())

            def extraer_clave_curso(texto):
                """Devuelve tupla (nivel_norm, letra_norm) para deduplicación estricta."""
                norm = normalizar_cadena_curso(texto)
                partes = norm.split()
                if not partes:
                    return ("", "a")
                if len(partes) > 1 and partes[-1] in ['a', 'b', 'c', 'd']:
                    nivel = " ".join(partes[:-1])
                    letra = partes[-1]
                else:
                    nivel = norm
                    letra = "a"

                # Erradicar Prekinder y Kinder convirtiéndolos obligatoriamente a NT1 y NT2
                if any(x in nivel for x in ['prekinder', 'pre-kinder', 'pre kinder', 'prek', 'pre-k']):
                    nivel = "nt1"
                elif any(x in nivel for x in ['kinder', 'kndr']) and 'pre' not in nivel:
                    nivel = "nt2"
                elif nivel in ['nt 1', 'nt-1', 'transicion 1', 'primer nivel de transicion']:
                    nivel = "nt1"
                elif nivel in ['nt 2', 'nt-2', 'transicion 2', 'segundo nivel de transicion']:
                    nivel = "nt2"

                return (nivel, letra)

            def calza_nombre_curso(c_al, c_sel):
                if not c_al or not c_sel: return False
                if str(c_sel).strip() == "🔍 Todos los Cursos": return True
                return extraer_clave_curso(c_al) == extraer_clave_curso(c_sel)

            # Cursos base institucionales con su letra A
            CURSOS_BASE_OFICIALES = [
                "NT1 A", "NT2 A",
                "1° Básico A", "2° Básico A", "3° Básico A", "4° Básico A",
                "5° Básico A", "6° Básico A", "7° Básico A", "8° Básico A"
            ]

            target_headers = ["N° Lista", "N° Matrícula", "RUT", "Nombre", "Curso", "Fecha Nacimiento", "Fecha Matrícula", "Fecha Alta", "Fecha Baja", "Estado", "Teléfono Apoderado"]

            def parse_date_to_obj(val, default_date=None):
                """Convierte de forma segura un string de fecha a objeto datetime.date para selectores st.date_input."""
                if default_date is None:
                    default_date = datetime.date.today()
                if not val or str(val).strip().lower() in ['', 'nan', 'none', 'nat', 'null', '-']:
                    return default_date
                val_s = str(val).strip()
                formatos = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y"]
                for fmt in formatos:
                    try:
                        return datetime.datetime.strptime(val_s, fmt).date()
                    except Exception:
                        pass
                m_dmy = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})', val_s)
                if m_dmy:
                    try:
                        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
                        if y < 100: y += 2000
                        return datetime.date(y, m, d)
                    except Exception:
                        pass
                return default_date

            def obtener_siguiente_matricula(df):
                """Calcula el siguiente número de matrícula correlativo."""
                if df.empty:
                    return 1
                for col in df.columns:
                    if 'matr' in col.lower() and 'fec' not in col.lower():
                        nums = pd.to_numeric(df[col], errors='coerce').dropna()
                        if not nums.empty:
                            m_val = int(nums.max())
                            if m_val > 0:
                                return m_val + 1
                return len(df) + 1

            def obtener_matricula_alumno(r):
                """Obtiene el número de matrícula asignado a un estudiante."""
                for col in (r.index if hasattr(r, 'index') else r.keys()):
                    if 'matr' in str(col).lower() and 'fec' not in str(col).lower():
                        val = pd.to_numeric(r[col], errors='coerce')
                        if pd.notnull(val) and int(val) > 0:
                            return int(val)
                return 1

            def obtener_fecha_matricula_alumno(r):
                """Obtiene la fecha de matrícula de un estudiante."""
                for col in (r.index if hasattr(r, 'index') else r.keys()):
                    cl = str(col).lower()
                    if 'matr' in cl and ('fec' in cl or 'date' in cl):
                        v = str(r[col]).strip()
                        if v and v.lower() not in ['', 'nan', 'none']:
                            return v
                if 'Fecha Alta' in r:
                    v = str(r['Fecha Alta']).strip()
                    if v and v.lower() not in ['', 'nan', 'none']:
                        return v
                return ""

            def es_alumno_retirado(r):
                """Detecta de forma infalible si un alumno está retirado revisando todas las columnas posibles."""
                for k in (r.index if hasattr(r, 'index') else r.keys()):
                    kl = str(k).lower().strip()
                    val = str(r[k]).strip().lower()
                    if val in ['', 'nan', 'none', 'nat', 'null', '-']:
                        continue
                    if 'baja' in kl or 'retir' in kl:
                        if val not in ['activo', 'no', 'false', '0']:
                            return True
                    if 'est' in kl:
                        if any(term in val for term in ['retir', 'baja', 'inactiv', 'desactiv']):
                            return True
                return False

            def obtener_fecha_retiro(r):
                """Obtiene la fecha de retiro registrada si existe."""
                for k in (r.index if hasattr(r, 'index') else r.keys()):
                    kl = str(k).lower().strip()
                    val = str(r[k]).strip()
                    if val and val.lower() not in ['', 'nan', 'none', 'nat', 'null', 'activo', 'retirado', 'retirada', 'inactivo', '-']:
                        if 'baja' in kl or 'retir' in kl:
                            return val
                return ""

            cursos_disponibles = obtener_cursos_oficiales_sistema()

            tab_nomina_al, tab_nuevo_al, tab_carga_al = st.tabs([
                "📋 Nómina y Edición de Alumnos",
                "➕ Inscribir Nuevo Alumno",
                "📤 Carga Masiva (Excel / CSV)"
            ])

            with tab_nomina_al:
                # Barra de filtros superior limpia y espaciosa
                col_sel_c, col_busq_al = st.columns([2.5, 4.5])
                with col_sel_c:
                    opciones_cursos = ["🔍 Todos los Cursos"] + cursos_disponibles
                    idx_c_sel = 0  # Por defecto 'Todos los Cursos' o el curso recordado
                    if st.session_state.get('alumno_gest_curso') in opciones_cursos:
                        idx_c_sel = opciones_cursos.index(st.session_state.alumno_gest_curso)
                    elif len(opciones_cursos) > 1:
                        idx_c_sel = 1
                    curso_gest = st.selectbox("📚 Curso:", opciones_cursos, index=idx_c_sel, key="sel_curso_gest_alumno")
                    st.session_state.alumno_gest_curso = curso_gest

                with col_busq_al:
                    txt_buscar_al = st.text_input("🔍 Buscar por Nombre o RUT:", placeholder="Ej: Perez o 12345678", key="txt_buscar_alumno_in").strip()

                # Preparar datos filtrados con coincidencia flexible
                df_filtrado_al = df_alumnos_all.copy()
                if not df_filtrado_al.empty:
                    if col_c in df_filtrado_al.columns and curso_gest != "🔍 Todos los Cursos":
                        df_filtrado_al = df_filtrado_al[df_filtrado_al[col_c].apply(lambda x: calza_nombre_curso(x, curso_gest))]

                    if col_o in df_filtrado_al.columns:
                        df_filtrado_al['_ord'] = pd.to_numeric(df_filtrado_al[col_o], errors='coerce').fillna(999).astype(int)
                    else:
                        df_filtrado_al['_ord'] = 999

                    if txt_buscar_al:
                        b_low = txt_buscar_al.lower().replace('.', '')
                        mask = df_filtrado_al.apply(
                            lambda r: b_low in str(r.get(col_n, '')).lower() or b_low in str(r.get(col_r, '')).lower().replace('.', ''),
                            axis=1
                        )
                        df_filtrado_al = df_filtrado_al[mask]

                    df_filtrado_al = df_filtrado_al.sort_values(by=[col_c, '_ord']) if curso_gest == "🔍 Todos los Cursos" else df_filtrado_al.sort_values(by=['_ord'])

                # Resumen métrico
                cant_tot = len(df_filtrado_al)
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:6px 12px;margin:4px 0 12px 0;font-size:0.82rem;color:#334155;'>"
                    f"📊 <b>{curso_gest}:</b> Mostrando <b>{cant_tot}</b> estudiantes &nbsp;|&nbsp; "
                    f"<i>Haz clic en una fila de la tabla para abrir y editar la ficha del alumno</i></div>",
                    unsafe_allow_html=True
                )

                col_tabla_al, col_ficha_al = st.columns([3.3, 2.7], gap="medium")

                with col_tabla_al:
                    st.markdown(
                        "<div style='font-weight:700;font-size:0.88rem;color:#1e293b;margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;'>"
                        "<span>📋 Nómina de Estudiantes</span>"
                        "<span style='font-size:0.75rem;font-weight:400;color:#64748b;'>Selecciona una fila para cargar su ficha 👉</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )

                    if not df_filtrado_al.empty:
                        def texto_tachado_fn(txt):
                            s = str(txt).strip()
                            if not s or s == "-":
                                return s
                            return "".join((ch + "\u0336") if ch != " " else " " for ch in s)

                        filas_vista = []
                        for _, r in df_filtrado_al.iterrows():
                            ret = es_alumno_retirado(r)
                            ord_val = r['_ord']
                            ord_str = str(int(ord_val)) if pd.notnull(ord_val) and int(ord_val) < 900 else "-"
                            rut_str = str(r[col_r]).replace('.', '').strip()
                            nom_str = str(r[col_n]).strip().upper()

                            if ret:
                                filas_vista.append({
                                    "N°": texto_tachado_fn(ord_str),
                                    "RUT": texto_tachado_fn(rut_str),
                                    "Nombre": texto_tachado_fn(nom_str),
                                    "Estado": "Retirado"
                                })
                            else:
                                filas_vista.append({
                                    "N°": ord_str,
                                    "RUT": rut_str,
                                    "Nombre": nom_str,
                                    "Estado": "Activo"
                                })

                        df_vista_al = pd.DataFrame(filas_vista)

                        try:
                            def estilo_filas_nomina(row):
                                if "retirado" in str(row.get("Estado", "")).lower():
                                    return ["color: #dc2626;"] * len(row)
                                return [""] * len(row)

                            df_para_mostrar = df_vista_al.style.apply(estilo_filas_nomina, axis=1)
                        except Exception:
                            df_para_mostrar = df_vista_al

                        event_al = st.dataframe(
                            df_para_mostrar,
                            use_container_width=True,
                            hide_index=True,
                            height=430,
                            selection_mode="single-row",
                            on_select="rerun",
                            key="tabla_interactiva_alumnos",
                            column_config={
                                "N°": st.column_config.TextColumn(
                                    "N°",
                                    help="Número de lista del estudiante"
                                ),
                                "RUT": st.column_config.TextColumn(
                                    "RUT",
                                    help="RUT del estudiante"
                                ),
                                "Nombre": st.column_config.TextColumn(
                                    "Nombre del Estudiante",
                                    help="Nombre completo del estudiante"
                                ),
                                "Estado": st.column_config.TextColumn(
                                    "Estado",
                                    help="Estado del estudiante"
                                )
                            }
                        )

                        sel_rows = []
                        if event_al:
                            sel = getattr(event_al, 'selection', None)
                            if sel is not None:
                                if isinstance(sel, dict):
                                    sel_rows = sel.get('rows', [])
                                else:
                                    sel_rows = getattr(sel, 'rows', [])

                        if sel_rows and len(sel_rows) > 0:
                            idx_sel_row = sel_rows[0]
                            if 0 <= idx_sel_row < len(df_filtrado_al):
                                rut_clickeado = str(df_filtrado_al.iloc[idx_sel_row][col_r]).replace('.', '').strip()
                                if st.session_state.get('alumno_sel_rut') != rut_clickeado:
                                    st.session_state.alumno_sel_rut = rut_clickeado
                                    st.rerun()
                    else:
                        st.info("💡 No se encontraron estudiantes con los filtros actuales.")

                with col_ficha_al:
                    rut_actual_sel = st.session_state.get('alumno_sel_rut')

                    if rut_actual_sel and not df_filtrado_al.empty and col_r in df_filtrado_al.columns:
                        ruts_actuales = [str(x).replace('.','').strip().lower() for x in df_filtrado_al[col_r].tolist()]
                        if rut_actual_sel.replace('.','').strip().lower() not in ruts_actuales:
                            rut_actual_sel = None
                            st.session_state.alumno_sel_rut = None

                    if not rut_actual_sel:
                        st.markdown(
                            "<div style='border:2px dashed #cbd5e1;border-radius:8px;padding:36px 20px;text-align:center;background:#f8fafc;color:#64748b;margin-top:10px;'>"
                            "<div style='font-size:2rem;margin-bottom:8px;'>👈</div>"
                            "<div style='font-weight:600;font-size:0.95rem;color:#334155;'>Ningún Alumno Seleccionado</div>"
                            "<div style='font-size:0.8rem;margin-top:4px;'>Haz clic en cualquier fila del listado a la izquierda para cargar y editar aquí los datos del estudiante.</div>"
                            "</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        alumno_row = df_alumnos_all[df_alumnos_all[col_r].astype(str).str.replace('.','', regex=False).str.strip().str.lower() == rut_actual_sel.replace('.','').strip().lower()]
                        if alumno_row.empty:
                            st.warning("No se encontraron los datos del estudiante seleccionado.")
                        else:
                            r_dat = alumno_row.iloc[0]
                            val_mat = obtener_matricula_alumno(r_dat)
                            val_f_mat = obtener_fecha_matricula_alumno(r_dat)
                            val_ord = int(pd.to_numeric(r_dat.get(col_o, 1), errors='coerce') or 1)
                            val_rut = str(r_dat.get(col_r, '')).strip()
                            val_nom = str(r_dat.get(col_n, '')).strip()
                            val_curso_f = str(r_dat.get(col_c, curso_gest)).strip()
                            val_tel = str(r_dat.get(col_tel, '')).strip()
                            if val_tel in ['nan', 'None']: val_tel = ""
                            val_nac = str(r_dat.get(col_nac, '')).strip()
                            if val_nac in ['nan', 'None']: val_nac = ""
                            val_alta = str(r_dat.get(col_alta, '')).strip()
                            if val_alta in ['nan', 'None']: val_alta = ""
                            val_baja_fecha = obtener_fecha_retiro(r_dat)
                            es_ret = es_alumno_retirado(r_dat)
                            val_est = "Retirado" if es_ret else "Activo"

                            # Clave dinámica unívoca por alumno para garantizar reactividad instantánea en pantalla
                            rut_slug = re.sub(r'[^a-zA-Z0-9]', '', str(rut_actual_sel))

                            # Parseo de fechas a objetos datetime.date para selectores tipo calendario
                            date_mat_obj = parse_date_to_obj(val_f_mat, default_date=datetime.date.today())
                            date_nac_obj = parse_date_to_obj(val_nac, default_date=datetime.date(2015, 1, 1))
                            date_baja_obj = parse_date_to_obj(val_baja_fecha, default_date=datetime.date.today())

                            if es_ret:
                                st.markdown(
                                    f"<div style='background:#fef2f2;border-left:4px solid #b91c1c;border-radius:4px;padding:8px 12px;margin-bottom:10px;'>"
                                    f"<div style='font-weight:700;font-size:0.95rem;color:#991b1b;'>{val_nom} (RETIRADO)</div>"
                                    f"<div style='font-size:0.78rem;color:#7f1d1d;'>RUT: <b>{val_rut}</b> &nbsp;|&nbsp; Matrícula: <b>N° {val_mat}</b> &nbsp;|&nbsp; Curso: <b>{val_curso_f}</b> &nbsp;|&nbsp; Fecha Retiro: <b>{val_baja_fecha}</b></div>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                            else:
                                st.markdown(
                                    f"<div style='background:#f8fafc;border-left:4px solid #166534;border-radius:4px;padding:8px 12px;margin-bottom:10px;'>"
                                    f"<div style='font-weight:700;font-size:0.95rem;color:#0f172a;'>{val_nom}</div>"
                                    f"<div style='font-size:0.78rem;color:#475569;'>RUT: <b>{val_rut}</b> &nbsp;|&nbsp; Matrícula: <b>N° {val_mat}</b> &nbsp;|&nbsp; Curso: <b>{val_curso_f}</b> &nbsp;|&nbsp; Estado: <b>Activo</b></div>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                            with st.container(border=True):
                                f1, f_mat_col, f2 = st.columns([1, 1.2, 1.8])
                                with f1:
                                    in_orden = st.number_input("N° Lista:", min_value=1, max_value=200, value=val_ord, step=1, key=f"ed_ord_{rut_slug}")
                                with f_mat_col:
                                    val_mat_num = int(pd.to_numeric(val_mat, errors='coerce') or 0)
                                    in_matricula = st.number_input("N° Matrícula:", min_value=0, max_value=99999, value=val_mat_num, step=1, key=f"ed_mat_{rut_slug}", help="Número oficial de matrícula del estudiante.")
                                with f2:
                                    # RUT 100% BLOQUEADO EN EDICIÓN
                                    st.text_input("RUT (Protegido / No editable):", value=val_rut, disabled=True, key=f"ed_rut_bloqueado_{rut_slug}")

                                in_nom = st.text_input("Nombre Completo:", value=val_nom, key=f"ed_nom_{rut_slug}").strip()

                                f3, f4 = st.columns(2)
                                with f3:
                                    idx_cf = 0
                                    for i_cd, cd in enumerate(cursos_disponibles):
                                        if calza_nombre_curso(val_curso_f, cd):
                                            idx_cf = i_cd
                                            break
                                    in_curso_dest = st.selectbox("Curso:", cursos_disponibles, index=idx_cf, key=f"ed_curso_{rut_slug}")
                                with f4:
                                    in_estado = st.selectbox("Estado:", ["Activo", "Retirado"], index=1 if es_ret else 0, key=f"ed_est_{rut_slug}")

                                f_d1, f_d2 = st.columns(2)
                                with f_d1:
                                    in_fecha_mat = st.date_input("Fecha de Matrícula:", value=date_mat_obj, format="DD/MM/YYYY", key=f"ed_f_mat_{rut_slug}", help="Fecha en que se formaliza la matrícula del estudiante.")
                                with f_d2:
                                    in_fecha_nac = st.date_input("Fecha de Nacimiento:", value=date_nac_obj, min_value=datetime.date(1990, 1, 1), max_value=datetime.date.today(), format="DD/MM/YYYY", key=f"ed_f_nac_{rut_slug}")

                                in_fecha_retiro = None
                                if in_estado == "Retirado":
                                    in_fecha_retiro = st.date_input("Fecha de Retiro:", value=date_baja_obj, format="DD/MM/YYYY", key=f"ed_f_baja_{rut_slug}", help="Fecha legal en que se hace efectiva la baja/retiro del estudiante.")

                                in_tel = st.text_input("Teléfono Apoderado:", value=val_tel, key=f"ed_tel_{rut_slug}").strip()

                                st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

                                if st.button("💾 Guardar Cambios del Estudiante", type="primary", use_container_width=True, key=f"btn_save_ed_{rut_slug}"):
                                    if not in_nom:
                                         st.error("⚠️ El nombre del estudiante no puede quedar vacío.")
                                    else:
                                        with st.spinner("Guardando cambios..."):
                                            try:
                                                recs_fresh = sheet_alumnos.get_all_records()
                                                df_fresh = pd.DataFrame(recs_fresh) if recs_fresh else pd.DataFrame()
                                                df_fresh.columns = [str(c).strip() for c in df_fresh.columns]

                                                rut_buscar = val_rut.replace('.', '').strip()
                                                df_fresh['RUT_NORM'] = df_fresh['RUT'].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()
                                                m_idx = df_fresh[df_fresh['RUT_NORM'] == rut_buscar.lower()]

                                                if not m_idx.empty:
                                                    idx_target = m_idx.index[0]
                                                    baja_val = in_fecha_retiro.strftime("%d-%m-%Y") if (in_estado == "Retirado" and in_fecha_retiro) else ""
                                                    f_mat_val = in_fecha_mat.strftime("%d-%m-%Y") if in_fecha_mat else ""
                                                    f_nac_val = in_fecha_nac.strftime("%d-%m-%Y") if in_fecha_nac else ""
                                                    mat_val = str(int(in_matricula)) if in_matricula > 0 else ""

                                                    # Asegurar columnas destino en el DataFrame
                                                    for col_th in target_headers:
                                                        if col_th not in df_fresh.columns:
                                                            df_fresh[col_th] = ""

                                                    df_fresh.at[idx_target, 'N° Lista'] = int(in_orden)
                                                    df_fresh.at[idx_target, 'N° Matrícula'] = mat_val
                                                    df_fresh.at[idx_target, 'Nombre'] = in_nom.upper()
                                                    df_fresh.at[idx_target, 'Curso'] = str(in_curso_dest)
                                                    df_fresh.at[idx_target, 'Fecha Nacimiento'] = f_nac_val
                                                    df_fresh.at[idx_target, 'Fecha Matrícula'] = f_mat_val
                                                    df_fresh.at[idx_target, 'Fecha Baja'] = baja_val
                                                    df_fresh.at[idx_target, 'Estado'] = in_estado
                                                    df_fresh.at[idx_target, 'Teléfono Apoderado'] = in_tel

                                                    for col_k in df_fresh.columns:
                                                        col_kl = str(col_k).lower().strip()
                                                        if 'est' in col_kl and col_k != 'Estado':
                                                            df_fresh.at[idx_target, col_k] = in_estado
                                                        elif ('baja' in col_kl or 'retir' in col_kl) and col_k not in ['Fecha Baja', 'Estado']:
                                                            df_fresh.at[idx_target, col_k] = baja_val
                                                        elif 'matr' in col_kl and ('fec' in col_kl or 'date' in col_kl) and col_k != 'Fecha Matrícula':
                                                            df_fresh.at[idx_target, col_k] = f_mat_val
                                                        elif 'matr' in col_kl and 'fec' not in col_kl and col_k != 'N° Matrícula':
                                                            df_fresh.at[idx_target, col_k] = mat_val

                                                    df_fresh['N° Lista'] = pd.to_numeric(df_fresh['N° Lista'], errors='coerce').fillna(999).astype(int)
                                                    df_fresh = df_fresh.sort_values(by=['Curso', 'N° Lista'])

                                                    cols_to_save = [c for c in target_headers if c in df_fresh.columns] + [c for c in df_fresh.columns if c not in target_headers and c != 'RUT_NORM']
                                                    df_fresh = df_fresh[cols_to_save].fillna("")

                                                    sheet_alumnos.clear()
                                                    sheet_alumnos.update(values=[df_fresh.columns.tolist()] + df_fresh.values.tolist())
                                                    st.session_state.df_alumnos_cache = None
                                                    st.success(f"✅ ¡Estudiante **{in_nom}** actualizado exitosamente!")
                                                    st.rerun()
                                            except Exception as e:
                                                st.error(f"Error al actualizar: {e}")

            with tab_nuevo_al:
                st.markdown("### ➕ Inscribir y Matricular Nuevo Alumno")
                st.write("Registra un nuevo estudiante en el sistema oficial. Los datos ingresados se integrarán automáticamente a la nómina, libro de clases, asistencia y futuros certificados de alumno regular.")

                # Siguiente número de matrícula sugerido
                next_mat_sug = obtener_siguiente_matricula(df_alumnos_all)

                # Curso predeterminado: el seleccionado actualmente en curso_gest si coincide
                idx_c_nuevo = 0
                for i_cd, cd in enumerate(cursos_disponibles):
                    if calza_nombre_curso(curso_gest, cd):
                        idx_c_nuevo = i_cd
                        break

                # Siguiente N° de lista sugerido para el curso seleccionado
                df_curso_exist = df_alumnos_all[df_alumnos_all[col_c].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, cursos_disponibles[idx_c_nuevo]))] if (not df_alumnos_all.empty and col_c in df_alumnos_all.columns) else pd.DataFrame()
                max_ord_cur = 0
                if not df_curso_exist.empty and col_o in df_curso_exist.columns:
                    max_ord_cur = int(pd.to_numeric(df_curso_exist[col_o], errors='coerce').fillna(0).max())
                sug_ord_cur = max(1, max_ord_cur + 1)

                with st.container(border=True):
                    col_n1, col_n2, col_n3 = st.columns([1, 1.2, 1.8])
                    with col_n1:
                        new_orden = st.number_input("N° Lista:", min_value=1, max_value=200, value=sug_ord_cur, step=1, key="new_al_orden")
                    with col_n2:
                        new_matricula = st.number_input("N° Matrícula:", min_value=1, max_value=99999, value=next_mat_sug, step=1, key="new_al_matricula", help="Correlativo oficial de matrícula (sugerido automáticamente).")
                    with col_n3:
                        new_rut = st.text_input("RUT del Alumno (con guion y dígito verificador):", placeholder="ej: 21.345.678-9", key="new_al_rut").strip()

                    new_nombre = st.text_input("Nombre Completo del Estudiante (Apellidos y Nombres):", placeholder="ej: PÉREZ GONZÁLEZ JUAN IGNACIO", key="new_al_nombre").strip()

                    col_n4, col_n5 = st.columns(2)
                    with col_n4:
                        new_curso = st.selectbox("Curso de Matrícula:", cursos_disponibles, index=idx_c_nuevo, key="new_al_curso")
                    with col_n5:
                        new_estado = st.selectbox("Estado Inicial:", ["Activo", "Retirado"], index=0, key="new_al_estado")

                    col_n6, col_n7 = st.columns(2)
                    with col_n6:
                        new_fecha_mat = st.date_input("Fecha de Matrícula:", value=datetime.date.today(), format="DD/MM/YYYY", key="new_al_f_mat", help="Fecha oficial en que se formaliza la matrícula del alumno.")
                    with col_n7:
                        new_fecha_nac = st.date_input("Fecha de Nacimiento:", value=datetime.date(2015, 1, 1), min_value=datetime.date(1990, 1, 1), max_value=datetime.date.today(), format="DD/MM/YYYY", key="new_al_f_nac")

                    col_n8, col_n9 = st.columns(2)
                    with col_n8:
                        new_telefono = st.text_input("Teléfono del Apoderado:", placeholder="ej: +56912345678", key="new_al_tel").strip()
                    with col_n9:
                        new_fecha_alta = st.date_input("Fecha de Incorporación / Alta:", value=datetime.date.today(), format="DD/MM/YYYY", key="new_al_f_alta", help="Fecha en que ingresa a clases.")

                    st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)

                    if st.button("➕ Inscribir Alumno Oficialmente", type="primary", use_container_width=True, key="btn_save_new_alumno"):
                        if not new_rut:
                            st.error("⚠️ Debe ingresar el RUT del alumno.")
                        elif not new_nombre:
                            st.error("⚠️ Debe ingresar el nombre completo del alumno.")
                        else:
                            with st.spinner("Registrando nuevo alumno en la base de datos..."):
                                try:
                                    recs_fresh = sheet_alumnos.get_all_records()
                                    df_fresh = pd.DataFrame(recs_fresh) if recs_fresh else pd.DataFrame()
                                    df_fresh.columns = [str(c).strip() for c in df_fresh.columns]

                                    # Asegurar headers requeridos
                                    for th in target_headers:
                                        if th not in df_fresh.columns:
                                            df_fresh[th] = ""

                                    # Verificar si el RUT ya existe
                                    rut_clean = new_rut.replace('.', '').replace('-', '').strip().lower()
                                    existing_ruts = df_fresh['RUT'].astype(str).str.replace('.', '', regex=False).str.replace('-', '', regex=False).str.strip().str.lower().tolist()
                                    if rut_clean in existing_ruts:
                                        st.error(f"⚠️ Ya existe un estudiante registrado con el RUT {new_rut}.")
                                    else:
                                        nuevo_registro = {
                                            "N° Lista": int(new_orden),
                                            "N° Matrícula": str(int(new_matricula)),
                                            "RUT": new_rut.upper(),
                                            "Nombre": new_nombre.upper(),
                                            "Curso": new_curso,
                                            "Fecha Nacimiento": new_fecha_nac.strftime("%d-%m-%Y") if new_fecha_nac else "",
                                            "Fecha Matrícula": new_fecha_mat.strftime("%d-%m-%Y") if new_fecha_mat else "",
                                            "Fecha Alta": new_fecha_alta.strftime("%d-%m-%Y") if new_fecha_alta else "",
                                            "Fecha Baja": "",
                                            "Estado": new_estado,
                                            "Teléfono Apoderado": new_telefono
                                        }
                                        df_fresh = pd.concat([df_fresh, pd.DataFrame([nuevo_registro])], ignore_index=True)
                                        df_fresh['N° Lista'] = pd.to_numeric(df_fresh['N° Lista'], errors='coerce').fillna(999).astype(int)
                                        df_fresh = df_fresh.sort_values(by=['Curso', 'N° Lista'])

                                        cols_to_save = [c for c in target_headers if c in df_fresh.columns] + [c for c in df_fresh.columns if c not in target_headers and c != 'RUT_NORM']
                                        df_fresh = df_fresh[cols_to_save].fillna("")

                                        sheet_alumnos.clear()
                                        sheet_alumnos.update(values=[df_fresh.columns.tolist()] + df_fresh.values.tolist())
                                        st.session_state.df_alumnos_cache = None
                                        st.success(f"🎉 ¡Estudiante **{new_nombre.upper()}** (Matrícula N° {new_matricula}) inscrito exitosamente!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error al inscribir alumno: {e}")

            with tab_carga_al:
                st.markdown("### 📤 Carga Masiva y Sincronización desde Excel o CSV")
                st.write("Sube una nómina de alumnos completa o por curso en formato **Excel (.xlsx / .xls)** o **CSV**.")

                col_ej1, col_ej2 = st.columns([2, 1])
                with col_ej1:
                    df_ejemplo = pd.DataFrame({
                        "N° Lista": [1, 2],
                        "N° Matrícula": [101, 102],
                        "RUT": ["12345678-9", "98765432-1"],
                        "Nombre": ["Juan Pérez González", "María Silva Castro"],
                        "Curso": ["1° Básico", "1° Básico"],
                        "Fecha Nacimiento": ["15-03-2014", "22-07-2013"],
                        "Fecha Matrícula": ["01-03-2026", "01-03-2026"],
                        "Fecha Alta": ["01-03-2026", "01-03-2026"],
                        "Fecha Baja": ["", ""],
                        "Estado": ["Activo", "Activo"],
                        "Teléfono Apoderado": ["+56912345678", "+56987654321"]
                    })
                    st.dataframe(df_ejemplo, hide_index=True, use_container_width=True)
                with col_ej2:
                    csv_plantilla = df_ejemplo.to_csv(index=False, sep=';').encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descargar Plantilla (.csv)",
                        data=csv_plantilla,
                        file_name="plantilla_alumnos.csv",
                        mime="text/csv",
                        key="btn_download_plantilla_tab_sep"
                    )

                uploaded_file = st.file_uploader("Sube tu archivo de alumnos", type=['csv', 'xls', 'xlsx'], key="uploader_alumnos_tab_sep")
                if uploaded_file is not None:
                    try:
                        if uploaded_file.name.endswith('.csv'):
                            df_up = None
                            for enc in ['utf-8-sig', 'latin-1', 'cp1252', 'utf-8']:
                                for sep in [';', ',']:
                                    try:
                                        uploaded_file.seek(0)
                                        temp_df = pd.read_csv(uploaded_file, sep=sep, encoding=enc)
                                        if len(temp_df.columns) >= 2:
                                            df_up = temp_df
                                            break
                                    except Exception:
                                        continue
                                if df_up is not None:
                                    break
                            if df_up is None:
                                uploaded_file.seek(0)
                                df_up = pd.read_csv(uploaded_file)
                        else:
                            df_up = pd.read_excel(uploaded_file)

                        col_r_up = next((c for c in df_up.columns if 'rut' in c.lower()), None)
                        if col_r_up:
                            df_up[col_r_up] = df_up[col_r_up].astype(str).str.replace('.', '', regex=False).str.strip()

                        st.dataframe(df_up.head(5), hide_index=True, use_container_width=True)
                        st.info(f"Se detectaron **{len(df_up)}** filas en el archivo.")

                        cols_norm = [str(c).strip().upper().replace(' ','').replace('°','') for c in df_up.columns]
                        req_map = {"RUT": "RUT", "NOMBRE": "Nombre", "CURSO": "Curso"}
                        faltantes = [label for key, label in req_map.items() if not any(key in cn for cn in cols_norm)]

                        col_c_up = next((c for c in df_up.columns if 'curs' in c.lower()), None)
                        cursos_archivo_no_oficiales = []
                        cursos_map_lower = {}
                        if cursos_disponibles:
                            for c in cursos_disponibles:
                                cursos_map_lower[c.lower()] = c
                                partes_c = c.split()
                                if partes_c and partes_c[-1].upper() in ['A', 'B', 'C', 'D']:
                                    c_sin_letra = " ".join(partes_c[:-1]).strip()
                                    if c_sin_letra.lower() not in cursos_map_lower:
                                        cursos_map_lower[c_sin_letra.lower()] = c

                        if col_c_up and cursos_disponibles:
                            cursos_archivo = [str(x).strip() for x in df_up[col_c_up].unique() if str(x).strip() and str(x).strip().lower() != 'nan']
                            for ca in cursos_archivo:
                                if ca.lower() not in cursos_map_lower:
                                    cursos_archivo_no_oficiales.append(ca)

                        if faltantes:
                            st.error(f"⚠️ Faltan las siguientes columnas obligatorias: **{', '.join(faltantes)}**")
                        elif cursos_archivo_no_oficiales:
                            st.error(
                                f"❌ **Cursos no reconocidos en el archivo:** {', '.join(cursos_archivo_no_oficiales)}.\n\n"
                                f"Los cursos deben existir previamente en el catálogo oficial antes de matricular estudiantes. "
                                f"Por favor, créalos primero en el módulo **🏫 Cursos** o ajusta los nombres en tu archivo Excel para que coincidan con la lista oficial: "
                                f"**{', '.join(cursos_disponibles)}**."
                            )
                        else:
                            modo_carga = st.radio(
                                "Modo de procesamiento:",
                                [
                                    "🔄 Combinar y actualizar (Actualiza existentes por RUT y agrega nuevos)",
                                    "⚠️ Reemplazar la lista completa (Reemplaza toda la base de datos de alumnos)"
                                ],
                                key="radio_modo_carga_tab_sep"
                            )
                            if st.button("🚀 Procesar Carga Masiva Ahora", type="primary", key="btn_sincronizar_alumnos_tab_sep"):
                                with st.spinner("Guardando en Google Sheets..."):
                                    col_map = {}
                                    for c in df_up.columns:
                                        clow = str(c).strip().lower().replace(' ','').replace('°','')
                                        if clow == 'rut': col_map[c] = 'RUT'
                                        elif 'nomb' in clow: col_map[c] = 'Nombre'
                                        elif 'curs' in clow: col_map[c] = 'Curso'
                                        elif any(x in clow for x in ['nlista', 'nrolista', 'orden']): col_map[c] = 'N° Lista'
                                        elif 'nacim' in clow or ('nac' in clow and 'fecha' in clow): col_map[c] = 'Fecha Nacimiento'
                                        elif 'alta' in clow or 'ingres' in clow: col_map[c] = 'Fecha Alta'
                                        elif 'baja' in clow or 'retir' in clow: col_map[c] = 'Fecha Baja'
                                        elif 'matr' in clow and ('fec' in clow or 'date' in clow): col_map[c] = 'Fecha Matrícula'
                                        elif 'matr' in clow and 'fec' not in clow: col_map[c] = 'N° Matrícula'
                                        elif 'est' in clow: col_map[c] = 'Estado'
                                        elif 'tel' in clow or 'apod' in clow: col_map[c] = 'Teléfono Apoderado'

                                    df_nuevo = df_up.rename(columns=col_map).fillna("")
                                    if 'Curso' in df_nuevo.columns and cursos_map_lower:
                                        df_nuevo['Curso'] = df_nuevo['Curso'].apply(lambda x: cursos_map_lower.get(str(x).strip().lower(), str(x).strip()))
                                    if "REEMPLAZAR" in modo_carga.upper():
                                        df_final = df_nuevo
                                    else:
                                        existentes = sheet_alumnos.get_all_records()
                                        if existentes:
                                            df_existente = pd.DataFrame(existentes)
                                            if 'RUT' in df_existente.columns:
                                                df_existente['RUT'] = df_existente['RUT'].astype(str).str.replace('.', '', regex=False).str.strip()
                                            df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
                                            if 'RUT' in df_final.columns:
                                                df_final = df_final.drop_duplicates(subset=['RUT'], keep='last')
                                            if 'N° Lista' in df_final.columns:
                                                df_final['N° Lista'] = pd.to_numeric(df_final['N° Lista'], errors='coerce').fillna(0).astype(int)
                                                df_final = df_final.sort_values(by=['Curso', 'N° Lista'])
                                        else:
                                            df_final = df_nuevo

                                    df_final = df_final.fillna("")
                                    sheet_alumnos.clear()
                                    sheet_alumnos.update(values=[df_final.columns.values.tolist()] + df_final.values.tolist())
                                    st.session_state.df_alumnos_cache = None
                                    st.success(f"✅ Se cargaron **{len(df_final)}** alumnos correctamente.")
                                    st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar: {e}")

        except Exception as e:
            st.error(f"Error al cargar la administración de alumnos: {e}")


elif st.session_state.current_module == 'cursos':
    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>🏫 Gestión y Mantención de Cursos</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_cursos", use_container_width=True):
            st.session_state.pop('curso_sel_tag', None)
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 12px 0;'>", unsafe_allow_html=True)

    sheet_cursos = get_cursos_sheet()
    _, _, _, sheet_funcionarios, sheet_asignaciones = get_sheets()

    if not sheet_cursos:
        st.error("❌ No se pudo conectar con la base de datos de Cursos en Google Sheets.")
    else:
        try:
            recs_cursos = sheet_cursos.get_all_records()
            df_cursos_all = pd.DataFrame(recs_cursos) if recs_cursos else pd.DataFrame()

            if not df_cursos_all.empty:
                df_cursos_all.columns = [str(c).strip() for c in df_cursos_all.columns]
                col_c_nom = next((c for c in df_cursos_all.columns if 'nomb' in c.lower() or 'curs' in c.lower()), 'Nombre')
                col_c_let = next((c for c in df_cursos_all.columns if 'let' in c.lower()), 'Letra')
                col_c_pj = next((c for c in df_cursos_all.columns if 'jefe' in c.lower() or 'prof' in c.lower()), 'Profesor_Jefe')
                col_c_rut = next((c for c in df_cursos_all.columns if 'rut' in c.lower()), 'RUT_Profesor_Jefe')

                if col_c_let not in df_cursos_all.columns:
                    df_cursos_all[col_c_let] = "A"
            else:
                col_c_nom, col_c_let, col_c_pj, col_c_rut = 'Nombre', 'Letra', 'Profesor_Jefe', 'RUT_Profesor_Jefe'
                df_cursos_all = pd.DataFrame(columns=[col_c_nom, col_c_let, col_c_pj, col_c_rut])

            # Obtener profesores activos para el selector de Profesor Jefe
            profesores_jefes_dict = {"— Sin Asignar —": {"nombre": "— Sin Asignar —", "rut": ""}}
            if sheet_funcionarios:
                try:
                    recs_f = sheet_funcionarios.get_all_records()
                    df_f = pd.DataFrame(recs_f) if recs_f else pd.DataFrame()
                    if not df_f.empty and 'Rol' in df_f.columns:
                        df_f_profs = df_f[df_f['Rol'].astype(str).str.lower().str.contains('prof')].copy()
                        col_est_f = next((c for c in df_f.columns if 'est' in c.lower()), None)
                        if col_est_f:
                            df_f_profs = df_f_profs[df_f_profs[col_est_f].astype(str).str.lower() != 'inactivo']
                        for _, rf in df_f_profs.iterrows():
                            nom_p = str(rf.get('Nombre', '')).strip()
                            rut_p = str(rf.get('RUT', '')).strip()
                            if nom_p:
                                profesores_jefes_dict[nom_p] = {"nombre": nom_p, "rut": rut_p}
                except Exception:
                    pass

            opciones_profs = list(profesores_jefes_dict.keys())

            tab_actuales, tab_nuevo = st.tabs([
                "📋 Cursos Actuales",
                "➕ Crear Nuevo Curso"
            ])

            with tab_actuales:
                # Buscador en vivo
                col_busq_c, _ = st.columns([3, 4])
                with col_busq_c:
                    txt_buscar_cur = st.text_input("🔍 Buscar Curso:", placeholder="Ej: 1° Básico o Pérez", key="txt_buscar_cur_in").strip()

                df_filtrado_c = df_cursos_all.copy()
                if not df_filtrado_c.empty and txt_buscar_cur:
                    b_low = txt_buscar_cur.lower()
                    df_filtrado_c = df_filtrado_c[
                        df_filtrado_c[col_c_nom].astype(str).str.lower().str.contains(b_low, na=False) |
                        df_filtrado_c[col_c_pj].astype(str).str.lower().str.contains(b_low, na=False)
                    ]

                cant_cursos = len(df_filtrado_c)
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:6px 12px;margin:4px 0 12px 0;font-size:0.82rem;color:#334155;'>"
                    f"📋 <b>{cant_cursos}</b> cursos registrados &nbsp;|&nbsp; <i>Haz clic en una fila de la tabla para reasignar su Profesor(a) Jefe</i></div>",
                    unsafe_allow_html=True
                )

                # Proporción con más espacio para la tabla para que los nombres de los profesores se lean completos
                col_tabla_c, col_ficha_c = st.columns([1.6, 1.0])

                with col_tabla_c:
                    if df_filtrado_c.empty:
                        st.info("ℹ️ No hay cursos registrados que coincidan con la búsqueda.")
                    else:
                        df_vista_c = df_filtrado_c.copy()
                        df_vista_c['Curso_Completo'] = df_vista_c.apply(
                            lambda r: f"{str(r[col_c_nom]).strip()} {str(r.get(col_c_let, 'A')).strip()}".strip() if not str(r[col_c_nom]).strip().endswith(str(r.get(col_c_let, 'A')).strip()) else str(r[col_c_nom]).strip(),
                            axis=1
                        )
                        df_vista_c = df_vista_c[['Curso_Completo', col_c_let, col_c_pj]].rename(columns={
                            'Curso_Completo': "Curso",
                            col_c_let: "Letra",
                            col_c_pj: "Profesor(a) Jefe"
                        })
                        ev_c = st.dataframe(
                            df_vista_c,
                            use_container_width=True,
                            hide_index=True,
                            selection_mode="single-row",
                            on_select="rerun",
                            key="df_cursos_select_tabla",
                            column_config={
                                "Curso": st.column_config.TextColumn("Curso", width=125),
                                "Letra": st.column_config.TextColumn("Letra", width=65),
                                "Profesor(a) Jefe": st.column_config.TextColumn("Profesor(a) Jefe", width="large")
                            }
                        )
                        sel_rows = ev_c.selection.get("rows", [])
                        if sel_rows:
                            idx_sel = sel_rows[0]
                            st.session_state.curso_sel_tag = str(df_filtrado_c.iloc[idx_sel][col_c_nom]).strip()

                with col_ficha_c:
                    curso_actual_sel = st.session_state.get('curso_sel_tag')
                    if not curso_actual_sel and not df_filtrado_c.empty:
                        curso_actual_sel = str(df_filtrado_c.iloc[0][col_c_nom]).strip()
                        st.session_state.curso_sel_tag = curso_actual_sel

                    df_curso_ficha = df_cursos_all[df_cursos_all[col_c_nom].astype(str).str.strip().str.lower() == str(curso_actual_sel).strip().lower()] if curso_actual_sel else pd.DataFrame()

                    if df_curso_ficha.empty:
                        st.markdown(
                            "<div style='text-align:center;padding:30px 15px;background:#f8fafc;border:1px dashed #cbd5e1;border-radius:8px;color:#64748b;font-size:0.85rem;'>"
                            "👈 <b>Selecciona un curso de la tabla</b> para ver y editar su Profesor(a) Jefe."
                            "</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        datos_c = df_curso_ficha.iloc[0]
                        val_nom_orig = str(datos_c[col_c_nom]).strip()
                        val_let_orig = str(datos_c.get(col_c_let, "A")).strip()
                        val_pj_orig = str(datos_c[col_c_pj]).strip()

                        st.markdown(
                            f"<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:8px 12px;margin-bottom:12px;'>"
                            f"<h4 style='margin:0;color:#166534;font-size:1.0rem;'>✏️ Ficha del Curso: {val_nom_orig}</h4>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                        with st.container(border=True):
                            c_f1, c_f2 = st.columns([2.5, 1])
                            with c_f1:
                                st.text_input("Curso Oficial:", value=val_nom_orig, disabled=True, key=f"f_nom_{val_nom_orig}", help="El nombre no es editable para proteger la integridad de notas y alumnos.")
                            with c_f2:
                                st.text_input("Letra:", value=val_let_orig, disabled=True, key=f"f_let_{val_nom_orig}", help="Letra registrada para los informes y certificados oficiales.")

                            idx_pj_c = opciones_profs.index(val_pj_orig) if val_pj_orig in opciones_profs else 0
                            ed_prof_jefe = st.selectbox("Profesor(a) Jefe:", opciones_profs, index=idx_pj_c, key=f"ed_pj_{val_nom_orig}")

                            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
                            col_bsave, col_bdel = st.columns([1.8, 1.2])

                            with col_bsave:
                                if st.button("💾 Guardar Jefatura", type="primary", use_container_width=True, key=f"btn_save_cur_{val_nom_orig}"):
                                    with st.spinner("Guardando cambios en Google Sheets..."):
                                        try:
                                            rut_jefe = profesores_jefes_dict.get(ed_prof_jefe, {}).get("rut", "")
                                            vals_c = sheet_cursos.get_all_values()
                                            if vals_c:
                                                headers_c = vals_c[0]
                                                idx_nom = next((i for i, h in enumerate(headers_c) if 'nomb' in h.lower() or 'curs' in h.lower()), 0)
                                                idx_pj = next((i for i, h in enumerate(headers_c) if 'jefe' in h.lower() or 'prof' in h.lower()), 2)
                                                idx_rut = next((i for i, h in enumerate(headers_c) if 'rut' in h.lower()), 3)

                                                for i_f, fila in enumerate(vals_c[1:], start=2):
                                                    if len(fila) > idx_nom and str(fila[idx_nom]).strip().lower() == val_nom_orig.lower():
                                                        if len(headers_c) > idx_pj:
                                                            sheet_cursos.update_cell(i_f, idx_pj + 1, ed_prof_jefe)
                                                        if len(headers_c) > idx_rut:
                                                            sheet_cursos.update_cell(i_f, idx_rut + 1, rut_jefe)
                                                        break

                                                # La jefatura reside en la tabla Cursos, no en Asignaturas de clases
                                                get_cursos_sheet.clear()
                                                st.session_state.cursos_oficiales_cache = None
                                                st.session_state.dict_cursos_cache = None
                                                st.session_state.curso_sel_tag = val_nom_orig
                                                st.success("✅ ¡Profesor(a) Jefe actualizado exitosamente!")
                                                time.sleep(1)
                                                st.rerun()
                                        except Exception as e_up:
                                            st.error(f"Error al actualizar: {e_up}")

                            with col_bdel:
                                with st.popover("🗑️ Eliminar"):
                                    st.write(f"¿Eliminar **{val_nom_orig}**?")
                                    st.caption("Esta acción quitará el curso del catálogo.")
                                    if st.button("Confirmar Eliminación", type="primary", key=f"btn_del_{val_nom_orig}"):
                                        try:
                                            vals_c = sheet_cursos.get_all_values()
                                            idx_nom = next((i for i, h in enumerate(vals_c[0]) if 'nomb' in h.lower() or 'curs' in h.lower()), 0)
                                            filas_filtradas = [vals_c[0]] + [f for f in vals_c[1:] if len(f) > idx_nom and str(f[idx_nom]).strip().lower() != val_nom_orig.lower()]
                                            sheet_cursos.clear()
                                            sheet_cursos.update(values=filas_filtradas)

                                            # Quitar jefatura asociada en Asignaciones
                                            if sheet_asignaciones:
                                                try:
                                                    vals_asig = sheet_asignaciones.get_all_values()
                                                    if vals_asig:
                                                        filas_asig_sin_jef = [vals_asig[0]] + [
                                                            r for r in vals_asig[1:]
                                                            if not (len(r) > 3 and str(r[2]).strip().lower() == val_nom_orig.lower() and str(r[3]).strip().upper() == "JEFATURA")
                                                        ]
                                                        sheet_asignaciones.clear()
                                                        sheet_asignaciones.update(values=filas_asig_sin_jef)
                                                except Exception:
                                                    pass

                                            get_cursos_sheet.clear()
                                            st.session_state.cursos_oficiales_cache = None
                                            st.session_state.dict_cursos_cache = None
                                            st.session_state.pop('curso_sel_tag', None)
                                            st.success("✅ Curso eliminado.")
                                            time.sleep(1)
                                            st.rerun()
                                        except Exception as e_del:
                                            st.error(f"Error al eliminar: {e_del}")

            with tab_nuevo:
                st.markdown(
                    "<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 18px;margin-bottom:16px;'>"
                    "<h3 style='margin:0 0 4px 0;color:#166534;font-size:1.1rem;'>➕ Crear Nuevo Curso</h3>"
                    "<span style='color:#15803d;font-size:0.85rem;'>Selecciona el nivel oficial, la letra y el profesor jefe correspondiente.</span>"
                    "</div>",
                    unsafe_allow_html=True
                )

                NIVELES_BASE = ["NT1", "NT2", "1° Básico", "2° Básico", "3° Básico", "4° Básico", "5° Básico", "6° Básico", "7° Básico", "8° Básico"]
                LETRAS_BASE = ["A", "B", "C", "D"]

                with st.container(border=True):
                    c_n1, c_n2 = st.columns([2.5, 1])
                    with c_n1:
                        in_nivel_sel = st.selectbox("Curso / Nivel Oficial:", NIVELES_BASE, index=2, key="in_cur_nivel_sel")
                    with c_n2:
                        in_letra_sel = st.selectbox("Letra Oficial:", LETRAS_BASE, index=0, key="in_cur_letra_sel", help="Letra requerida para informes de notas y certificados del Decreto 67.")

                    in_pj_nuevo = st.selectbox("Profesor(a) Jefe:", opciones_profs, index=0, key="in_cur_nuevo_pj")

                    nombre_curso_oficial = f"{in_nivel_sel} {in_letra_sel}".strip()

                    st.markdown(
                        f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin:10px 0;font-size:0.80rem;color:#475569;'>"
                        f"💡 El curso se registrará como <b>{nombre_curso_oficial}</b> con letra oficial <b>{in_letra_sel}</b> para todos los módulos, actas y certificados."
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)
                    if st.button("🚀 Crear Curso", type="primary", use_container_width=True, key="btn_crear_curso_sub"):
                        existentes = [str(x).strip().lower() for x in df_cursos_all[col_c_nom].tolist()] if not df_cursos_all.empty else []
                        if nombre_curso_oficial.lower() in existentes:
                            st.warning(f"⚠️ El curso '{nombre_curso_oficial}' ya existe en el catálogo.")
                        else:
                            with st.spinner("Creando nuevo curso en Google Sheets..."):
                                try:
                                    rut_jefe = profesores_jefes_dict.get(in_pj_nuevo, {}).get("rut", "")
                                    # Fila: Nombre, Letra, Profesor_Jefe, RUT_Profesor_Jefe
                                    sheet_cursos.append_row([nombre_curso_oficial, in_letra_sel, in_pj_nuevo, rut_jefe])

                                    get_cursos_sheet.clear()
                                    st.session_state.cursos_oficiales_cache = None
                                    st.session_state.dict_cursos_cache = None
                                    st.session_state.curso_sel_tag = nombre_curso_oficial
                                    st.success(f"✅ ¡Curso '{nombre_curso_oficial}' creado exitosamente!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e_c_new:
                                    st.error(f"Error al crear curso: {e_c_new}")

        except Exception as e_main_cur:
            st.error(f"Error al cargar la administración de cursos: {e_main_cur}")


elif st.session_state.current_module == 'notas':
    renderizar_insignia_universal()

    # Si venimos de otro módulo, limpiar toda la grilla y forzar rerun limpio.
    # IMPORTANTE: borrar keys en el mismo run donde se renderizan los widgets NO funciona
    # en Streamlit (los widgets ya leyeron su estado al inicio del run). Por eso hacemos
    # st.rerun() para que el PRÓXIMO run renderice los widgets con estado limpio.
    _prev = st.session_state.get('_previous_module')
    if _prev != 'notas':
        for _k in [
            'notas_curso_sel', 'notas_asig_sel', 'notas_sem_seg',
            'notas_grilla_cargada', 'notas_curso_activo', 'notas_asig_activa', 'notas_sem_activo'
        ]:
            st.session_state.pop(_k, None)
        for _k in [k for k in list(st.session_state.keys()) if k.startswith('nota_')]:
            st.session_state.pop(_k, None)
        st.session_state['_previous_module'] = 'notas'
        st.rerun()  # Rerun limpio: en el siguiente run _prev=='notas', widgets arrancan vacíos

    col_titulo, col_escape = st.columns([3.5, 1])
    with col_titulo:
        st.title("📝 Carga de Notas")
    with col_escape:
        st.write("")
        if st.button("🏠 Volver", key="btn_escape_sup_notas", use_container_width=True):
            navigate('home')
            st.rerun()
    st.write("---")

    sheet_alumnos, _, sheet_notas, sheet_funcionarios, sheet_asignaciones = get_sheets()

    def procesar_nota_chilena(raw_val, es_conceptual=False):
        """
        Valida y normaliza notas escolares chilenas:
        - Si es_conceptual=True o se ingresa concepto (I, S, B, MB):
          Retorna (None, concepto_mayuscula, True) -> No tiene valor numérico, no promedia.
        - Para asignaturas cuantitativas: valida rango (1,0 a 7,0), división por 10 si se ingresa dos dígitos (ej. 52 -> 5,2).
        - Retorna (num_float, formatted_str, es_valido)
        """
        if raw_val is None:
            return None, "", True
        txt = str(raw_val).strip()
        if not txt or txt in ["—", "-", "None", "nan", "null"]:
            return None, "", True

        if es_conceptual:
            # En asignaturas conceptuales (Religión y Orientación) se admiten y traducen I, S, B, MB
            conc = nota_a_concepto(txt)
            if conc in ["I", "S", "B", "MB"]:
                return None, conc, True
            return None, txt, False

        # Verificar si en una asignatura cuantitativa se ingresó un concepto
        txt_upper = txt.upper()
        if txt_upper in ["I", "S", "B", "MB"]:
            return None, txt_upper, True

        norm = txt.replace(',', '.')
        try:
            num = float(norm)
        except ValueError:
            return None, txt, False

        # Si se ingresó sin coma entre 10.0 y 70.0 (ej: 52 -> 5.2, 65 -> 6.5, 70 -> 7.0)
        if 10.0 <= num <= 70.0:
            num = num / 10.0

        num = redondear_nota(num, 1)

        # Rango estricto de notas en Chile: 1.0 a 7.0
        if 1.0 <= num <= 7.0:
            str_formateada = f"{num:.1f}".replace('.', ',')
            return num, str_formateada, True
        else:
            return None, txt, False

    # ── CSS para la grilla de notas ──────────────────────────────────────────
    st.markdown("""
    <style>
    .notas-header {
        display: flex; align-items: center; background: #f0f7f2;
        border-radius: 8px 8px 0 0; padding: 8px 6px;
        font-weight: 700; font-size: 0.78rem; color: #1a5c32;
        border-bottom: 2px solid #008F39; gap: 4px;
    }
    .notas-row {
        display: flex; align-items: center; padding: 5px 6px;
        border-bottom: 1px solid #f0f0f0; gap: 4px;
        font-size: 0.82rem;
    }
    .notas-row:hover { background: #fafffe; }
    .notas-row.retirado { background: #fff5f5; color: #cc0000; }
    .col-num  { width: 36px;  min-width: 36px;  text-align: center; font-weight: 700; }
    .col-name { flex: 1;      min-width: 180px; }
    .col-nota { width: 54px;  min-width: 54px;  text-align: center; }
    .col-prom { width: 60px;  min-width: 60px;  text-align: center;
                font-weight: 700; color: #008F39; }
    .badge-retirado {
        font-size: 0.68rem; background: #ffdddd; color: #cc0000;
        border-radius: 4px; padding: 1px 5px; margin-left: 6px;
    }
    /* Estilos compactos para inputs de notas: texto centrado, sin flechas y tamaño completo */
    div[data-testid="stTextInput"] {
        margin-bottom: 0px !important;
    }
    div[data-testid="stTextInput"] > div {
        min-height: 32px !important;
    }
    div[data-testid="stTextInput"] input {
        padding: 2px 2px !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        text-align: center !important;
        height: 32px !important;
        min-height: 32px !important;
        border-radius: 6px !important;
        letter-spacing: 0.5px !important;
        color: #1a1a1a !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #008F39 !important;
        box-shadow: 0 0 0 1px #008F39 !important;
    }
    /* Resaltar notas menores a 4.0 en rojo */
    div[data-testid="stTextInput"] input.nota-roja,
    div[data-testid="stTextInput"]:has(input.nota-roja) input {
        color: #dc2626 !important;
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Confirmar guardado previo si existe (persiste a través del rerun) ─────
    if '_notas_guardadas_msg' in st.session_state:
        nuevas, actualizadas = st.session_state.pop('_notas_guardadas_msg')
        st.toast(f"✅ ¡Notas guardadas! {nuevas} nuevas · {actualizadas} actualizadas", icon="✅")
        st.balloons()

    # ── Determinar asignaciones permitidas según rol ────────────────────────
    rol_usuario = st.session_state.user.get('rol', '') if st.session_state.user else ''
    rut_usuario = st.session_state.user.get('rut', '') if st.session_state.user else ''
    es_admin = rol_usuario in ['Administrador Total', 'Director', 'Jefe UTP']

    cursos_permitidos = []
    asigs_permitidas  = []

    CURSOS_DEFAULT = [
        "NT1", "NT2",
        "1° básico", "2° básico", "3° básico", "4° básico",
        "5° básico", "6° básico", "7° básico", "8° básico"
    ]

    if es_admin:
        # Admin: usa caché de sesión para no saturar la cuota de la API
        if st.session_state.get('_admin_cursos_cache'):
            cursos_permitidos = st.session_state['_admin_cursos_cache']
        else:
            try:
                sheet_c_nt = get_cursos_sheet()
                if sheet_c_nt:
                    rc_nt = sheet_c_nt.get_all_records()
                    if rc_nt:
                        df_c_nt = pd.DataFrame(rc_nt)
                        if 'Estado' in df_c_nt.columns:
                            df_c_nt = df_c_nt[df_c_nt['Estado'].astype(str).str.lower() == 'activo']
                        if not df_c_nt.empty and 'Nombre' in df_c_nt.columns:
                            if 'Orden' in df_c_nt.columns:
                                df_c_nt['_o_nt'] = pd.to_numeric(df_c_nt['Orden'], errors='coerce').fillna(99)
                                df_c_nt = df_c_nt.sort_values(by='_o_nt')
                            c_nt = [str(x).strip() for x in df_c_nt['Nombre'].tolist() if str(x).strip()]
                            if c_nt:
                                cursos_permitidos = c_nt
                                st.session_state['_admin_cursos_cache'] = cursos_permitidos
            except Exception:
                pass

            if not cursos_permitidos and sheet_alumnos:
                try:
                    # Intentar leer registros
                    ra = sheet_alumnos.get_all_records()
                    df_a_adm = pd.DataFrame(ra) if ra else pd.DataFrame()
                    if not df_a_adm.empty:
                        df_a_adm.columns = [str(c).strip() for c in df_a_adm.columns]
                        col_c_adm = next((c for c in df_a_adm.columns if 'curs' in c.lower()), None)
                        if col_c_adm:
                            cursos_permitidos = sorted([str(v).strip() for v in df_a_adm[col_c_adm].unique() if str(v).strip()], key=orden_curso_sistema)
                            if cursos_permitidos:
                                st.session_state['_admin_cursos_cache'] = cursos_permitidos
                except Exception:
                    pass
        
        # Si la API tuvo un hipo momentáneo de cuota o conexión, usar los cursos institucionales para nunca bloquear
        if not cursos_permitidos:
            cursos_permitidos = CURSOS_DEFAULT
            st.session_state['_admin_cursos_cache'] = CURSOS_DEFAULT
    else:
        # Profesor: solo ve los cursos y asignaturas que tiene asignados
        if sheet_asignaciones:
            try:
                recs_asig = sheet_asignaciones.get_all_records()
                df_asig   = pd.DataFrame(recs_asig) if recs_asig else pd.DataFrame()
                if not df_asig.empty:
                    col_rut = next((c for c in df_asig.columns if 'rut' in c.lower()), None)
                    col_c   = next((c for c in df_asig.columns if 'curs' in c.lower()), None)
                    col_a   = next((c for c in df_asig.columns if 'asig' in c.lower()), None)
                    if col_rut and col_c and col_a:
                        df_mias = df_asig[
                            (df_asig[col_rut].astype(str).str.strip() == str(rut_usuario).strip()) &
                            (df_asig[col_a].astype(str).str.strip().str.upper() != 'JEFATURA')
                        ]
                        cursos_permitidos = sorted(df_mias[col_c].unique().tolist(), key=orden_curso_sistema)
                        asigs_permitidas  = sorted([a for a in df_mias[col_a].unique().tolist() if str(a).strip().upper() != 'JEFATURA'])
            except Exception as e:
                st.warning(f"No se pudieron cargar las asignaciones: {e}")

    ASIGNATURAS_DEFAULT = [
        "Matemáticas", "Lenguaje y Comunicación", "Ciencias Naturales",
        "Historia, Geografía y Ciencias Sociales", "Inglés",
        "Educación Física y Salud", "Artes Visuales", "Música",
        "Tecnología", "Orientación", "Religión Católica", "Religión Evangélica"
    ]
    if not asigs_permitidas:
        asigs_permitidas = ASIGNATURAS_DEFAULT

    # Eliminar estrictamente JEFATURA de cualquier lista de asignaturas para notas
    asigs_permitidas = [a for a in asigs_permitidas if str(a).strip().upper() != 'JEFATURA']

    if not cursos_permitidos:
        st.warning("⚠️ No tienes cursos asignados. Contacta al Administrador para configurar tus asignaciones docentes.")
        if st.button("⬅️ Volver al Dashboard", key="btn_volver_notas_sinasig"):
            navigate('home')
            st.rerun()
        st.stop()

    # ── Selectores de filtro ─────────────────────────────────────────────────
    col_s1, col_s2, col_s3, col_s4 = st.columns([1.8, 2.2, 1.6, 1.2])
    with col_s1:
        curso_sel = st.selectbox("📚 Curso:", cursos_permitidos, key="notas_curso_sel")
    with col_s2:
        # Si el usuario es profesor, filtrar asignaturas por curso seleccionado (excluyendo JEFATURA)
        if not es_admin and sheet_asignaciones:
            try:
                df_asig_tmp = pd.DataFrame(sheet_asignaciones.get_all_records())
                if not df_asig_tmp.empty:
                    col_rut_t = next((c for c in df_asig_tmp.columns if 'rut' in c.lower()), None)
                    col_c_t   = next((c for c in df_asig_tmp.columns if 'curs' in c.lower()), None)
                    col_a_t   = next((c for c in df_asig_tmp.columns if 'asig' in c.lower()), None)
                    if all([col_rut_t, col_c_t, col_a_t]):
                        df_filt = df_asig_tmp[
                            (df_asig_tmp[col_rut_t].astype(str).str.strip() == str(rut_usuario).strip()) &
                            (df_asig_tmp[col_c_t].astype(str) == str(curso_sel)) &
                            (df_asig_tmp[col_a_t].astype(str).str.strip().str.upper() != 'JEFATURA')
                        ]
                        asigs_del_curso = sorted([a for a in df_filt[col_a_t].unique().tolist() if str(a).strip().upper() != 'JEFATURA'])
                        if asigs_del_curso:
                            asigs_permitidas = asigs_del_curso
            except Exception:
                pass
        asigs_permitidas = [a for a in asigs_permitidas if str(a).strip().upper() != 'JEFATURA']
        asignatura_sel = st.selectbox("📖 Asignatura:", asigs_permitidas, key="notas_asig_sel")
    with col_s3:
        st.markdown("<p style='font-size:14px;margin-bottom:6px;font-weight:400'>🗓️ Semestre:</p>", unsafe_allow_html=True)
        semestre_sel = st.segmented_control(
            "Semestre",
            options=["1° Semestre", "2° Semestre"],
            default="1° Semestre",
            key="notas_sem_seg",
            label_visibility="collapsed"
        )
        if not semestre_sel:
            semestre_sel = "1° Semestre"
    with col_s4:
        st.write("")
        st.write("")
        cargar = st.button("🔍 Cargar Grilla", type="primary", key="btn_cargar_notas", use_container_width=True)

    sem_num = "1" if "1" in semestre_sel else "2"

    if cargar:
        st.session_state['notas_grilla_cargada'] = True
        st.session_state['notas_curso_activo']   = curso_sel
        st.session_state['notas_asig_activa']    = asignatura_sel
        st.session_state['notas_sem_activo']     = sem_num
        # Limpiar inputs anteriores
        for k in [k for k in st.session_state if k.startswith("nota_n")]:
            del st.session_state[k]

    # ── Grilla de notas ──────────────────────────────────────────────────────
    if st.session_state.get('notas_grilla_cargada') and sheet_alumnos and sheet_notas:
        curso_activo = st.session_state.get('notas_curso_activo', curso_sel)
        asig_activa  = st.session_state.get('notas_asig_activa',  asignatura_sel)
        sem_activo   = st.session_state.get('notas_sem_activo',   sem_num)

        st.markdown(f"### 📋 {curso_activo} · {asig_activa} · {semestre_sel}")
        st.write("---")

        try:
            # ── Cargar alumnos del curso ──────────────────────────────────
            recs_al = sheet_alumnos.get_all_records()
            df_al   = pd.DataFrame(recs_al) if recs_al else pd.DataFrame()

            if df_al.empty:
                st.warning("No hay alumnos registrados en la base de datos.")
                st.stop()

            df_al.columns = [str(c).strip() for c in df_al.columns]
            col_nombre_al = next((c for c in df_al.columns if 'nomb' in c.lower()), None)
            col_curso_al  = next((c for c in df_al.columns if 'curs' in c.lower()), None)
            col_rut_al    = next((c for c in df_al.columns if 'rut'  in c.lower()), None)
            col_orden_al  = next((c for c in df_al.columns if 'orden' in c.lower() or 'lista' in c.lower() or 'n°' in c.lower() or 'nro' in c.lower()), None)
            col_baja_al   = next((c for c in df_al.columns if 'baja' in c.lower() or 'retir' in c.lower()), None)

            if not col_curso_al or not col_nombre_al or not col_rut_al:
                st.error("La hoja Alumnos no tiene las columnas esperadas (Nombre, Curso, RUT).")
                st.stop()

            df_curso = df_al[df_al[col_curso_al].astype(str).str.strip() == str(curso_activo)].copy()

            if df_curso.empty:
                st.info(f"No hay alumnos registrados para el curso **{curso_activo}**.")
                st.stop()

            # Determinar N° de orden
            if col_orden_al:
                df_curso['_orden'] = pd.to_numeric(df_curso[col_orden_al], errors='coerce').fillna(0).astype(int)
            else:
                df_curso = df_curso.sort_values(by=col_nombre_al)
                df_curso['_orden'] = range(1, len(df_curso) + 1)

            df_curso = df_curso.sort_values(by='_orden')

            # Determinar retirados
            def es_retirado(row):
                if col_baja_al and str(row.get(col_baja_al, '')).strip() not in ['', 'nan', 'None']:
                    return True
                return False

            df_activos  = df_curso[~df_curso.apply(es_retirado, axis=1)]
            df_retirados = df_curso[df_curso.apply(es_retirado, axis=1)]
            # Retirados van al final
            df_ordenado = pd.concat([df_activos, df_retirados], ignore_index=True)

            # ── Cargar notas existentes ───────────────────────────────────
            recs_notas = sheet_notas.get_all_records()
            df_notas   = pd.DataFrame(recs_notas) if recs_notas else pd.DataFrame()

            notas_existentes = {}  # {rut: {N1: val, N2: val, ...}}
            if not df_notas.empty:
                df_notas.columns = [str(c).strip() for c in df_notas.columns]
                col_rut_n  = next((c for c in df_notas.columns if 'rut'  in c.lower()), None)
                col_asig_n = next((c for c in df_notas.columns if 'asig' in c.lower()), None)
                col_sem_n  = next((c for c in df_notas.columns if 'sem'  in c.lower()), None)
                col_cur_n  = next((c for c in df_notas.columns if 'curs' in c.lower()), None)

                if all([col_rut_n, col_asig_n, col_sem_n, col_cur_n]):
                    import unicodedata
                    def _norm_cmp(s):
                        return "".join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn').lower().strip()

                    def _norm_sem(s):
                        txt = str(s).strip()
                        return "1" if "1" in txt else ("2" if "2" in txt else txt)

                    cur_act_norm = _norm_cmp(curso_activo)
                    asig_act_norm = _norm_cmp(asig_activa)
                    sem_act_norm = _norm_sem(sem_activo)

                    df_filtradas = df_notas[
                        df_notas[col_cur_n].apply(lambda x: _norm_cmp(x) == cur_act_norm) &
                        df_notas[col_asig_n].apply(lambda x: _norm_cmp(x) == asig_act_norm) &
                        df_notas[col_sem_n].apply(lambda x: _norm_sem(x) == sem_act_norm)
                    ]
                    for _, row_n in df_filtradas.iterrows():
                        rut_key = str(row_n[col_rut_n]).strip()
                        notas_existentes[rut_key] = {
                            f"N{i}": str(row_n.get(f"N{i}", "")).strip()
                            for i in range(1, 11)
                        }

            es_asig_conceptual = any(k in asig_activa.lower() for k in ['religi', 'orientac'])

            # Pre-cargar y sanitizar session_state con notas existentes
            for _, row_al in df_ordenado.iterrows():
                rut_k = str(row_al[col_rut_al]).strip()
                retirado = es_retirado(row_al)
                if retirado:
                    continue
                for i in range(1, 11):
                    sk = f"nota_n{i}_{rut_k}"
                    if sk not in st.session_state:
                        val_exist = notas_existentes.get(rut_k, {}).get(f"N{i}", "")
                        _, str_val, _ = procesar_nota_chilena(val_exist, es_conceptual=es_asig_conceptual)
                        st.session_state[sk] = str_val
                    else:
                        # Si ya existía un valor en session_state (por ejemplo un float viejo como 52.0 o texto sin coma como '52')
                        curr_v = st.session_state[sk]
                        if curr_v is not None and str(curr_v).strip() != "":
                            _, str_val, ok = procesar_nota_chilena(curr_v, es_conceptual=es_asig_conceptual)
                            if ok:
                                st.session_state[sk] = str_val

            if es_asig_conceptual:
                st.info("ℹ️ **Asignatura Conceptual:** Ingresa los conceptos **I** (Insuficiente), **S** (Suficiente), **B** (Bueno) o **MB** (Muy Bueno). Estas calificaciones **no se promedian numéricamente ni afectan el promedio general**.")
            else:
                st.caption("💡 **Criterio de ingreso:** Notas de **1,0 a 7,0** con separación por coma (ej. `5,2`). Si escribes dos dígitos sin coma (ej. `52`), se convertirá automáticamente a `5,2`.")

            # ── Renderizar encabezado ─────────────────────────────────────
            COLS_N = [f"N{i}" for i in range(1, 11)]
            header_cols = st.columns([0.5, 2.8] + [0.6]*10 + [0.75])
            header_cols[0].markdown("**N°**")
            header_cols[1].markdown("**Alumno**")
            for idx, cn in enumerate(COLS_N):
                header_cols[idx + 2].markdown(f"<div style='text-align:center;font-weight:700'>{cn}</div>", unsafe_allow_html=True)
            col_prom_title = "Conc." if es_asig_conceptual else "Prom."
            header_cols[-1].markdown(f"<div style='text-align:center;font-weight:700'>{col_prom_title}</div>", unsafe_allow_html=True)

            st.markdown("<hr style='margin:4px 0 8px 0;border-color:#008F39'>", unsafe_allow_html=True)

            # ── Renderizar filas ──────────────────────────────────────────
            hay_algun_error_global = False
            for _, row_al in df_ordenado.iterrows():
                rut_k    = str(row_al[col_rut_al]).strip()
                nombre_k = str(row_al[col_nombre_al]).strip()
                orden_k  = int(row_al['_orden'])
                retirado = es_retirado(row_al)

                fila_cols = st.columns([0.5, 2.8] + [0.6]*10 + [0.75])

                # N° de orden
                if retirado:
                    fila_cols[0].markdown(f"<span style='color:#cc0000'>~~{orden_k}~~</span>", unsafe_allow_html=True)
                    fila_cols[1].markdown(
                        f"<span style='color:#cc0000;text-decoration:line-through'>{nombre_k}</span>"
                        f"<span style='font-size:0.68rem;background:#ffdddd;color:#cc0000;border-radius:4px;padding:1px 5px;margin-left:6px'>Retirado</span>",
                        unsafe_allow_html=True
                    )
                    for i in range(10):
                        fila_cols[i + 2].markdown("<span style='color:#ccc'>—</span>", unsafe_allow_html=True)
                    fila_cols[-1].markdown("<span style='color:#ccc'>—</span>", unsafe_allow_html=True)
                else:
                    fila_cols[0].markdown(f"**{orden_k}**")
                    fila_cols[1].markdown(nombre_k)

                    notas_vals = []
                    conceptos_fila = []
                    tiene_error_fila = False
                    for i, col_nota in enumerate(COLS_N):
                        sk = f"nota_n{i+1}_{rut_k}"
                        val_input = fila_cols[i + 2].text_input(
                            label=col_nota,
                            value=st.session_state.get(sk, ""),
                            key=sk,
                            placeholder="—",
                            max_chars=4,
                            label_visibility="collapsed"
                        )
                        if val_input and str(val_input).strip():
                            num_val, str_fmt, es_valida = procesar_nota_chilena(val_input, es_conceptual=es_asig_conceptual)
                            if es_valida:
                                if num_val is not None:
                                    notas_vals.append(num_val)
                                elif str_fmt:
                                    conceptos_fila.append(str_fmt)
                            else:
                                tiene_error_fila = True
                                hay_algun_error_global = True

                    # Promedio automático o concepto final
                    if tiene_error_fila:
                        err_hint = "Solo conceptos I, S, B, MB permitidos" if es_asig_conceptual else "Nota fuera de rango (1,0 a 7,0)"
                        fila_cols[-1].markdown(
                            f"<div style='text-align:center;font-weight:700;color:#cc0000;font-size:0.8rem' title='{err_hint}'>⚠️ Error</div>",
                            unsafe_allow_html=True
                        )
                    elif es_asig_conceptual:
                        ultimo_conc = conceptos_fila[-1] if conceptos_fila else "—"
                        fila_cols[-1].markdown(
                            f"<div style='text-align:center;font-weight:700;color:#166534;font-size:0.9rem'>{ultimo_conc}</div>",
                            unsafe_allow_html=True
                        )
                    elif notas_vals:
                        prom_raw = sum(notas_vals) / len(notas_vals)
                        prom = redondear_nota(prom_raw, 1)
                        from decimal import Decimal as _D
                        prom_str = str(_D(f"{prom:.6f}").quantize(_D('0.1'), rounding='ROUND_HALF_UP')).replace('.', ',')
                        color_prom = "#008F39" if prom >= 4.0 else "#cc0000"
                        fila_cols[-1].markdown(
                            f"<div style='text-align:center;font-weight:700;color:{color_prom};font-size:0.9rem'>{prom_str}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        fila_cols[-1].markdown("<div style='text-align:center;color:#aaa'>—</div>", unsafe_allow_html=True)

            if hay_algun_error_global:
                if es_asig_conceptual:
                    st.warning("⚠️ Se detectaron valores no válidos. En esta asignatura solo se admiten conceptos: **I**, **S**, **B** o **MB**.")
                else:
                    st.warning("⚠️ Se detectaron notas fuera del rango permitido (1,0 a 7,0) o con formato no reconocido. Corrígelas para poder guardar.")

            # Inyección de script JS en tiempo real para pintar de rojo las notas < 4,0 e 'I'
            import streamlit.components.v1 as _components
            _components.html("""
            <script>
            (function() {
                function pintar() {
                    try {
                        const doc = window.parent.document;
                        if (!doc) return;
                        const inputs = doc.querySelectorAll('div[data-testid="stTextInput"] input');
                        inputs.forEach(inp => {
                            const val = (inp.value || '').trim().replace(',', '.');
                            if (!val) {
                                inp.classList.remove('nota-roja');
                                return;
                            }
                            const n = parseFloat(val);
                            if ((!isNaN(n) && n < 4.0 && n >= 1.0) || val.toUpperCase() === 'I') {
                                inp.classList.add('nota-roja');
                            } else {
                                inp.classList.remove('nota-roja');
                            }
                        });
                    } catch(e) {}
                }

                // Ejecutar inmediatamente y continuar indefinidamente
                pintar();
                setInterval(pintar, 500);

                try {
                    window.parent.document.addEventListener('input', pintar);
                } catch(e) {}
            })();
            </script>
            """, height=0, width=0)

            st.write("")
            st.markdown("<hr style='margin:4px 0 12px 0'>", unsafe_allow_html=True)

            # ── Botón Guardar ─────────────────────────────────────────────
            col_g1, col_g2, col_g3 = st.columns([2, 1.5, 2])
            with col_g2:
                guardar_notas = st.button(
                    f"💾 Guardar {semestre_sel}",
                    type="primary",
                    key="btn_guardar_notas",
                    use_container_width=True
                )

            if guardar_notas:
                # Validar previamente que no existan notas fuera de rango
                notas_invalidas = []
                for _, row_al in df_activos.iterrows():
                    rut_k = str(row_al[col_rut_al]).strip()
                    nom_k = str(row_al[col_nombre_al]).strip()
                    for i in range(1, 11):
                        sk = f"nota_n{i}_{rut_k}"
                        v = st.session_state.get(sk)
                        if v is not None and str(v).strip() != "":
                            num_val, _, ok = procesar_nota_chilena(v, es_conceptual=es_asig_conceptual)
                            if not ok:
                                notas_invalidas.append(f"{nom_k} (N{i}: '{v}')")

                if notas_invalidas:
                    msg_err = "conceptos no válidos (solo I, S, B, MB)" if es_asig_conceptual else "notas fuera de rango (1,0 a 7,0)"
                    st.error(f"❌ No se puede guardar: Hay {msg_err}: {', '.join(notas_invalidas[:4])}")
                else:
                    _save_ok    = False
                    _save_error = None
                    filas_nuevas       = 0
                    filas_actualizadas = 0

                    try:
                        with st.spinner("Guardando notas en Google Sheets..."):
                            recs_notas_fresh = sheet_notas.get_all_records()
                            df_nf = pd.DataFrame(recs_notas_fresh) if recs_notas_fresh else pd.DataFrame()

                            def _norm_k(s):
                                return "".join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn').lower().strip()

                            def _norm_sem(s):
                                txt = str(s).strip()
                                return "1" if "1" in txt else ("2" if "2" in txt else txt)

                            fila_map = {}
                            if not df_nf.empty:
                                df_nf.columns = [str(c).strip() for c in df_nf.columns]
                                col_rn = next((c for c in df_nf.columns if 'rut'  in c.lower()), None)
                                col_an = next((c for c in df_nf.columns if 'asig' in c.lower()), None)
                                col_sn = next((c for c in df_nf.columns if 'sem'  in c.lower()), None)
                                col_cn = next((c for c in df_nf.columns if 'curs' in c.lower()), None)
                                if all([col_rn, col_an, col_sn, col_cn]):
                                    for row_idx, row_nf in df_nf.iterrows():
                                        key_nf = (
                                            _norm_k(row_nf[col_rn]),
                                            _norm_k(row_nf[col_cn]),
                                            _norm_k(row_nf[col_an]),
                                            _norm_sem(row_nf[col_sn])
                                        )
                                        fila_map[key_nf] = row_idx + 2

                            filas_nuevas_batch = []
                            for _, row_al in df_activos.iterrows():
                                rut_k = str(row_al[col_rut_al]).strip()
                                nom_k = str(row_al[col_nombre_al]).strip()

                                notas_fila = []
                                vals_notas = []
                                conceptos_f = []
                                for i in range(1, 11):
                                    sk  = f"nota_n{i}_{rut_k}"
                                    val = st.session_state.get(sk)
                                    if val is not None and str(val).strip() != "":
                                        num_val, str_f, ok = procesar_nota_chilena(val, es_conceptual=es_asig_conceptual)
                                        if ok:
                                            notas_fila.append(str_f)
                                            if num_val is not None:
                                                vals_notas.append(num_val)
                                            elif str_f:
                                                conceptos_f.append(str_f)
                                        else:
                                            notas_fila.append("")
                                    else:
                                        notas_fila.append("")

                                if es_asig_conceptual:
                                    prom_calc = conceptos_f[-1] if conceptos_f else ""
                                elif vals_notas:
                                    prom_num = redondear_nota(sum(vals_notas) / len(vals_notas), 1)
                                    prom_calc = f"{prom_num:.1f}".replace('.', ',')
                                else:
                                    prom_calc = ""

                                fila_data = [
                                    rut_k, nom_k, str(curso_activo), str(asig_activa), str(sem_activo),
                                    *notas_fila,
                                    prom_calc
                                ]

                                clave_fila = (
                                    _norm_k(rut_k),
                                    _norm_k(curso_activo),
                                    _norm_k(asig_activa),
                                    _norm_sem(sem_activo)
                                )

                                if clave_fila in fila_map:
                                    row_sheet = fila_map[clave_fila]
                                    sheet_notas.update(values=[fila_data], range_name=f"A{row_sheet}:P{row_sheet}")
                                    filas_actualizadas += 1
                                else:
                                    filas_nuevas_batch.append(fila_data)
                                    filas_nuevas += 1

                            if filas_nuevas_batch:
                                sheet_notas.append_rows(filas_nuevas_batch)

                        _save_ok = True

                    except Exception as e:
                        _save_error = str(e)

                    # st.rerun() FUERA del try/except
                    if _save_ok:
                        st.session_state['_notas_guardadas_msg'] = (filas_nuevas, filas_actualizadas)
                        # Limpiar keys de notas para que el siguiente render los lea frescos desde la DB
                        for k in [k for k in st.session_state if k.startswith("nota_")]:
                            del st.session_state[k]
                        st.rerun()
                    else:
                        st.error(f"❌ Error al guardar las notas: {_save_error}")
        except Exception as e:
            st.error(f"Error al cargar la grilla de notas: {e}")
    else:
        st.info("👆 Selecciona curso, asignatura y semestre, luego presiona **Cargar Grilla** para comenzar.")

    st.write("")
    if st.button("⬅️ Volver al Dashboard Principal", key="btn_volver_notas"):
        for k in [k for k in st.session_state if k.startswith("nota_")]:
            del st.session_state[k]
        navigate('home')
        st.rerun()

elif st.session_state.current_module == 'funcionarios':
    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>👔 Gestión y Edición de Funcionarios</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_func", use_container_width=True):
            st.session_state.pop('func_edit_tag', None)
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 12px 0;'>", unsafe_allow_html=True)

    _, _, _, sheet_funcionarios, _ = get_sheets()

    if not sheet_funcionarios:
        st.error("❌ Error de conexión con la base de datos de Google Sheets.")
    else:
        try:
            recs_func = sheet_funcionarios.get_all_records()
            df_func_all = pd.DataFrame(recs_func) if recs_func else pd.DataFrame()

            if not df_func_all.empty:
                df_func_all.columns = [str(c).strip() for c in df_func_all.columns]
                # Estandarizar columnas clave
                col_r = next((c for c in df_func_all.columns if 'rut' in c.lower()), 'RUT')
                col_n = next((c for c in df_func_all.columns if 'nomb' in c.lower()), 'Nombre')
                col_rol = next((c for c in df_func_all.columns if 'rol' in c.lower() or 'carg' in c.lower()), 'Rol')
                col_pin = next((c for c in df_func_all.columns if 'pin' in c.lower() or 'clav' in c.lower()), 'PIN')
                col_est = next((c for c in df_func_all.columns if 'est' in c.lower()), 'Estado')
            else:
                col_r, col_n, col_rol, col_pin, col_est = 'RUT', 'Nombre', 'Rol', 'PIN', 'Estado'

            # Resumen métrico superior
            cant_total_f = len(df_func_all)
            cant_activos_f = len(df_func_all[df_func_all[col_est].astype(str).str.lower() != 'inactivo']) if not df_func_all.empty and col_est in df_func_all.columns else cant_total_f
            cant_prof_f = len(df_func_all[df_func_all[col_rol].astype(str).str.lower().str.contains('prof')]) if not df_func_all.empty and col_rol in df_func_all.columns else 0

            st.markdown(
                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 14px;margin-bottom:14px;font-size:0.83rem;color:#334155;'>"
                f"👥 <b>Total Registrados:</b> {cant_total_f} &nbsp;|&nbsp; "
                f"<span style='color:#166534;font-weight:600;'>{cant_activos_f} Activos</span> &nbsp;|&nbsp; "
                f"<span style='color:#1e40af;font-weight:600;'>{cant_prof_f} Docentes</span></div>",
                unsafe_allow_html=True
            )

            tab_gestion_f, tab_carga_f = st.tabs([
                "📋 Nómina de Funcionarios y Claves",
                "📤 Carga Masiva (Excel / CSV)"
            ])

            with tab_gestion_f:
                # Barra de filtros superior (búsqueda y rol para escalar a 50+ funcionarios)
                col_busq_f, col_rol_filtro = st.columns([3, 2])
                with col_busq_f:
                    txt_buscar_f = st.text_input("🔍 Buscar por Nombre o RUT:", placeholder="Ej: Mendoza o 12345678", key="txt_buscar_func_in").strip()
                with col_rol_filtro:
                    filtro_rol_sel = st.selectbox(
                        "Filtrar por Rol:",
                        ["Todos los Roles", "Solo Profesores", "Solo Inspectores", "Solo Secretarias", "Equipo Directivo"],
                        key="sel_filtro_rol_func"
                    )

                # Filtrar datos de funcionarios
                df_filtrado_f = df_func_all.copy()
                if not df_filtrado_f.empty:
                    if filtro_rol_sel == "Solo Profesores":
                        df_filtrado_f = df_filtrado_f[df_filtrado_f[col_rol].astype(str).str.lower().str.contains('prof')]
                    elif filtro_rol_sel == "Solo Inspectores":
                        df_filtrado_f = df_filtrado_f[df_filtrado_f[col_rol].astype(str).str.lower().str.contains('inspect')]
                    elif filtro_rol_sel == "Solo Secretarias":
                        df_filtrado_f = df_filtrado_f[df_filtrado_f[col_rol].astype(str).str.lower().str.contains('secretar')]
                    elif filtro_rol_sel == "Equipo Directivo":
                        df_filtrado_f = df_filtrado_f[df_filtrado_f[col_rol].astype(str).str.lower().str.contains('direct|utp|admin')]

                    if txt_buscar_f:
                        b_low_f = txt_buscar_f.lower().replace('.', '')
                        mask_f = df_filtrado_f.apply(
                            lambda r: b_low_f in str(r.get(col_n, '')).lower() or b_low_f in str(r.get(col_r, '')).lower().replace('.', ''),
                            axis=1
                        )
                        df_filtrado_f = df_filtrado_f[mask_f]

                # Resumen métrico
                st.markdown(
                    f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:6px 12px;margin:4px 0 12px 0;font-size:0.82rem;color:#334155;'>"
                    f"👥 Mostrando <b>{len(df_filtrado_f)}</b> de <b>{cant_total_f}</b> funcionarios &nbsp;|&nbsp; "
                    f"<i>Haz clic en una fila de la tabla para ver y editar su ficha / clave</i></div>",
                    unsafe_allow_html=True
                )

                modo_func = st.session_state.get('modo_func_actual', 'VER_EDITAR')

                # Barra de acción superior clara
                col_b_f1, col_b_f2, col_sp_f = st.columns([2.2, 2.2, 2.6])
                with col_b_f1:
                    t_btn_lf = "primary" if modo_func == 'VER_EDITAR' else "secondary"
                    if st.button("📋 Nómina y Edición de Personal", type=t_btn_lf, use_container_width=True, key="btn_modo_ver_f"):
                        st.session_state.modo_func_actual = 'VER_EDITAR'
                        st.rerun()
                with col_b_f2:
                    t_btn_nf = "primary" if modo_func == 'CREAR_NUEVO' else "secondary"
                    if st.button("➕ Inscribir Nuevo Funcionario", type=t_btn_nf, use_container_width=True, key="btn_modo_crear_f"):
                        st.session_state.modo_func_actual = 'CREAR_NUEVO'
                        st.session_state.func_sel_rut = None
                        st.rerun()

                st.markdown("<hr style='margin:10px 0 16px 0;border-color:#e2e8f0;'>", unsafe_allow_html=True)

                if modo_func == 'CREAR_NUEVO':
                    # ==================== VISTA: INSCRIBIR NUEVO FUNCIONARIO ====================
                    st.markdown(
                        "<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 18px;margin-bottom:16px;'>"
                        "<h3 style='margin:0 0 4px 0;color:#166534;font-size:1.1rem;'>➕ Formulario de Nuevo Funcionario</h3>"
                        "<span style='color:#15803d;font-size:0.85rem;'>Ingresa los datos para otorgar acceso al sistema institucional.</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )

                    with st.container(border=True):
                        c_fn1, c_fn2 = st.columns([1.5, 2.5])
                        with c_fn1:
                            in_n_rut_f = st.text_input("RUT (Sin puntos, con guión):", placeholder="Ej: 12345678-9", key="in_new_rut_func").strip()
                        with c_fn2:
                            in_n_nom_f = st.text_input("Nombre Completo:", placeholder="Ej: Carlos Silva Castro", key="in_new_nom_func").strip()

                        c_fn3, c_fn4, c_fn5 = st.columns([1.5, 1.2, 1.3])
                        with c_fn3:
                            in_n_rol_f = st.selectbox("Rol Institucional:", ROLES_TODOS, key="in_new_rol_func")
                        with c_fn4:
                            in_n_pin_f = st.text_input("Clave PIN (4 dígitos):", value="1234", max_chars=4, key="in_new_pin_func").strip()
                        with c_fn5:
                            in_n_est_f = st.selectbox("Estado de Acceso:", ["Activo", "Inactivo"], index=0, key="in_new_est_func")

                        st.markdown("<hr style='margin:12px 0;'>", unsafe_allow_html=True)
                        col_save_fn, col_cancel_fn = st.columns([2, 1])
                        with col_save_fn:
                            if st.button("🚀 Guardar e Inscribir Funcionario", type="primary", use_container_width=True, key="btn_save_new_func"):
                                if not in_n_rut_f or not in_n_nom_f:
                                    st.error("⚠️ El RUT y el Nombre Completo son obligatorios.")
                                elif len(in_n_pin_f) != 4 or not in_n_pin_f.isdigit():
                                    st.error("⚠️ La clave PIN debe tener 4 dígitos numéricos.")
                                else:
                                    with st.spinner("Guardando en Google Sheets..."):
                                        try:
                                            rut_clean_fn = in_n_rut_f.replace('.', '').strip()
                                            recs_ff = sheet_funcionarios.get_all_records()
                                            df_ff = pd.DataFrame(recs_ff) if recs_ff else pd.DataFrame(columns=['RUT', 'Nombre', 'Rol', 'PIN', 'Estado'])
                                            df_ff.columns = [str(c).strip() for c in df_ff.columns]

                                            df_ff['RUT_NORM'] = df_ff['RUT'].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()
                                            if not df_ff[df_ff['RUT_NORM'] == rut_clean_fn.lower()].empty:
                                                st.error(f"⚠️ Ya existe un funcionario registrado con el RUT {rut_clean_fn}.")
                                            else:
                                                nueva_fila_fn = {
                                                    "RUT": rut_clean_fn,
                                                    "Nombre": in_n_nom_f,
                                                    "Rol": in_n_rol_f,
                                                    "PIN": in_n_pin_f,
                                                    "Estado": in_n_est_f
                                                }
                                                df_ff = pd.concat([df_ff, pd.DataFrame([nueva_fila_fn])], ignore_index=True)
                                                cols_s_fn = ['RUT', 'Nombre', 'Rol', 'PIN', 'Estado']
                                                for c in df_ff.columns:
                                                    if c not in cols_s_fn and c != 'RUT_NORM':
                                                        cols_s_fn.append(c)

                                                df_ff = df_ff[cols_s_fn].fillna("")
                                                sheet_funcionarios.clear()
                                                sheet_funcionarios.update(values=[df_ff.columns.tolist()] + df_ff.values.tolist())
                                                st.success(f"✅ ¡Funcionario **{in_n_nom_f}** registrado exitosamente!")
                                                st.session_state.func_sel_rut = rut_clean_fn
                                                st.session_state.modo_func_actual = 'VER_EDITAR'
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Error al guardar: {e}")
                        with col_cancel_fn:
                            if st.button("Cancelar", use_container_width=True, key="btn_cancel_new_func"):
                                st.session_state.modo_func_actual = 'VER_EDITAR'
                                st.rerun()

                else:
                    # ==================== VISTA: LISTADO Y EDICIÓN DIRECTA ====================
                    col_tabla_f, col_ficha_f = st.columns([3.2, 2.8], gap="large")

                    with col_tabla_f:
                        st.markdown(
                            "<div style='font-weight:700;font-size:0.88rem;color:#1e293b;margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;'>"
                            "<span>📋 Nómina de Personal</span>"
                            "<span style='font-size:0.75rem;font-weight:400;color:#64748b;'>Selecciona una fila para cargar su ficha 👉</span>"
                            "</div>",
                            unsafe_allow_html=True
                        )

                        if not df_filtrado_f.empty:
                            df_vista_f = pd.DataFrame()
                            df_vista_f['RUT'] = df_filtrado_f[col_r].astype(str).str.replace('.', '', regex=False).str.strip()
                            df_vista_f['Nombre'] = df_filtrado_f[col_n].astype(str)
                            df_vista_f['Rol'] = df_filtrado_f[col_rol].astype(str)
                            df_vista_f['Estado'] = df_filtrado_f[col_est].astype(str)

                            event_f = st.dataframe(
                                df_vista_f,
                                use_container_width=True,
                                hide_index=True,
                                height=380,
                                selection_mode="single-row",
                                on_select="rerun",
                                key="tabla_interactiva_funcionarios"
                            )

                            if event_f and event_f.selection and event_f.selection.rows:
                                idx_sel_f = event_f.selection.rows[0]
                                rut_click_f = str(df_vista_f.iloc[idx_sel_f]['RUT']).strip()
                                if st.session_state.get('func_sel_rut') != rut_click_f:
                                    st.session_state.func_sel_rut = rut_click_f
                                    # Limpiar widgets viejos
                                    for wk in ['ed_nom_func', 'ed_rol_func', 'ed_pin_func', 'ed_est_func']:
                                        st.session_state.pop(wk, None)
                                    st.rerun()
                        else:
                            st.info("💡 No se encontraron funcionarios con los filtros actuales.")

                    with col_ficha_f:
                        rut_actual_f = st.session_state.get('func_sel_rut')

                        if not rut_actual_f:
                            st.markdown(
                                "<div style='border:2px dashed #cbd5e1;border-radius:8px;padding:36px 20px;text-align:center;background:#f8fafc;color:#64748b;margin-top:10px;'>"
                                "<div style='font-size:2rem;margin-bottom:8px;'>👈</div>"
                                "<div style='font-weight:600;font-size:0.95rem;color:#334155;'>Ningún Funcionario Seleccionado</div>"
                                "<div style='font-size:0.8rem;margin-top:4px;'>Haz clic en cualquier fila de la lista a la izquierda para cargar y editar aquí los datos y clave del funcionario.</div>"
                                "</div>",
                                unsafe_allow_html=True
                            )
                        else:
                            func_row = df_func_all[df_func_all[col_r].astype(str).str.replace('.','', regex=False).str.strip().str.lower() == rut_actual_f.replace('.','').strip().lower()]
                            if func_row.empty:
                                st.warning("No se encontraron los datos del funcionario seleccionado.")
                            else:
                                r_dat_f = func_row.iloc[0]
                                val_rut_f = str(r_dat_f.get(col_r, '')).strip()
                                val_nom_f = str(r_dat_f.get(col_n, '')).strip()
                                val_rol_f = str(r_dat_f.get(col_rol, 'Profesor')).strip()
                                val_pin_f = str(r_dat_f.get(col_pin, '1234')).strip()
                                val_est_f = str(r_dat_f.get(col_est, 'Activo')).strip()

                                st.markdown(
                                    f"<div style='background:#f1f5f9;border-left:4px solid #166534;border-radius:4px;padding:8px 12px;margin-bottom:10px;'>"
                                    f"<div style='font-weight:700;font-size:0.95rem;color:#0f172a;'>✏️ {val_nom_f}</div>"
                                    f"<div style='font-size:0.78rem;color:#475569;'>RUT: <b>{val_rut_f}</b> &nbsp;|&nbsp; Rol: <b>{val_rol_f}</b></div>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                                with st.container(border=True):
                                    c1_f, c2_f = st.columns([1.5, 2.5])
                                    with c1_f:
                                        # RUT BLOQUEADO EN EDICIÓN
                                        st.text_input("RUT (Protegido / No editable):", value=val_rut_f, disabled=True, key="ed_rut_bloqueado_func")
                                    with c2_f:
                                        in_nom_f = st.text_input("Nombre Completo:", value=val_nom_f, key="ed_nom_func").strip()

                                    c3_f, c4_f, c5_f = st.columns([1.5, 1.2, 1.3])
                                    roles_validos = ROLES_TODOS
                                    idx_rol = roles_validos.index(val_rol_f) if val_rol_f in roles_validos else 0
                                    with c3_f:
                                        in_rol_f = st.selectbox("Rol:", roles_validos, index=idx_rol, key="ed_rol_func")
                                    with c4_f:
                                        in_pin_f = st.text_input("Clave PIN:", value=val_pin_f if val_pin_f else "1234", max_chars=4, key="ed_pin_func").strip()
                                    with c5_f:
                                        idx_est_f = 0 if val_est_f.lower() != 'inactivo' else 1
                                        in_est_f = st.selectbox("Estado:", ["Activo", "Inactivo"], index=idx_est_f, key="ed_est_func")

                                    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

                                    if st.button("💾 Guardar Cambios del Funcionario", type="primary", use_container_width=True, key="btn_save_ed_func"):
                                        if not in_nom_f:
                                            st.error("⚠️ El Nombre Completo es obligatorio.")
                                        elif len(in_pin_f) != 4 or not in_pin_f.isdigit():
                                            st.error("⚠️ La clave PIN debe tener exactamente 4 dígitos numéricos.")
                                        else:
                                            with st.spinner("Guardando en Google Sheets..."):
                                                try:
                                                    rut_buscar_f = val_rut_f.replace('.', '').strip()
                                                    recs_fresh_f = sheet_funcionarios.get_all_records()
                                                    df_fresh_f = pd.DataFrame(recs_fresh_f) if recs_fresh_f else pd.DataFrame()
                                                    df_fresh_f.columns = [str(c).strip() for c in df_fresh_f.columns]

                                                    df_fresh_f['RUT_NORM'] = df_fresh_f['RUT'].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()
                                                    m_idx_f = df_fresh_f[df_fresh_f['RUT_NORM'] == rut_buscar_f.lower()]

                                                    if not m_idx_f.empty:
                                                        idx_target_f = m_idx_f.index[0]
                                                        df_fresh_f.at[idx_target_f, 'Nombre'] = in_nom_f
                                                        df_fresh_f.at[idx_target_f, 'Rol'] = in_rol_f
                                                        df_fresh_f.at[idx_target_f, 'PIN'] = in_pin_f
                                                        df_fresh_f.at[idx_target_f, 'Estado'] = in_est_f

                                                        cols_save_f = ['RUT', 'Nombre', 'Rol', 'PIN', 'Estado']
                                                        for c in df_fresh_f.columns:
                                                            if c not in cols_save_f and c != 'RUT_NORM':
                                                                cols_save_f.append(c)

                                                        df_fresh_f = df_fresh_f[cols_save_f].fillna("")
                                                        sheet_funcionarios.clear()
                                                        sheet_funcionarios.update(values=[df_fresh_f.columns.tolist()] + df_fresh_f.values.tolist())
                                                        st.success(f"✅ ¡Funcionario **{in_nom_f}** actualizado con éxito!")
                                                        st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error al actualizar: {e}")

                                    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
                                    with st.expander("🗑️ Zona de Peligro: Eliminar este Funcionario"):
                                        if val_rut_f.lower() == 'admin':
                                            st.info("🔒 La cuenta 'admin' principal del sistema no puede ser eliminada.")
                                        else:
                                            st.warning(f"¿Estás seguro de eliminar a **{val_nom_f}** ({val_rut_f})?")
                                            if st.button("Confirmar Eliminación Permanente", type="primary", key="btn_del_func_ficha_act"):
                                                with st.spinner("Eliminando..."):
                                                    try:
                                                        recs_fresh_f = sheet_funcionarios.get_all_records()
                                                        df_fresh_f = pd.DataFrame(recs_fresh_f)
                                                        df_fresh_f.columns = [str(c).strip() for c in df_fresh_f.columns]
                                                        col_r_del_f = next((c for c in df_fresh_f.columns if 'rut' in c.lower()), 'RUT')
                                                        rut_clean_del_f = val_rut_f.replace('.', '').strip().lower()
                                                        df_fresh_f = df_fresh_f[df_fresh_f[col_r_del_f].astype(str).str.replace('.', '', regex=False).str.strip().str.lower() != rut_clean_del_f]

                                                        sheet_funcionarios.clear()
                                                        sheet_funcionarios.update(values=[df_fresh_f.columns.tolist()] + df_fresh_f.values.tolist())
                                                        st.success("Funcionario eliminado.")
                                                        st.session_state.func_sel_rut = None
                                                        st.rerun()
                                                    except Exception as e:
                                                        st.error(f"Error al eliminar: {e}")

            with tab_carga_f:
                st.markdown("### 📤 Carga Masiva y Sincronización de Funcionarios")
                st.write("Sube una nómina de personal en formato **Excel (.xlsx / .xls)** o **CSV**.")

                col_ej_f1, col_ej_f2 = st.columns([2, 1])
                with col_ej_f1:
                    df_ej_func = pd.DataFrame({
                        "RUT": ["12345678-9", "98765432-1"],
                        "Nombre": ["Carlos Mendoza Silva", "Ana Morales Castro"],
                        "Rol": ["Profesor", "Inspector"],
                        "PIN": ["1234", "5678"],
                        "Estado": ["Activo", "Activo"]
                    })
                    st.dataframe(df_ej_func, hide_index=True, use_container_width=True)
                with col_ej_f2:
                    csv_plantilla_f = df_ej_func.to_csv(index=False, sep=';').encode('utf-8-sig')
                    st.download_button(
                        label="📥 Descargar Plantilla (.csv)",
                        data=csv_plantilla_f,
                        file_name="plantilla_funcionarios.csv",
                        mime="text/csv",
                        key="btn_download_plantilla_func_sep"
                    )

                uploaded_file_func = st.file_uploader("Sube tu archivo de funcionarios (CSV o Excel)", type=['csv', 'xls', 'xlsx'], key="uploader_func_tab_sep")
                if uploaded_file_func is not None:
                    try:
                        if uploaded_file_func.name.endswith('.csv'):
                            df_up_f = None
                            for enc in ['utf-8-sig', 'latin-1', 'cp1252', 'utf-8']:
                                for sep in [';', ',']:
                                    try:
                                        uploaded_file_func.seek(0)
                                        temp_df = pd.read_csv(uploaded_file_func, sep=sep, encoding=enc)
                                        if len(temp_df.columns) >= 2:
                                            df_up_f = temp_df
                                            break
                                    except Exception:
                                        continue
                                if df_up_f is not None:
                                    break
                            if df_up_f is None:
                                uploaded_file_func.seek(0)
                                df_up_f = pd.read_csv(uploaded_file_func)
                        else:
                            df_up_f = pd.read_excel(uploaded_file_func)

                        col_map_f = {}
                        for c in df_up_f.columns:
                            clow = str(c).strip().lower()
                            if 'rut' in clow: col_map_f[c] = 'RUT'
                            elif 'nomb' in clow: col_map_f[c] = 'Nombre'
                            elif 'rol' in clow or 'carg' in clow: col_map_f[c] = 'Rol'
                            elif 'pin' in clow or 'clav' in clow or 'pass' in clow: col_map_f[c] = 'PIN'
                            elif 'est' in clow: col_map_f[c] = 'Estado'

                        df_up_f = df_up_f.rename(columns=col_map_f).fillna("")
                        if 'RUT' in df_up_f.columns:
                            df_up_f['RUT'] = df_up_f['RUT'].astype(str).str.replace('.', '', regex=False).str.strip()
                        if 'PIN' not in df_up_f.columns or df_up_f['PIN'].astype(str).str.strip().eq("").all():
                            df_up_f['PIN'] = "1234"
                        else:
                            df_up_f['PIN'] = df_up_f['PIN'].astype(str).str.replace('.0', '', regex=False).str.strip()
                            df_up_f['PIN'] = df_up_f['PIN'].apply(lambda val: str(val) if str(val).strip() != "" else "1234")
                        if 'Estado' not in df_up_f.columns or df_up_f['Estado'].astype(str).str.strip().eq("").all():
                            df_up_f['Estado'] = "Activo"
                        if 'Rol' not in df_up_f.columns:
                            df_up_f['Rol'] = "Profesor"

                        st.dataframe(df_up_f.head(5), hide_index=True, use_container_width=True)
                        st.info(f"Se detectaron **{len(df_up_f)}** filas en el archivo.")

                        cols_check = [str(c).strip().upper() for c in df_up_f.columns]
                        if "RUT" not in cols_check or "NOMBRE" not in cols_check:
                            st.error("⚠️ El archivo debe contener al menos las columnas 'RUT' y 'Nombre'.")
                        else:
                            modo_carga_f = st.radio(
                                "Modo de procesamiento:",
                                [
                                    "🔄 Combinar y actualizar (Conserva funcionarios existentes y agrega/actualiza por RUT)",
                                    "⚠️ Reemplazar lista completa (Borra los funcionarios actuales excepto el admin por defecto)"
                                ],
                                key="radio_modo_carga_func_sep"
                            )

                            if st.button("🚀 Procesar Carga de Funcionarios Ahora", type="primary", key="btn_sincronizar_func_sep"):
                                with st.spinner("Sincronizando funcionarios con Google Sheets..."):
                                    df_nuevo_f = df_up_f[['RUT', 'Nombre', 'Rol', 'PIN', 'Estado']].copy()
                                    if "REEMPLAZAR" in modo_carga_f.upper():
                                        if not any(df_nuevo_f['RUT'].astype(str).str.lower() == 'admin'):
                                            admin_row = pd.DataFrame([{
                                                "RUT": "admin",
                                                "Nombre": "Administrador General",
                                                "Rol": "Administrador Total",
                                                "PIN": "1234",
                                                "Estado": "Activo"
                                            }])
                                            df_final_f = pd.concat([admin_row, df_nuevo_f], ignore_index=True)
                                        else:
                                            df_final_f = df_nuevo_f
                                    else:
                                        recs_ex = sheet_funcionarios.get_all_records()
                                        if recs_ex:
                                            df_ex_f = pd.DataFrame(recs_ex)
                                            if 'RUT' in df_ex_f.columns:
                                                df_ex_f['RUT'] = df_ex_f['RUT'].astype(str).str.replace('.', '', regex=False).str.strip()
                                            df_final_f = pd.concat([df_ex_f, df_nuevo_f], ignore_index=True)
                                            if 'RUT' in df_final_f.columns:
                                                df_final_f = df_final_f.drop_duplicates(subset=['RUT'], keep='last')
                                        else:
                                            df_final_f = df_nuevo_f

                                    df_final_f = df_final_f.fillna("")
                                    sheet_funcionarios.clear()
                                    sheet_funcionarios.update(values=[df_final_f.columns.values.tolist()] + df_final_f.values.tolist())
                                    st.success("✅ ¡Nómina de funcionarios actualizada exitosamente!")
                                    st.rerun()
                    except Exception as e:
                        st.error(f"Error al procesar archivo de funcionarios: {e}")

        except Exception as e:
            st.error(f"Error al cargar módulo de funcionarios: {e}")

elif st.session_state.current_module == 'asignaciones':
    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>📚 Asignación Docente por Curso</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_asig", use_container_width=True):
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 12px 0;'>", unsafe_allow_html=True)

    if st.session_state.get('asig_guardada_ok', False):
        msg_ok = st.session_state.get('asig_guardada_msg', "✅ ¡Asignaciones actualizadas exitosamente!")
        st.success(msg_ok)
        st.session_state['asig_guardada_ok'] = False

    sheet_alumnos, _, _, sheet_funcionarios, sheet_asignaciones = get_sheets()

    # 1. Obtener lista de Cursos disponibles
    cursos_list = ["1° Básico", "2° Básico", "3° Básico", "4° Básico", "5° Básico", "6° Básico", "7° Básico", "8° Básico", "1° Medio", "2° Medio", "3° Medio", "4° Medio"]
    try:
        sheet_c_asig = get_cursos_sheet()
        if sheet_c_asig:
            rc_asig = sheet_c_asig.get_all_records()
            if rc_asig:
                df_c_asig = pd.DataFrame(rc_asig)
                if 'Estado' in df_c_asig.columns:
                    df_c_asig = df_c_asig[df_c_asig['Estado'].astype(str).str.lower() == 'activo']
                if not df_c_asig.empty and 'Nombre' in df_c_asig.columns:
                    if 'Orden' in df_c_asig.columns:
                        df_c_asig['_ord_t'] = pd.to_numeric(df_c_asig['Orden'], errors='coerce').fillna(99)
                        df_c_asig = df_c_asig.sort_values(by='_ord_t')
                    c_oficiales = [str(x).strip() for x in df_c_asig['Nombre'].tolist() if str(x).strip()]
                    if c_oficiales:
                        cursos_list = c_oficiales
    except Exception:
        pass

    if sheet_alumnos and (not cursos_list or len(cursos_list) <= 12 and cursos_list[0] == "1° Básico"):
        try:
            ra = sheet_alumnos.get_all_records()
            df_a = pd.DataFrame(ra)
            col_c = next((c for c in df_a.columns if 'curs' in c.lower()), None)
            if col_c and not df_a.empty:
                c_db = sorted([str(val) for val in df_a[col_c].unique() if str(val).strip() != ""], key=orden_curso_sistema)
                if c_db:
                    cursos_list = c_db
        except Exception:
            pass

    # 2. Obtener lista de Profesores (exclusivamente con Rol = 'Profesor')
    profesores_dict = {}  # "Nombre": {"rut": ..., "nombre": ...}
    profesores_opciones = ["— Sin Asignar —"]

    if sheet_funcionarios:
        try:
            rf = sheet_funcionarios.get_all_records()
            df_f = pd.DataFrame(rf)
            if not df_f.empty and 'Rol' in df_f.columns:
                # Filtrar estrictamente solo funcionarios con rol de Profesor
                profs = df_f[df_f['Rol'].astype(str).str.strip().str.lower() == 'profesor'].copy()
                if not profs.empty:
                    profs = profs.sort_values(by=['Nombre'])
                    for _, row in profs.iterrows():
                        rut_p = str(row['RUT']).strip()
                        nom_p = str(row['Nombre']).strip()
                        if nom_p:
                            profesores_dict[nom_p] = {"rut": rut_p, "nombre": nom_p}
                            if nom_p not in profesores_opciones:
                                profesores_opciones.append(nom_p)
        except Exception:
            pass

    # 3. Asignaturas oficiales
    asignaturas_list = [
        "Matemáticas",
        "Lenguaje y Comunicación",
        "Ciencias Naturales",
        "Historia, Geografía y Ciencias Sociales",
        "Inglés",
        "Educación Física y Salud",
        "Artes Visuales",
        "Música",
        "Tecnología",
        "Orientación",
        "Religión Católica",
        "Religión Evangélica"
    ]

    # 4. Selector de Curso Compacto
    col_sel_curso, col_info_curso = st.columns([2.5, 4.5])
    with col_sel_curso:
        curso_seleccionado = st.selectbox("Selecciona el Curso a Configurar:", cursos_list, key="sel_curso_asig_matriz")
    with col_info_curso:
        st.markdown(
            f"<div style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:6px 12px;margin-top:16px;color:#166534;font-size:0.80rem;'>"
            f"💡 Asigna el <b>Profesor 1</b> y/o <b>Profesor 2</b> para cada asignatura de <b>{curso_seleccionado}</b>. "
            f"<i>(El Profesor(a) Jefe de este curso se gestiona desde el módulo <b>🏫 Cursos</b>)</i>.</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # 5. Cargar asignaciones vigentes para este curso desde Sheets
    asignaciones_existentes = {} # asig -> [ {"rut":..., "nombre":...}, ... ]
    df_todas_asig = pd.DataFrame()

    if sheet_asignaciones:
        try:
            recs_raw = sheet_asignaciones.get_all_records()
            if recs_raw:
                df_todas_asig = pd.DataFrame(recs_raw)
                df_todas_asig.columns = [str(c).strip() for c in df_todas_asig.columns]
                col_c_as = next((c for c in df_todas_asig.columns if 'curs' in c.lower()), 'Curso')
                col_a_as = next((c for c in df_todas_asig.columns if 'asig' in c.lower()), 'Asignatura')
                col_r_as = next((c for c in df_todas_asig.columns if 'rut' in c.lower()), 'RUT_Profesor')
                col_n_as = next((c for c in df_todas_asig.columns if 'nomb' in c.lower()), 'Nombre_Profesor')

                df_curso_actual = df_todas_asig[df_todas_asig[col_c_as].astype(str).str.strip() == str(curso_seleccionado).strip()]
                for _, r_asig in df_curso_actual.iterrows():
                    asig_nombre = str(r_asig[col_a_as]).strip()
                    rut_val = str(r_asig[col_r_as]).strip()
                    nom_val = str(r_asig[col_n_as]).strip()
                    if asig_nombre not in asignaciones_existentes:
                        asignaciones_existentes[asig_nombre] = []
                    asignaciones_existentes[asig_nombre].append({"rut": rut_val, "nombre": nom_val})
        except Exception as e:
            st.error(f"Error al leer asignaciones: {e}")

    # 6. Formulario de Matriz: Asignatura | Profesor 1 | Profesor 2
    with st.form("form_matriz_asignaciones"):

        # Encabezado de la tabla de asignaturas
        ch_asig, ch_p1, ch_p2 = st.columns([2.2, 2.5, 2.5])
        with ch_asig:
            st.markdown("<div style='font-weight:700;font-size:0.84rem;color:#1a5c32;padding:4px 0;'>📖 Asignatura</div>", unsafe_allow_html=True)
        with ch_p1:
            st.markdown("<div style='font-weight:700;font-size:0.84rem;color:#1a5c32;padding:4px 0;'>👨‍🏫 Profesor 1</div>", unsafe_allow_html=True)
        with ch_p2:
            st.markdown("<div style='font-weight:700;font-size:0.84rem;color:#1a5c32;padding:4px 0;'>👨‍🏫 Profesor 2</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin:2px 0 8px 0;border-color:#e2e8f0;'>", unsafe_allow_html=True)

        nuevas_elecciones = {}

        for idx_asig, asig in enumerate(asignaturas_list):
            asignados_previos = asignaciones_existentes.get(asig, [])
            
            # Determinar valor previo para Profesor 1
            default_p1 = "— Sin Asignar —"
            if len(asignados_previos) >= 1:
                p1_prev = asignados_previos[0]
                for op in profesores_opciones:
                    if p1_prev['rut'] in op or p1_prev['nombre'] in op:
                        default_p1 = op
                        break

            # Determinar valor previo para Profesor 2
            default_p2 = "— Sin Asignar —"
            if len(asignados_previos) >= 2:
                p2_prev = asignados_previos[1]
                for op in profesores_opciones:
                    if p2_prev['rut'] in op or p2_prev['nombre'] in op:
                        default_p2 = op
                        break

            c_asig, c_p1, c_p2 = st.columns([2.2, 2.5, 2.5])
            with c_asig:
                st.markdown(f"<div style='font-weight:600;font-size:0.82rem;color:#2d3748;padding-top:7px;'>{asig}</div>", unsafe_allow_html=True)
            with c_p1:
                idx_p1 = profesores_opciones.index(default_p1) if default_p1 in profesores_opciones else 0
                sel_p1 = st.selectbox(
                    f"P1_{asig}",
                    options=profesores_opciones,
                    index=idx_p1,
                    key=f"matriz_p1_{curso_seleccionado}_{idx_asig}",
                    label_visibility="collapsed"
                )
            with c_p2:
                idx_p2 = profesores_opciones.index(default_p2) if default_p2 in profesores_opciones else 0
                sel_p2 = st.selectbox(
                    f"P2_{asig}",
                    options=profesores_opciones,
                    index=idx_p2,
                    key=f"matriz_p2_{curso_seleccionado}_{idx_asig}",
                    label_visibility="collapsed"
                )

            nuevas_elecciones[asig] = {"profesor_1": sel_p1, "profesor_2": sel_p2}

        st.markdown("<hr style='margin:12px 0 10px 0;'>", unsafe_allow_html=True)
        col_btn_save, col_esp = st.columns([2.2, 4.8])
        with col_btn_save:
            btn_guardar_matriz = st.form_submit_button(
                f"💾 Guardar Asignaciones de {curso_seleccionado}",
                type="primary",
                use_container_width=True
            )

        if btn_guardar_matriz:
            if not sheet_asignaciones:
                st.error("❌ No hay conexión con la hoja Asignaciones.")
            else:
                with st.spinner(f"Guardando asignaciones de {curso_seleccionado} en Google Sheets..."):
                    try:
                        # 1. Leer todas las asignaciones existentes
                        recs_act = sheet_asignaciones.get_all_records()
                        df_act = pd.DataFrame(recs_act) if recs_act else pd.DataFrame(columns=["RUT_Profesor", "Nombre_Profesor", "Curso", "Asignatura"])
                        
                        if not df_act.empty:
                            col_c_act = next((c for c in df_act.columns if 'curs' in c.lower()), 'Curso')
                            col_a_act = next((c for c in df_act.columns if 'asig' in c.lower()), 'Asignatura')
                            # Conservar todas las filas de otros cursos (omitiendo cualquier residuo de JEFATURA)
                            df_otros_cursos = df_act[
                                (df_act[col_c_act].astype(str).str.strip() != str(curso_seleccionado).strip()) &
                                (df_act[col_a_act].astype(str).str.strip().str.upper() != 'JEFATURA')
                            ].copy()
                        else:
                            df_otros_cursos = pd.DataFrame(columns=["RUT_Profesor", "Nombre_Profesor", "Curso", "Asignatura"])

                        # 2. Construir filas nuevas para las asignaturas de este curso
                        filas_curso_nuevas = []

                        for asig_nom, profs_data in nuevas_elecciones.items():
                            p1_val = profs_data["profesor_1"]
                            p2_val = profs_data["profesor_2"]

                            # Agregar Profesor 1 si está asignado
                            if p1_val != "— Sin Asignar —" and p1_val in profesores_dict:
                                datos_p1 = profesores_dict[p1_val]
                                filas_curso_nuevas.append({
                                    "RUT_Profesor": datos_p1["rut"],
                                    "Nombre_Profesor": datos_p1["nombre"],
                                    "Curso": str(curso_seleccionado),
                                    "Asignatura": asig_nom
                                })

                            # Agregar Profesor 2 si está asignado y no es el mismo que P1
                            if p2_val != "— Sin Asignar —" and p2_val in profesores_dict:
                                if p2_val != p1_val:
                                    datos_p2 = profesores_dict[p2_val]
                                    filas_curso_nuevas.append({
                                        "RUT_Profesor": datos_p2["rut"],
                                        "Nombre_Profesor": datos_p2["nombre"],
                                        "Curso": str(curso_seleccionado),
                                        "Asignatura": asig_nom
                                    })

                        df_nuevas_curso = pd.DataFrame(filas_curso_nuevas)
                        df_guardar_final = pd.concat([df_otros_cursos, df_nuevas_curso], ignore_index=True)
                        df_guardar_final = df_guardar_final.fillna("")

                        # 3. Guardar en Google Sheets de forma atómica
                        sheet_asignaciones.clear()
                        headers_asig = ["RUT_Profesor", "Nombre_Profesor", "Curso", "Asignatura"]
                        if not df_guardar_final.empty:
                            sheet_asignaciones.update(values=[headers_asig] + df_guardar_final[headers_asig].values.tolist())
                        else:
                            sheet_asignaciones.append_row(headers_asig)

                        st.session_state['asig_guardada_ok'] = True
                        st.session_state['asig_guardada_msg'] = f"✅ ¡Asignaciones de **{curso_seleccionado}** actualizadas exitosamente! ({len(filas_curso_nuevas)} registros activos)"
                        st.toast(f"✅ ¡Asignaciones de {curso_seleccionado} guardadas!", icon="📚")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al guardar en Google Sheets: {e}")

elif st.session_state.current_module == 'asistencia':
    import calendar as cal_mod

    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>📅 Control de Asistencia</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_asistencia", use_container_width=True):
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 10px 0;'>", unsafe_allow_html=True)

    sheet_alumnos, _, _, _, _ = get_sheets()
    sheet_asistencia = get_asistencia_sheet()

    # ── CSS Específico de Asistencia Compacta ───────────────────────────────────
    st.markdown("""
    <style>
    div[data-testid="stTextInput"] input {
        font-size: 0.82rem !important;
        padding: 2px 4px !important;
        text-align: center !important;
        height: 30px !important;
        min-height: 30px !important;
    }
    .asist-nom-container {
        border: 1px solid #EBEBEB;
        border-radius: 8px;
        background: #FFFFFF;
        padding: 10px;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.02);
    }
    .asist-nom-item {
        display: flex;
        align-items: center;
        padding: 3px 6px;
        border-bottom: 1px solid #F5F5F5;
        font-size: 0.80rem;
    }
    .asist-nom-item:last-child {
        border-bottom: none;
    }
    .asist-nom-num {
        display: inline-block;
        width: 26px;
        font-weight: 700;
        color: #008F39;
        font-size: 0.82rem;
    }
    .asist-nom-nombre {
        color: #2D3748;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .asist-nom-ret {
        color: #E53E3E;
        font-size: 0.70rem;
        margin-left: 6px;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Cursos disponibles ───────────────────────────────────────────────────
    cursos_disp = []
    df_alumnos_raw = pd.DataFrame()
    if sheet_alumnos:
        try:
            ra = sheet_alumnos.get_all_records()
            df_alumnos_raw = pd.DataFrame(ra) if ra else pd.DataFrame()
            if not df_alumnos_raw.empty:
                col_c_tmp = next((c for c in df_alumnos_raw.columns if 'curs' in c.lower()), None)
                if col_c_tmp:
                    cursos_disp = sorted([str(v) for v in df_alumnos_raw[col_c_tmp].unique() if str(v).strip()], key=orden_curso_sistema)
        except:
            pass

    if not cursos_disp:
        st.warning("⚠️ No hay cursos disponibles. Carga primero la base de datos de alumnos.")
        if st.button("⬅️ Volver", key="btn_asist_nocursos"):
            navigate('home'); st.rerun()
        st.stop()

    # ── Inicializar state ────────────────────────────────────────────────────
    today = datetime.date.today()
    if 'asist_year'  not in st.session_state: st.session_state.asist_year  = today.year
    if 'asist_month' not in st.session_state: st.session_state.asist_month = today.month
    if 'asist_curso' not in st.session_state: st.session_state.asist_curso = cursos_disp[0]

    year  = st.session_state.asist_year
    month = st.session_state.asist_month

    MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    # ── Fila de controles compacta con navegación y calendario ───────────────
    col_c, col_p, col_m, col_cal, col_n, col_s = st.columns([2.4, 0.42, 1.7, 1.1, 0.42, 1.9])

    with col_c:
        idx_c = cursos_disp.index(st.session_state.asist_curso) if st.session_state.asist_curso in cursos_disp else 0
        curso_asist = st.selectbox("📚 Curso:", cursos_disp, index=idx_c, key="sel_asist_curso", label_visibility="collapsed")

    with col_p:
        if st.button("◀", key="btn_asist_prev"):
            m, y = st.session_state.asist_month, st.session_state.asist_year
            if m == 1: st.session_state.asist_month = 12; st.session_state.asist_year = y - 1
            else: st.session_state.asist_month = m - 1
            st.session_state.asist_loaded_key = ""
            st.rerun()

    with col_m:
        st.markdown(
            f"<div style='text-align:center;font-size:1.0rem;font-weight:700;padding-top:4px;color:#1a5c32;white-space:nowrap;'>"
            f"{MESES[st.session_state.asist_month-1]} {st.session_state.asist_year}</div>",
            unsafe_allow_html=True
        )

    with col_cal:
        f_cal_val = datetime.date(st.session_state.asist_year, st.session_state.asist_month, 1)
        f_cal_sel = st.date_input(
            "📅 Mes:",
            value=f_cal_val,
            key=f"asist_cal_{st.session_state.asist_year}_{st.session_state.asist_month}",
            format="DD/MM/YYYY",
            label_visibility="collapsed"
        )
        if f_cal_sel and (f_cal_sel.month != st.session_state.asist_month or f_cal_sel.year != st.session_state.asist_year):
            st.session_state.asist_month = f_cal_sel.month
            st.session_state.asist_year = f_cal_sel.year
            st.session_state.asist_loaded_key = ""
            st.rerun()

    with col_n:
        if st.button("▶", key="btn_asist_next"):
            m, y = st.session_state.asist_month, st.session_state.asist_year
            if m == 12: st.session_state.asist_month = 1; st.session_state.asist_year = y + 1
            else: st.session_state.asist_month = m + 1
            st.session_state.asist_loaded_key = ""
            st.rerun()

    with col_s:
        guardar_asist = st.button("💾 Guardar mes", type="primary",
                                   key="btn_guardar_asist", use_container_width=True)

    st.markdown(
        "<div style='font-size:0.88rem;color:#555;margin:-4px 0 6px 0;'>"
        "💡 <b>Comandos rápidos:</b> <code>ok</code> (todos presentes) · "
        "<code>todos</code> (todos ausentes) · "
        "<code>sc</code> (sin clases) · "
        "<code>borrar</code> (limpiar) · "
        "<code>1-4-15</code> (N° de lista inasistentes)</div>",
        unsafe_allow_html=True
    )
    st.markdown("<hr style='margin-top:2px;margin-bottom:8px;'>", unsafe_allow_html=True)

    if st.session_state.get('asist_guardada_ok', False):
        st.success(st.session_state.get('asist_guardada_msg', "✅ ¡Asistencia guardada exitosamente!"))
        st.session_state['asist_guardada_ok'] = False

    # ── Preparar nómina de alumnos con N° de lista ───────────────────────────
    alumnos_nomina = []
    conf_inst_asis = cargar_datos_configuracion_reportes()
    f_inicio_semestre_1 = conf_inst_asis.get("s1_ini", datetime.date(year, 3, 4))

    if not df_alumnos_raw.empty:
        df_al_work = df_alumnos_raw.copy()
        df_al_work.columns = [str(c).strip() for c in df_al_work.columns]
        col_c_al = next((c for c in df_al_work.columns if 'curs' in c.lower()), None)
        col_n_al = next((c for c in df_al_work.columns if 'nomb' in c.lower()), None)
        col_o_al = next((c for c in df_al_work.columns if any(x in c.lower() for x in ['list', 'orden', 'n°', 'nro'])), None)

        if col_c_al and col_n_al:
            df_curso_al = df_al_work[df_al_work[col_c_al].astype(str).str.strip() == str(curso_asist)].copy()
            if not df_curso_al.empty:
                if col_o_al:
                    df_curso_al['_ord'] = pd.to_numeric(df_curso_al[col_o_al], errors='coerce').fillna(999).astype(int)
                else:
                    df_curso_al = df_curso_al.sort_values(col_n_al)
                    df_curso_al['_ord'] = range(1, len(df_curso_al) + 1)
                df_curso_al = df_curso_al.sort_values('_ord')

                for _, r_alu in df_curso_al.iterrows():
                    f_info = extraer_fechas_alumno(r_alu, f_inicio_semestre_1)
                    alumnos_nomina.append({
                        "num": int(r_alu['_ord']),
                        "nombre": str(r_alu[col_n_al]).strip(),
                        "retirado": f_info["es_retirado"],
                        "ingreso_tardio": f_info["es_ingreso_tardio"],
                        "f_inicio_efectiva": f_info["f_inicio_efectiva"]
                    })

    # ── Detectar cambio de curso/mes → recargar datos ────────────────────────
    year  = st.session_state.asist_year
    month = st.session_state.asist_month
    lk    = f"{curso_asist}_{year}_{month}"

    if st.session_state.get('asist_loaded_key') != lk:
        # Limpiar inputs anteriores
        for k in [k for k in st.session_state if k.startswith('asist_dia_')]:
            del st.session_state[k]

        # Cargar datos del mes para este curso (consulta directa y ultra rapida a Supabase)
        datos_mes = {}
        if sheet_asistencia:
            try:
                mes_pre = f"{year:04d}-{month:02d}"
                if hasattr(sheet_asistencia, '_client'):
                    resp_mes = sheet_asistencia._client.table('asistencia')\
                        .select('fecha,datos')\
                        .eq('curso', str(curso_asist))\
                        .like('fecha', f'{mes_pre}%')\
                        .execute()
                    for r in (resp_mes.data or []):
                        f_k = str(r.get('fecha', '')).strip()
                        d_v = str(r.get('datos', '')).strip()
                        if f_k:
                            datos_mes[f_k] = d_v
                else:
                    recs_a = sheet_asistencia.get_all_records()
                    df_a = pd.DataFrame(recs_a) if recs_a else pd.DataFrame()
                    if not df_a.empty:
                        df_a.columns = [str(c).strip() for c in df_a.columns]
                        col_f_a = next((c for c in df_a.columns if 'fecha' in c.lower()), None)
                        col_c_a = next((c for c in df_a.columns if 'curs'  in c.lower()), None)
                        col_d_a = next((c for c in df_a.columns if 'dato'  in c.lower()), None)
                        if all([col_f_a, col_c_a, col_d_a]):
                            df_mes = df_a[
                                (df_a[col_f_a].astype(str).str.startswith(mes_pre)) &
                                (df_a[col_c_a].astype(str).str.strip() == str(curso_asist))
                            ]
                            for _, row_a in df_mes.iterrows():
                                datos_mes[str(row_a[col_f_a]).strip()] = str(row_a[col_d_a]).strip()
            except Exception:
                pass

        # Pre-poblar session_state
        first_d = datetime.date(year, month, 1)
        n_days  = cal_mod.monthrange(year, month)[1]
        wdays   = [first_d + datetime.timedelta(days=i)
                   for i in range(n_days)
                   if (first_d + datetime.timedelta(days=i)).weekday() < 5]
        for d in wdays:
            fs = d.strftime("%Y-%m-%d")
            st.session_state[f"asist_dia_{fs}"] = datos_mes.get(fs, "")

        st.session_state.asist_loaded_key = lk
        st.session_state.asist_curso      = curso_asist

    # ── Estructura de Dos Columnas: Calendario (72%) + Nómina N° Lista (28%) ──
    col_calendario, col_nomina = st.columns([3.2, 1.3], gap="small")

    with col_nomina:
        st.markdown(
            f"<div style='font-size:0.85rem;font-weight:700;color:#1a5c32;margin-bottom:4px;'>"
            f"📋 Lista del Curso ({len(alumnos_nomina)})</div>",
            unsafe_allow_html=True
        )
        if not alumnos_nomina:
            st.info("Sin nómina de alumnos cargada.")
        else:
            items_html = ""
            for al in alumnos_nomina:
                if al["retirado"]:
                    ret_tag = "<span style='background:#fee2e2;color:#b91c1c;border:1px solid #f87171;font-size:0.68rem;font-weight:700;padding:1px 5px;border-radius:4px;margin-left:6px;'>RETIRADO</span>"
                    cls_item = " style='background:#fef2f2;border-left:3px solid #ef4444;color:#991b1b;'"
                else:
                    ret_tag = ""
                    cls_item = ""
                num_badge = str(al['num'])
                items_html += (
                    f"<div class='asist-nom-item'{cls_item}>"
                    f"<span class='asist-nom-num'>{num_badge}.</span>"
                    f"<span class='asist-nom-nombre' title='{al['nombre']}'>{al['nombre']}</span>"
                    f"{ret_tag}"
                    f"</div>"
                )
            st.markdown(
                f"<div class='asist-nom-container' style='max-height:430px;overflow-y:auto;'>"
                f"{items_html}"
                f"</div>",
                unsafe_allow_html=True
            )

    with col_calendario:
        first_d  = datetime.date(year, month, 1)
        n_days   = cal_mod.monthrange(year, month)[1]
        all_wdays = [first_d + datetime.timedelta(days=i)
                     for i in range(n_days)
                     if (first_d + datetime.timedelta(days=i)).weekday() < 5]

        if not all_wdays:
            st.info("No hay días hábiles en este mes.")
        else:
            first_dow = all_wdays[0].weekday()
            padded    = [None] * first_dow + all_wdays
            while len(padded) % 5 != 0:
                padded.append(None)

            DIA_NOM = ["Lun", "Mar", "Mié", "Jue", "Vie"]
            h_cols  = st.columns(5)
            for i, dn in enumerate(DIA_NOM):
                h_cols[i].markdown(
                    f"<div style='text-align:center;font-weight:700;font-size:0.78rem;background:#f0f7f2;"
                    f"color:#1a5c32;padding:4px 0;border-radius:4px;margin-bottom:4px;'>{dn}</div>",
                    unsafe_allow_html=True
                )

            n_weeks = len(padded) // 5
            for w in range(n_weeks):
                week  = padded[w*5:(w+1)*5]
                wcols = st.columns(5)
                for i, day in enumerate(week):
                    with wcols[i]:
                        if day is None:
                            st.markdown("<div style='min-height:58px'></div>", unsafe_allow_html=True)
                        else:
                            fs  = day.strftime("%Y-%m-%d")
                            sk  = f"asist_dia_{fs}"
                            val = str(st.session_state.get(sk, "")).strip().lower()

                            if val == "ok":
                                estado_html = "<span style='color:#008F39;font-size:0.68rem;font-weight:600;'>✅ Completa</span>"
                            elif val == "todos":
                                estado_html = "<span style='color:#cc0000;font-size:0.68rem;font-weight:600;'>❌ Aus. Total</span>"
                            elif val == "sc":
                                estado_html = "<span style='color:#6366f1;font-size:0.68rem;font-weight:600;'>🚫 Sin Clases</span>"
                            elif val and val != "borrar":
                                estado_html = f"<span style='color:#d97706;font-size:0.68rem;font-weight:600;'>⚠️ {val}</span>"
                            else:
                                estado_html = "<span style='color:#aaa;font-size:0.68rem;'>—</span>"

                            st.markdown(
                                f"<div style='display:flex;justify-content:space-between;align-items:center;padding:0 2px;'>"
                                f"<span style='font-weight:700;color:#1a5c32;font-size:0.85rem;'>{day.day}</span>"
                                f"<span>{estado_html}</span>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            st.text_input(
                                label=fs, key=sk,
                                label_visibility="collapsed"
                            )
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

    # ── Guardar ──────────────────────────────────────────────────────────────────
    if guardar_asist:
        if not sheet_asistencia:
            st.error("❌ No se puede conectar con la hoja Asistencia.")
        else:
            errores_val = []
            nuevas_filas = []
            for day in all_wdays:
                fs  = day.strftime("%Y-%m-%d")
                sk  = f"asist_dia_{fs}"
                raw = str(st.session_state.get(sk, "")).strip().lower()

                if not raw or raw == "borrar":
                    continue

                if raw == "ok":
                    nuevas_filas.append({"Fecha": fs, "Curso": str(curso_asist), "Datos": "ok",   "Tipo": "completa"})
                elif raw == "todos":
                    nuevas_filas.append({"Fecha": fs, "Curso": str(curso_asist), "Datos": "todos", "Tipo": "total"})
                elif raw == "sc":
                    nuevas_filas.append({"Fecha": fs, "Curso": str(curso_asist), "Datos": "sc", "Tipo": "sin_clases"})
                else:
                    partes = raw.split("-")
                    nums   = [p.strip() for p in partes if p.strip().isdigit()]
                    if nums and len(nums) == len(partes):
                        datos_str = "-".join(nums)
                        nuevas_filas.append({"Fecha": fs, "Curso": str(curso_asist), "Datos": datos_str, "Tipo": "parcial"})
                    else:
                        errores_val.append(f"Día {day.day}: valor '{raw}' no es válido.")

            if errores_val:
                for ev in errores_val:
                    st.error(f"❌ {ev} — Usa exclusivamente números separados por guión (ej: 1-4-15), o los comandos: ok | todos | sc | borrar")
                st.info("💡 **Por seguridad, no se modificó la base de datos.** Corrige los días señalados arriba y vuelve a presionar '💾 Guardar mes'.")
            else:
                try:
                    with st.spinner("Guardando en la base de datos..."):
                        mes_pre = f"{year:04d}-{month:02d}"

                        # 1. Eliminar exclusivamente los registros de este curso y este mes,
                        # protegiendo al 100% todos los demás cursos y meses del colegio.
                        if hasattr(sheet_asistencia, '_client'):
                            sheet_asistencia._client.table('asistencia').delete().eq('curso', str(curso_asist)).like('fecha', f'{mes_pre}%').execute()

                        # 2. Insertar los registros actualizados del mes
                        if nuevas_filas:
                            if hasattr(sheet_asistencia, '_client'):
                                db_records = [{
                                    'fecha': r['Fecha'],
                                    'curso': r['Curso'],
                                    'datos': r['Datos'],
                                    'tipo':  r['Tipo']
                                } for r in nuevas_filas]
                                sheet_asistencia._client.table('asistencia').insert(db_records).execute()
                            else:
                                sheet_asistencia.append_rows([[r['Fecha'], r['Curso'], r['Datos'], r['Tipo']] for r in nuevas_filas])

                    st.session_state['asist_guardada_ok'] = True
                    st.session_state['asist_guardada_msg'] = f"✅ ¡Asistencia de **{curso_asist}** para **{MESES[month-1]} {year}** guardada y actualizada exitosamente! ({len(nuevas_filas)} días registrados)"
                    st.toast(f"✅ ¡Asistencia de {curso_asist} ({MESES[month-1]} {year}) guardada!", icon="📅")
                    st.session_state.asist_loaded_key = ""   # forzar recarga
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")

    # ── Resumen anual ─────────────────────────────────────────────────────────────────
    dias_anio_count = 0
    if sheet_asistencia:
        try:
            if hasattr(sheet_asistencia, '_client'):
                resp_cnt = sheet_asistencia._client.table('asistencia')\
                    .select('id,tipo')\
                    .eq('curso', str(curso_asist))\
                    .like('fecha', f'{year}%')\
                    .neq('tipo', 'sin_clases')\
                    .execute()
                dias_anio_count = len(resp_cnt.data or [])
            else:
                recs_cnt = sheet_asistencia.get_all_records()
                df_cnt   = pd.DataFrame(recs_cnt) if recs_cnt else pd.DataFrame()
                if not df_cnt.empty:
                    df_cnt.columns = [str(c).strip() for c in df_cnt.columns]
                    col_f_c = next((c for c in df_cnt.columns if 'fecha' in c.lower()), None)
                    col_c_c = next((c for c in df_cnt.columns if 'curs'  in c.lower()), None)
                    if col_f_c and col_c_c:
                        col_t_c = next((c for c in df_cnt.columns if 'tipo' in c.lower()), None)
                        _df_cnt_f = df_cnt[
                            (df_cnt[col_f_c].astype(str).str.startswith(str(year))) &
                            (df_cnt[col_c_c].astype(str).str.strip() == str(curso_asist))
                        ]
                        if col_t_c:
                            _df_cnt_f = _df_cnt_f[_df_cnt_f[col_t_c].astype(str).str.strip().str.lower() != 'sin_clases']
                        dias_anio_count = len(_df_cnt_f)
        except Exception:
            pass

    with st.expander(f"📊 Resumen y % de asistencia  —  Días hábiles del curso ({year}): {dias_anio_count}"):
        if not sheet_asistencia or not sheet_alumnos:
            st.warning("No hay conexión con la base de datos.")
        else:
            try:
                # Datos del año
                recs_yr  = sheet_asistencia.get_all_records()
                df_yr    = pd.DataFrame(recs_yr) if recs_yr else pd.DataFrame()
                recs_alu = sheet_alumnos.get_all_records()
                df_alu   = pd.DataFrame(recs_alu) if recs_alu else pd.DataFrame()

                if df_yr.empty or df_alu.empty:
                    st.info("Sin datos suficientes para el resumen.")
                else:
                    df_yr.columns  = [str(c).strip() for c in df_yr.columns]
                    df_alu.columns = [str(c).strip() for c in df_alu.columns]

                    col_f_y  = next((c for c in df_yr.columns  if 'fecha' in c.lower()), None)
                    col_c_y  = next((c for c in df_yr.columns  if 'curs'  in c.lower()), None)
                    col_d_y  = next((c for c in df_yr.columns  if 'dato'  in c.lower()), None)
                    col_n_al = next((c for c in df_alu.columns if 'nomb'  in c.lower()), None)
                    col_c_al = next((c for c in df_alu.columns if 'curs'  in c.lower()), None)
                    col_o_al = next((c for c in df_alu.columns if any(
                                     x in c.lower() for x in ['list', 'orden', 'n°', 'nro'])), None)
                    col_b_al = next((c for c in df_alu.columns if 'baja'  in c.lower() or 'retir' in c.lower()), None)
                    col_f_ing_al = next((c for c in df_alu.columns if any(
                                         x in c.lower() for x in ['ingres', 'matric', 'matr_fec'])), None)

                    conf_inst_asis = cargar_datos_configuracion_reportes()
                    f_inicio_semestre_1 = conf_inst_asis.get("s1_ini", datetime.date(year, 3, 4))
                    f_fin_semestre_1    = conf_inst_asis.get("s1_fin", datetime.date(year, 6, 18))
                    f_inicio_semestre_2 = conf_inst_asis.get("s2_ini", datetime.date(year, 7, 6))
                    f_fin_semestre_2    = conf_inst_asis.get("s2_fin", datetime.date(year, 12, 11))

                    if not all([col_f_y, col_c_y, col_d_y, col_n_al, col_c_al]):
                        st.warning("Faltan columnas necesarias en la base de datos.")
                    else:
                        col_cur_y = next((c for c in df_yr.columns if 'curs' in c.lower()), col_c_y)
                        df_curso_yr = df_yr[
                            (df_yr[col_f_y].astype(str).str.startswith(str(year))) &
                            (df_yr[col_cur_y].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, curso_asist)))
                        ].copy()

                        # Excluir días marcados como "sin_clases" o "sc"
                        col_t_y = next((c for c in df_curso_yr.columns if 'tipo' in c.lower()), None)
                        if col_t_y:
                            df_curso_yr = df_curso_yr[df_curso_yr[col_t_y].astype(str).str.strip().str.lower() != 'sin_clases']
                        df_curso_yr = df_curso_yr[~df_curso_yr[col_d_y].astype(str).str.strip().str.lower().isin(['sc', 'borrar', ''])]

                        # Excluir fechas fuera de los semestres escolares oficiales (vacaciones de invierno / fuera de rango)
                        def _es_dia_escolar_oficial(f_str):
                            fd = parse_fecha_flexible(f_str)
                            if not fd: return False
                            return (f_inicio_semestre_1 <= fd <= f_fin_semestre_1) or (f_inicio_semestre_2 <= fd <= f_fin_semestre_2)

                        df_curso_yr = df_curso_yr[df_curso_yr[col_f_y].apply(_es_dia_escolar_oficial)]
                        total_dias = len(df_curso_yr)

                        df_alu_c = df_alu[df_alu[col_c_al].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, curso_asist))].copy()

                        if df_alu_c.empty:
                            st.info("No hay alumnos registrados para este curso.")
                        else:
                            # Ordenar por N° lista
                            if col_o_al:
                                df_alu_c['_ord'] = pd.to_numeric(df_alu_c[col_o_al], errors='coerce').fillna(999).astype(int)
                            else:
                                df_alu_c = df_alu_c.sort_values(col_n_al)
                                df_alu_c['_ord'] = range(1, len(df_alu_c)+1)
                            df_alu_c = df_alu_c.sort_values('_ord')

                            # Calcular por alumno mediante la función oficial y unificada
                            rows_res = []
                            for _, alu in df_alu_c.iterrows():
                                num_l    = int(alu['_ord'])
                                nombre_a = str(alu[col_n_al])
                                asis_alu = calcular_asistencia_estudiante(alu, df_curso_yr, curso_asist, periodo='anual', config_inst=conf_inst_asis)

                                etiqueta_alu = nombre_a
                                if asis_alu["es_retirado"]:
                                    etiqueta_alu += " 🔴 (Retirado)"

                                rows_res.append({
                                    "N°":                  num_l,
                                    "Alumno":              etiqueta_alu,
                                    "Días Clase":         asis_alu["dias_clase"],
                                    "Días Asistidos":     asis_alu["dias_asist"],
                                    "Días Inasistencia":  asis_alu["dias_inasist"],
                                    "% Asistencia":        asis_alu["pct_asist"]
                                })

                            df_res = pd.DataFrame(rows_res)

                            st.markdown(f"""
                            | 📅 Total días clase del curso ({year}) | **{total_dias}** |
                            |---|---|
                            """)

                            # Color condicional
                            def _color_pct(val):
                                if val >= 85: return 'color: #008F39; font-weight:700'
                                if val >= 75: return 'color: #e67e00; font-weight:700'
                                return 'color: #cc0000; font-weight:700'

                            styled_res = df_res.style.map(_color_pct, subset=['% Asistencia'])\
                                                     .format({'% Asistencia': '{:.1f}%'})
                            st.dataframe(styled_res, use_container_width=True, hide_index=True)
                            st.caption("🟢 ≥85% asistencia correcta · 🟠 75-84% en riesgo · 🔴 <75% crítico")

            except Exception as e:
                st.error(f"Error al calcular resumen: {e}")

    st.write("")
    if st.button("⬅️ Volver al Dashboard Principal", key="btn_volver_asistencia"):
        navigate('home')
        st.rerun()

elif st.session_state.current_module == 'configuracion':
    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>⚙️ Configuración del Establecimiento</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_conf", use_container_width=True):
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 14px 0;'>", unsafe_allow_html=True)

    sheet_config = get_config_sheet()
    if not sheet_config:
        st.error("❌ Error de conexión con la hoja de configuración.")
    else:
        try:
            recs_c = sheet_config.get_all_records()
            conf_dict = {}
            for r in recs_c:
                k = str(r.get("Clave", "")).strip()
                v = str(r.get("Valor", "")).strip()
                if k: conf_dict[k] = v

            # Valores actuales o predeterminados
            c_nom_col = conf_dict.get("nombre_colegio", "ESCUELA VILLA LAS PEÑAS")
            c_region = conf_dict.get("region", "BÍOBÍO")
            c_ciudad = conf_dict.get("ciudad", "Mulchén")
            c_director = conf_dict.get("nombre_director", "RUBÉN MARCOS QUEZADA BALBOA")
            c_rbd = conf_dict.get("rbd", "4410-5")
            c_s1_ini = conf_dict.get("semestre_1_inicio", "01-03-2026")
            c_s1_fin = conf_dict.get("semestre_1_fin", "05-07-2026")
            c_s2_ini = conf_dict.get("semestre_2_inicio", "22-07-2026")
            c_s2_fin = conf_dict.get("semestre_2_fin", "10-12-2026")
            c_firma_b64 = conf_dict.get("firma_director_b64", "")

            tab_datos_col, tab_permisos_cfg = st.tabs(["🏛️ Datos Institucionales y Calendario", "🛡️ Roles y Permisos de Módulos"])

            with tab_datos_col:
                st.markdown(
                    "<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 16px;margin-bottom:14px;color:#334155;font-size:0.83rem;'>"
                    "ℹ️ Estos datos se utilizarán para la cabecera oficial, firma ministerial y cálculo de períodos en los <b>Informes de Notas</b> y documentos oficiales.</div>",
                    unsafe_allow_html=True
                )

                col_izq_cfg, col_der_cfg = st.columns([3.2, 2.8], gap="large")

                with col_izq_cfg:
                    st.markdown("<div style='font-weight:700;font-size:0.92rem;color:#1a5c32;margin-bottom:8px;'>🏛️ Identificación Institucional</div>", unsafe_allow_html=True)
                    with st.container(border=True):
                        in_cfg_col = st.text_input("Nombre del Establecimiento:", value=c_nom_col, key="cfg_in_col").strip()
                        c_c0, c_c1, c_c2 = st.columns([1.2, 1.2, 1])
                        with c_c0:
                            in_cfg_reg = st.text_input("Región:", value=c_region, key="cfg_in_reg").strip()
                        with c_c1:
                            in_cfg_ciudad = st.text_input("Ciudad / Comuna:", value=c_ciudad, key="cfg_in_ciu").strip()
                        with c_c2:
                            in_cfg_rbd = st.text_input("RBD:", value=c_rbd, key="cfg_in_rbd").strip()

                        in_cfg_dir = st.text_input("Nombre Completo del Director(a):", value=c_director, key="cfg_in_dir").strip()

                    st.markdown("<div style='font-weight:700;font-size:0.92rem;color:#1a5c32;margin:12px 0 8px 0;'>📅 Calendario de Semestres Escolares</div>", unsafe_allow_html=True)
                    with st.container(border=True):
                        # Función auxiliar para parsear fechas en formato dd-mm-aaaa
                        def _parse_fecha(s, fallback):
                            try:
                                return datetime.datetime.strptime(s.strip(), "%d-%m-%Y").date()
                            except Exception:
                                return fallback

                        st.markdown("<div style='font-weight:600;font-size:0.82rem;color:#475569;'>1° Semestre:</div>", unsafe_allow_html=True)
                        s1_c1, s1_c2 = st.columns(2)
                        with s1_c1:
                            _d_s1_ini = _parse_fecha(c_s1_ini, datetime.date(datetime.date.today().year, 3, 1))
                            _v_s1_ini = st.date_input("Fecha Inicio:", value=_d_s1_ini, key="cfg_in_s1_ini", format="DD/MM/YYYY")
                            in_s1_ini = _v_s1_ini.strftime("%d-%m-%Y") if _v_s1_ini else c_s1_ini
                        with s1_c2:
                            _d_s1_fin = _parse_fecha(c_s1_fin, datetime.date(datetime.date.today().year, 7, 5))
                            _v_s1_fin = st.date_input("Fecha Término:", value=_d_s1_fin, key="cfg_in_s1_fin", format="DD/MM/YYYY")
                            in_s1_fin = _v_s1_fin.strftime("%d-%m-%Y") if _v_s1_fin else c_s1_fin

                        st.markdown("<div style='font-weight:600;font-size:0.82rem;color:#475569;margin-top:8px;'>2° Semestre:</div>", unsafe_allow_html=True)
                        s2_c1, s2_c2 = st.columns(2)
                        with s2_c1:
                            _d_s2_ini = _parse_fecha(c_s2_ini, datetime.date(datetime.date.today().year, 7, 22))
                            _v_s2_ini = st.date_input("Fecha Inicio:", value=_d_s2_ini, key="cfg_in_s2_ini", format="DD/MM/YYYY")
                            in_s2_ini = _v_s2_ini.strftime("%d-%m-%Y") if _v_s2_ini else c_s2_ini
                        with s2_c2:
                            _d_s2_fin = _parse_fecha(c_s2_fin, datetime.date(datetime.date.today().year, 12, 10))
                            _v_s2_fin = st.date_input("Fecha Término:", value=_d_s2_fin, key="cfg_in_s2_fin", format="DD/MM/YYYY")
                            in_s2_fin = _v_s2_fin.strftime("%d-%m-%Y") if _v_s2_fin else c_s2_fin

                with col_der_cfg:
                    st.markdown("<div style='font-weight:700;font-size:0.92rem;color:#1a5c32;margin-bottom:8px;'>✍️ Firma y Timbre del Director(a)</div>", unsafe_allow_html=True)
                    with st.container(border=True):
                        st.write("Sube la imagen de la firma y timbre en formato **PNG** (idealmente con fondo transparente):")
                        
                        up_firma = st.file_uploader("Archivo PNG de Firma/Timbre:", type=['png', 'jpg', 'jpeg'], key="up_firma_dir")
                        firma_a_guardar = c_firma_b64

                        if up_firma is not None:
                            try:
                                from PIL import Image
                                import io
                                img_pil = Image.open(up_firma)
                                # Convertir a RGBA para preservar transparencia
                                img_pil = img_pil.convert("RGBA")
                                # Redimensionar para firma proporcional (ancho máx 260px, alto máx 90px)
                                img_pil.thumbnail((260, 90), Image.Resampling.LANCZOS)
                                
                                buffer_out = io.BytesIO()
                                img_pil.save(buffer_out, format="PNG", optimize=True)
                                b_bytes = buffer_out.getvalue()
                                b64_str = base64.b64encode(b_bytes).decode('utf-8')
                                
                                firma_a_guardar = b64_str
                                st.session_state['temp_firma_b64'] = b64_str
                                st.success(f"✅ Firma procesada y optimizada ({len(firma_a_guardar)} caracteres, dentro del límite de Sheets).")
                            except Exception as e:
                                st.error(f"Error al procesar la imagen de firma: {e}")
                        elif 'temp_firma_b64' in st.session_state:
                            firma_a_guardar = st.session_state['temp_firma_b64']

                        if firma_a_guardar:
                            st.markdown("<div style='font-size:0.78rem;font-weight:600;color:#64748b;margin:8px 0 4px 0;'>Previsualización en Informes:</div>", unsafe_allow_html=True)
                            st.markdown(
                                f"<div style='background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;padding:12px;text-align:center;'>"
                                f"<img src='data:image/png;base64,{firma_a_guardar}' style='max-height:85px;max-width:240px;object-fit:contain;'/>"
                                f"<div style='font-size:0.8rem;font-weight:700;color:#1e293b;border-top:1px solid #94a3b8;margin-top:6px;padding-top:4px;'>{in_cfg_dir}</div>"
                                f"<div style='font-size:0.72rem;color:#64748b;'>DIRECTOR(A) DEL ESTABLECIMIENTO</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if st.button("🗑️ Quitar Firma", key="btn_quitar_firma"):
                                if 'temp_firma_b64' in st.session_state:
                                    del st.session_state['temp_firma_b64']
                                firma_a_guardar = ""
                                st.rerun()
                        else:
                            st.info("Sin firma digital cargada. En el informe se mostrará la línea tradicional para firma manual.")

                st.markdown("<hr style='margin:18px 0 12px 0;'>", unsafe_allow_html=True)

                if st.session_state.get('conf_guardada_ok', False):
                    st.success("✅ ¡Configuración del establecimiento guardada y actualizada exitosamente!")
                    st.session_state['conf_guardada_ok'] = False

                if st.button("💾 Guardar Toda la Configuración Institucional", type="primary", use_container_width=True, key="btn_save_config_all"):
                    with st.spinner("Guardando en la base de datos..."):
                        try:
                            filas_actualizadas = [
                                ["Clave", "Valor"],
                                ["nombre_colegio", in_cfg_col],
                                ["region", in_cfg_reg],
                                ["ciudad", in_cfg_ciudad],
                                ["nombre_director", in_cfg_dir],
                                ["rbd", in_cfg_rbd],
                                ["semestre_1_inicio", in_s1_ini],
                                ["semestre_1_fin", in_s1_fin],
                                ["semestre_2_inicio", in_s2_ini],
                                ["semestre_2_fin", in_s2_fin],
                                ["firma_director_b64", firma_a_guardar]
                            ]
                            if "matriz_permisos_roles" in conf_dict:
                                filas_actualizadas.append(["matriz_permisos_roles", conf_dict["matriz_permisos_roles"]])

                            sheet_config.clear()
                            sheet_config.update(values=filas_actualizadas)
                            st.session_state['conf_guardada_ok'] = True
                            st.toast("✅ ¡Configuración guardada exitosamente!", icon="🎉")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar configuración: {e}")

            with tab_permisos_cfg:
                st.markdown("<h3 style='margin:4px 0 6px 0;color:#1a5c32;font-size:1.15rem;'>🛡️ Matriz de Control de Acceso por Rol</h3>", unsafe_allow_html=True)
                st.markdown(
                    "<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 16px;margin-bottom:14px;color:#334155;font-size:0.83rem;'>"
                    "ℹ️ Define a qué módulos tiene acceso cada rol en la Escuela Villa Las Peñas. "
                    "El rol <b>Administrador Total</b> siempre cuenta con acceso irrestricto por seguridad del sistema.</div>",
                    unsafe_allow_html=True
                )

                matriz_actual_cfg = obtener_matriz_permisos(sheet_config)

                st.info("🔒 **Administrador Total:** Acceso permanente a todos los 12 módulos del sistema.")

                tabs_roles_cfg = st.tabs([f"🎭 {r}" for r in ROLES_CONFIGURABLES])

                cambios_matriz = {}
                for idx_r, rol_nom in enumerate(ROLES_CONFIGURABLES):
                    with tabs_roles_cfg[idx_r]:
                        st.markdown(f"**Permisos de acceso asignados para el rol: `{rol_nom}`**")
                        permisos_este_rol = matriz_actual_cfg.get(rol_nom, DEFAULT_PERMISOS_ROLES.get(rol_nom, []))

                        col_chk1, col_chk2 = st.columns(2)
                        nuevos_permisos_rol = []

                        for i_mod, mod in enumerate(MODULOS_SISTEMA):
                            col_destino = col_chk1 if i_mod < 6 else col_chk2
                            with col_destino:
                                esta_activo = mod["id"] in permisos_este_rol
                                chk_val = st.checkbox(
                                    f"{mod['titulo']} — *{mod['sub']}*",
                                    value=esta_activo,
                                    key=f"chk_perm_{rol_nom}_{mod['id']}"
                                )
                                if chk_val:
                                    nuevos_permisos_rol.append(mod["id"])

                        cambios_matriz[rol_nom] = nuevos_permisos_rol

                st.markdown("<hr style='margin:18px 0 12px 0;'>", unsafe_allow_html=True)

                if st.session_state.get('permisos_guardados_ok', False):
                    st.success("✅ ¡Permisos de roles institucionales guardados y aplicados exitosamente!")
                    st.session_state['permisos_guardados_ok'] = False

                if st.button("💾 Guardar Permisos de Roles", type="primary", use_container_width=True, key="btn_save_permisos_roles"):
                    with st.spinner("Guardando matriz de permisos en la base de datos..."):
                        try:
                            import json
                            v_json = json.dumps(cambios_matriz, ensure_ascii=False)

                            recs_raw = sheet_config.get_all_records()
                            df_cfg_all = pd.DataFrame(recs_raw) if recs_raw else pd.DataFrame(columns=["Clave", "Valor"])
                            df_cfg_all.columns = [str(c).strip() for c in df_cfg_all.columns]
                            if '_id' in df_cfg_all.columns:
                                df_cfg_all = df_cfg_all.drop(columns=['_id'])
                            if "Clave" not in df_cfg_all.columns: df_cfg_all["Clave"] = []
                            if "Valor" not in df_cfg_all.columns: df_cfg_all["Valor"] = []

                            m_perm = df_cfg_all["Clave"].astype(str).str.strip() == "matriz_permisos_roles"
                            if m_perm.any():
                                df_cfg_all.loc[m_perm, "Valor"] = v_json
                            else:
                                nueva_f = pd.DataFrame([{"Clave": "matriz_permisos_roles", "Valor": v_json}])
                                df_cfg_all = pd.concat([df_cfg_all, nueva_f], ignore_index=True)

                            sheet_config.clear()
                            sheet_config.update(values=[df_cfg_all.columns.tolist()] + df_cfg_all.values.tolist())
                            st.session_state['permisos_guardados_ok'] = True
                            st.toast("✅ ¡Permisos actualizados con éxito!", icon="🛡️")
                            st.rerun()
                        except Exception as err_p:
                            st.error(f"Error al guardar permisos: {err_p}")

        except Exception as e:
            st.error(f"Error al cargar módulo de configuración: {e}")



elif st.session_state.current_module == 'preacta':
    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>📊 Preacta Anual de Calificaciones</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_preacta", use_container_width=True):
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 12px 0;'>", unsafe_allow_html=True)

    sheet_alumnos, _, sheet_notas, _, sheet_asignaciones = get_sheets()
    sheet_asistencia = get_asistencia_sheet()
    sheet_preacta = get_preacta_sheet()
    sheet_config = get_config_sheet()

    if not sheet_alumnos or not sheet_notas or not sheet_preacta:
        st.error("❌ Error de conexión con la base de datos de Google Sheets.")
    else:
        try:
            # 1. Cargar Configuración del Establecimiento
            conf_data = {}
            if sheet_config:
                for r in sheet_config.get_all_records():
                    conf_data[str(r.get("Clave","")).strip()] = str(r.get("Valor","")).strip()

            anio_actual = datetime.date.today().year
            nombre_colegio = conf_data.get("nombre_colegio", "ESCUELA VILLA LAS PEÑAS")
            rbd_colegio = conf_data.get("rbd", "4410-5")
            comuna_colegio = conf_data.get("ciudad") or conf_data.get("comuna") or "Mulchén"
            director_colegio = conf_data.get("nombre_director", "CÉSAR JULIÁN ROA SOTO")
            firma_director_b64 = conf_data.get("firma_director_b64", "")

            # Cargar insignia en Base64
            insignia_b64 = ""
            for p_ins in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "insignia.png"), "insignia.png", "C:/SistemaEscolar/insignia.png"]:
                if os.path.exists(p_ins):
                    try:
                        with open(p_ins, "rb") as f_ins:
                            insignia_b64 = base64.b64encode(f_ins.read()).decode('utf-8')
                        break
                    except Exception:
                        pass

            # 2. Cargar Alumnos
            recs_al = sheet_alumnos.get_all_records()
            df_al = pd.DataFrame(recs_al) if recs_al else pd.DataFrame()
            if not df_al.empty:
                df_al.columns = [str(c).strip() for c in df_al.columns]

            col_c = next((c for c in df_al.columns if 'curs' in c.lower()), 'Curso')
            col_n = next((c for c in df_al.columns if 'nomb' in c.lower()), 'Nombre')
            col_r = next((c for c in df_al.columns if 'rut' in c.lower()), 'RUT')
            col_o = next((c for c in df_al.columns if any(x in c.lower() for x in ['list','orden','n°','nro'])), 'N° Lista')
            col_baja = next((c for c in df_al.columns if 'baja' in c.lower() or 'retir' in c.lower()), 'Fecha Baja')
            col_ing_pre = next((c for c in df_al.columns if any(x in c.lower() for x in ['ingres', 'matric', 'matr_fec'])), None)

            # Filtrar exclusivamente cursos de Educación Básica (1° a 8°) ya que Preacta y SIGE Tipo 4/5 corresponden al plan de asignaturas
            cursos_disp = [
                c for c in sorted([str(c).strip() for c in df_al[col_c].unique() if str(c).strip()], key=orden_curso_sistema)
                if not any(k in c.upper() for k in ['NT1', 'NT2', 'PRE-K', 'KINDER', 'PARV'])
            ] if not df_al.empty and col_c in df_al.columns else ["1° Básico A"]

            # Barra superior de filtros
            c_p1, c_p2 = st.columns([2.5, 1.5])
            with c_p1:
                curso_preacta_sel = st.selectbox("📚 Selecciona el Curso para Preacta:", cursos_disp, key="sel_curso_preacta")
            with c_p2:
                anio_preacta_sel = st.number_input("📅 Año Escolar:", min_value=2020, max_value=2035, value=anio_actual, step=1, key="num_anio_preacta")

            # Cargar alumnos del curso (incluyendo retirados para el registro oficial completo)
            df_curso = df_al[df_al[col_c].astype(str).str.strip() == str(curso_preacta_sel).strip()].copy()

            if df_curso.empty:
                st.warning(f"No hay alumnos registrados en {curso_preacta_sel}.")
            else:
                if col_o in df_curso.columns:
                    df_curso['_ord'] = pd.to_numeric(df_curso[col_o], errors='coerce').fillna(999).astype(int)
                else:
                    df_curso['_ord'] = range(1, len(df_curso) + 1)
                df_curso = df_curso.sort_values(by=['_ord'])

                # Buscar nombre del Profesor(a) Jefe en asignaciones docentes
                profesor_jefe_nombre = "Profesor(a) Jefe"
                if sheet_asignaciones:
                    try:
                        recs_asig = sheet_asignaciones.get_all_records()
                        if recs_asig:
                            df_asig_temp = pd.DataFrame(recs_asig)
                            col_as_c = next((c for c in df_asig_temp.columns if 'curs' in c.lower()), 'Curso')
                            col_as_p = next((c for c in df_asig_temp.columns if 'prof' in c.lower() and 'nomb' in c.lower()), 'Nombre_Profesor')
                            col_as_m = next((c for c in df_asig_temp.columns if 'asig' in c.lower()), 'Asignatura')
                            
                            import unicodedata
                            def _norm_cmp_jefe(s):
                                return "".join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn').lower().replace('°','').replace('.','').strip()

                            cur_preacta_norm = _norm_cmp_jefe(curso_preacta_sel)
                            m_jef = df_asig_temp[
                                df_asig_temp[col_as_c].apply(lambda x: _norm_cmp_jefe(x) == cur_preacta_norm) &
                                df_asig_temp[col_as_m].astype(str).str.strip().str.upper().eq('JEFATURA')
                            ]
                            if not m_jef.empty:
                                nom_p = str(m_jef.iloc[0].get(col_as_p, '')).strip()
                                if nom_p:
                                    profesor_jefe_nombre = nom_p
                    except Exception:
                        pass

                # Cargar Notas
                df_notas = pd.DataFrame(sheet_notas.get_all_records()) if sheet_notas else pd.DataFrame()
                if not df_notas.empty:
                    df_notas.columns = [str(c).strip() for c in df_notas.columns]
                    col_r_n = next((c for c in df_notas.columns if 'rut' in c.lower()), 'RUT')
                    col_a_n = next((c for c in df_notas.columns if 'asig' in c.lower()), 'Asignatura')
                    col_s_n = next((c for c in df_notas.columns if 'sem' in c.lower()), 'Semestre')
                    df_notas['RUT_NORM'] = df_notas[col_r_n].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()

                # Cargar Asistencia
                df_asist = pd.DataFrame(sheet_asistencia.get_all_records()) if sheet_asistencia else pd.DataFrame()
                if not df_asist.empty:
                    df_asist.columns = [str(c).strip() for c in df_asist.columns]

                # Cargar registros previos de Preacta guardados
                recs_preacta = sheet_preacta.get_all_records()
                df_preacta_existente = pd.DataFrame(recs_preacta) if recs_preacta else pd.DataFrame()
                if not df_preacta_existente.empty:
                    df_preacta_existente.columns = [str(c).strip() for c in df_preacta_existente.columns]
                    if 'RUT' in df_preacta_existente.columns:
                        df_preacta_existente['RUT_NORM'] = df_preacta_existente['RUT'].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()
                    if 'Año' in df_preacta_existente.columns:
                        df_preacta_existente['Año_STR'] = df_preacta_existente['Año'].astype(str).str.strip()

                # Asignaturas oficiales con división de Religión (Evangélica y Católica):
                asigs_catalogo = [
                    ("Lengua y Literatura", "Lenguaje", "Leng"),
                    ("Idioma Extranjero Inglés", "Inglés", "Ing"),
                    ("Matemática", "Matemática", "Mat"),
                    ("Historia, Geografía y Ciencias Sociales", "Historia", "Hist"),
                    ("Ciencias Naturales", "Ciencias", "Cien"),
                    ("Tecnología", "Tecnología", "Tec"),
                    ("Música", "Música", "Mús"),
                    ("Educación Física y Salud", "Ed. Física", "EF"),
                    ("Artes Visuales", "Artes", "Art"),
                    ("Religión Evangélica", "Rel. Evang.", "R.Ev"),
                    ("Religión Católica", "Rel. Cat.", "R.Cat"),
                    ("Orientación", "Orientación", "Ori")
                ]

                # Asistencia del curso y fechas de semestres institucionales
                conf_inst_pre = cargar_datos_configuracion_reportes()
                f_inicio_semestre_1_pre = conf_inst_pre.get("s1_ini", datetime.date(anio_preacta_sel, 3, 4))
                f_fin_semestre_1_pre    = conf_inst_pre.get("s1_fin", datetime.date(anio_preacta_sel, 6, 18))
                f_inicio_semestre_2_pre = conf_inst_pre.get("s2_ini", datetime.date(anio_preacta_sel, 7, 6))
                f_fin_semestre_2_pre    = conf_inst_pre.get("s2_fin", datetime.date(anio_preacta_sel, 12, 11))

                total_dias_asis = 0
                df_c_asist = pd.DataFrame()
                col_f_asist = 'Fecha'
                col_d_asist = 'Datos'
                if not df_asist.empty and 'Curso' in df_asist.columns:
                    col_cur_asist = next((c for c in df_asist.columns if 'curs' in c.lower()), 'Curso')
                    df_c_asist = df_asist[df_asist[col_cur_asist].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, curso_preacta_sel))]
                    total_dias_asis = len(df_c_asist)
                    col_f_asist = next((c for c in df_c_asist.columns if any(x in c.lower() for x in ['fecha', 'fec', 'dia'])), 'Fecha')
                    col_d_asist = next((c for c in df_c_asist.columns if any(x in c.lower() for x in ['dato', 'ina', 'aus', 'asis'])), 'Datos')

                def match_asig(nombre_bd, asig_cat_full):
                    nbd = str(nombre_bd).lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').strip()
                    ncat = str(asig_cat_full).lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').strip()
                    if nbd == ncat or nbd in ncat or ncat in nbd: return True
                    if 'matemat' in nbd and 'matemat' in ncat: return True
                    if ('lengua' in nbd or 'lenguaje' in nbd) and ('lengua' in ncat or 'lenguaje' in ncat): return True
                    if 'ingles' in nbd and 'ingles' in ncat: return True
                    if 'ciencias nat' in nbd and 'ciencias nat' in ncat: return True
                    if 'historia' in nbd and 'historia' in ncat: return True
                    if 'musica' in nbd and 'musica' in ncat: return True
                    if 'arte' in nbd and 'arte' in ncat: return True
                    if 'tecnol' in nbd and 'tecnol' in ncat: return True
                    if 'fisic' in nbd and 'fisic' in ncat: return True
                    if 'evangel' in nbd and 'evangel' in ncat: return True
                    if 'catolic' in nbd and 'catolic' in ncat: return True
                    if 'orientac' in nbd and 'orientac' in ncat: return True
                    if 'religi' in nbd and not any(k in nbd for k in ['evangel', 'catolic']) and 'evangel' in ncat: return True
                    return False

                def parsear_prom_num(val_raw):
                    if val_raw is None or str(val_raw).strip() in ['', 'None', 'nan']:
                        return None
                    try:
                        num = float(str(val_raw).replace(',', '.'))
                        if num > 10.0:
                            num = redondear_nota(num / 10.0, 1)
                        return num
                    except:
                        return None

                # Construir matriz de datos de cada alumno
                filas_matriz = []
                sumas_asig = {asig_corta: [] for _, asig_corta, _ in asigs_catalogo}

                for _, r_al in df_curso.iterrows():
                    r_raw = str(r_al.get(col_r, '')).strip()
                    r_limpio = r_raw.replace('.', '').strip()
                    r_norm = r_limpio.lower()
                    nom_al = str(r_al.get(col_n, '')).strip().upper()
                    n_lista = int(r_al.get('_ord', 1))

                    # Detección de Retirado
                    val_baja = str(r_al.get(col_baja, '')).strip() if col_baja in r_al else ""
                    es_ret = bool(val_baja and val_baja not in ['', 'nan', 'None'] and not pd.isna(r_al.get(col_baja)))

                    if es_ret:
                        filas_matriz.append({
                            "lista": n_lista,
                            "rut": r_limpio,
                            "rut_norm": r_norm,
                            "nombre": nom_al,
                            "es_retirado": True,
                            "fecha_baja": val_baja,
                            "promedios_asig": {asig_corta: "—" for _, asig_corta, _ in asigs_catalogo},
                            "prom_gral_num": 0.0,
                            "prom_gral_str": "—",
                            "pct_asist": 0.0,
                            "rojas": 0,
                            "situacion": "RETIRADO",
                            "promovido_chk": False,
                            "observaciones": f"RETIRADO ({val_baja})" if val_baja else "RETIRADO"
                        })
                        continue

                    # Alumno regular activo
                    df_n_al = df_notas[df_notas['RUT_NORM'] == r_norm] if not df_notas.empty and 'RUT_NORM' in df_notas.columns else pd.DataFrame()

                    promedios_asignaturas = {}
                    promedios_computables = []

                    for asig_full, asig_corta, _ in asigs_catalogo:
                        es_conceptual = any(k in asig_full.lower() for k in ['religi', 'orientac'])
                        p1_val, p2_val = "", ""
                        if not df_n_al.empty:
                            m_s1 = df_n_al[df_n_al[col_a_n].apply(lambda x: match_asig(x, asig_full)) & df_n_al[col_s_n].astype(str).str.contains('1')]
                            if not m_s1.empty:
                                p1_raw = m_s1.iloc[0].get("Promedio", "")
                                if es_conceptual:
                                    p1_val = nota_a_concepto(p1_raw)
                                else:
                                    num1 = parsear_prom_num(p1_raw)
                                    if num1 is not None:
                                        p1_val = f"{redondear_nota(num1):.1f}"

                            m_s2 = df_n_al[df_n_al[col_a_n].apply(lambda x: match_asig(x, asig_full)) & df_n_al[col_s_n].astype(str).str.contains('2')]
                            if not m_s2.empty:
                                p2_raw = m_s2.iloc[0].get("Promedio", "")
                                if es_conceptual:
                                    p2_val = nota_a_concepto(p2_raw)
                                else:
                                    num2 = parsear_prom_num(p2_raw)
                                    if num2 is not None:
                                        p2_val = f"{redondear_nota(num2):.1f}"

                        nf_final = ""
                        if es_conceptual:
                            nf_final = p2_val if p2_val else p1_val
                        else:
                            try:
                                f1 = float(p1_val) if p1_val else None
                                f2 = float(p2_val) if p2_val else None
                                if f1 is not None and f2 is not None:
                                    prom_a = redondear_nota((f1 + f2) / 2.0, 1)
                                    nf_final = f"{prom_a:.1f}".replace('.', ',')
                                    promedios_computables.append(prom_a)
                                    sumas_asig[asig_corta].append(prom_a)
                                elif f1 is not None:
                                    prom_a = redondear_nota(f1, 1)
                                    nf_final = f"{prom_a:.1f}".replace('.', ',')
                                    promedios_computables.append(prom_a)
                                    sumas_asig[asig_corta].append(prom_a)
                                elif f2 is not None:
                                    prom_a = redondear_nota(f2, 1)
                                    nf_final = f"{prom_a:.1f}".replace('.', ',')
                                    promedios_computables.append(prom_a)
                                    sumas_asig[asig_corta].append(prom_a)
                            except:
                                pass

                        promedios_asignaturas[asig_corta] = nf_final

                    # Promedio General Anual
                    if promedios_computables:
                        prom_gral_num = redondear_nota(sum(promedios_computables) / len(promedios_computables), 1)
                        prom_gral_str = f"{prom_gral_num:.1f}".replace('.', ',')
                    else:
                        prom_gral_num = 0.0
                        prom_gral_str = "—"

                    # Asistencia del Alumno considerando fecha de matrícula / ingreso oficial
                    asis_pre = calcular_asistencia_estudiante(r_al, df_asist, curso_preacta_sel, periodo='anual', config_inst=conf_inst_pre)
                    dias_clase_al = asis_pre["dias_clase"]
                    inasist_al = asis_pre["dias_inasist"]
                    pct_asist_num = asis_pre["pct_asist"]

                    # Conteo de rojas numéricas (< 4.0)
                    cant_rojas = sum(1 for p in promedios_computables if p < 4.0)

                    # Verificar si ya tenía datos guardados en Preacta
                    sit_guardada = None
                    obs_guardada = ""
                    if not df_preacta_existente.empty and 'RUT_NORM' in df_preacta_existente.columns:
                        coincid = df_preacta_existente[
                            (df_preacta_existente['RUT_NORM'] == r_norm) &
                            (df_preacta_existente.get('Año_STR', '') == str(anio_preacta_sel).strip())
                        ]
                        if not coincid.empty:
                            row_p = coincid.iloc[-1]
                            sit_guardada = str(row_p.get('Situacion_Final', '')).strip()
                            obs_guardada = str(row_p.get('Observaciones', '')).strip()

                    # Verificar si el usuario modificó manualmente en la sesión actual
                    k_mod = f"preacta_mod_{curso_preacta_sel}_{r_norm}"
                    if k_mod in st.session_state:
                        sit_base = st.session_state[k_mod].get("situacion", "Promovido(a)")
                        obs_base = st.session_state[k_mod].get("observaciones", "")
                    elif sit_guardada:
                        sit_base = sit_guardada
                        obs_base = obs_guardada
                    else:
                        sit_base = "Promovido(a)"
                        obs_base = ""

                    filas_matriz.append({
                        "lista": n_lista,
                        "rut": r_limpio,
                        "rut_norm": r_norm,
                        "nombre": nom_al,
                        "es_retirado": False,
                        "fecha_baja": "",
                        "promedios_asig": promedios_asignaturas,
                        "prom_gral_num": prom_gral_num,
                        "prom_gral_str": prom_gral_str,
                        "pct_asist": pct_asist_num,
                        "rojas": cant_rojas,
                        "situacion": sit_base,
                        "observaciones": obs_base
                    })

                # Métricas superiores resumen del curso (calculadas sobre estudiantes activos)
                total_al = len(filas_matriz)
                total_retirados = sum(1 for f in filas_matriz if f['es_retirado'])
                alumnos_activos = [f for f in filas_matriz if not f['es_retirado']]
                total_activos = len(alumnos_activos)
                total_promovidos = sum(1 for f in alumnos_activos if f['situacion'] == "Promovido(a)")
                total_reprobados = total_activos - total_promovidos
                proms_validos = [f['prom_gral_num'] for f in alumnos_activos if f['prom_gral_num'] > 0]
                prom_curso_gral = redondear_nota(sum(proms_validos) / len(proms_validos), 1) if proms_validos else 0.0
                prom_curso_str = f"{prom_curso_gral:.1f}".replace('.', ',') if prom_curso_gral > 0 else "—"
                pct_promovidos = round(total_promovidos / total_activos * 100, 1) if total_activos else 100
                fecha_emision_str = datetime.date.today().strftime('%d/%m/%Y')

                # (Las métricas y el botón de imprimir se despliegan en la cabecera de la pestaña oficial)


                # Construir Tabla Oficial en HTML para pantalla:
                # - Los nombres se muestran completos sin cortarse y sin que el usuario deba estirar celdas.
                # - Las notas menores a 4.0 aparecen en texto rojo en negrita (#dc2626) con fondo suave (#fff1f2).
                # - Los retirados se destacan con franja roja institucional.
                filas_html_pantalla = ""
                for f in filas_matriz:
                    if f["es_retirado"]:
                        celdas_ret = "".join(["<td style='text-align:center;padding:5px 2px;color:#cbd5e1;border:1px solid #e2e8f0;'>—</td>" for _ in asigs_catalogo])
                        filas_html_pantalla += f"""
                        <tr style='background-color:#fef2f2;border-left:4px solid #ef4444;'>
                            <td style='text-align:center;font-weight:700;color:#991b1b;padding:5px 4px;border:1px solid #fecaca;'>{f['lista']}</td>
                            <td style='padding:5px 8px;font-weight:700;color:#991b1b;white-space:nowrap;border:1px solid #fecaca;'>
                                {f['nombre']} <span style='background:#fee2e2;color:#b91c1c;border:1px solid #f87171;font-size:0.68rem;padding:1px 6px;border-radius:4px;margin-left:6px;font-weight:700;'>RETIRADO</span>
                            </td>
                            {celdas_ret}
                            <td style='text-align:center;color:#cbd5e1;font-weight:bold;border:1px solid #fecaca;'>—</td>
                            <td style='text-align:center;color:#cbd5e1;border:1px solid #fecaca;'>—</td>
                            <td style='text-align:center;padding:5px 4px;border:1px solid #fecaca;'><span style='background:#fee2e2;color:#dc2626;font-weight:800;padding:2px 8px;border-radius:4px;font-size:0.75rem;'>RETIRADO</span></td>
                            <td style='padding:5px 10px;font-size:0.75rem;color:#b91c1c;border:1px solid #fecaca;min-width:240px;white-space:normal;word-break:break-word;line-height:1.3;'>{f['observaciones']}</td>
                        </tr>
                        """
                    else:
                        celdas_asig_p = ""
                        for _, asig_corta, _ in asigs_catalogo:
                            val = f["promedios_asig"].get(asig_corta, "")
                            es_roja = False
                            try:
                                if float(str(val).replace(',', '.')) < 4.0:
                                    es_roja = True
                            except:
                                pass
                            if es_roja:
                                celdas_asig_p += f"<td style='text-align:center;padding:5px 3px;color:#dc2626;font-weight:800;background:#fff1f2;border:1px solid #e2e8f0;'>{val}</td>"
                            elif val:
                                celdas_asig_p += f"<td style='text-align:center;padding:5px 3px;color:#1e293b;border:1px solid #e2e8f0;'>{val}</td>"
                            else:
                                celdas_asig_p += f"<td style='text-align:center;padding:5px 3px;color:#cbd5e1;border:1px solid #e2e8f0;'>—</td>"

                        color_prom_gen = "#dc2626" if f["prom_gral_num"] > 0 and f["prom_gral_num"] < 4.0 else "#008F39"
                        badge_sit = (
                            "<span style='background:#dcfce7;color:#15803d;font-weight:700;padding:2px 8px;border-radius:4px;font-size:0.75rem;'>✓ Promovido(a)</span>"
                            if f["situacion"] == "Promovido(a)" else
                            "<span style='background:#fee2e2;color:#b91c1c;font-weight:700;padding:2px 8px;border-radius:4px;font-size:0.75rem;'>✗ Reprobado(a)</span>"
                        )
                        filas_html_pantalla += f"""
                        <tr style='border-bottom:1px solid #f1f5f9;'>
                            <td style='text-align:center;color:#64748b;padding:5px 4px;border:1px solid #e2e8f0;'>{f['lista']}</td>
                            <td style='padding:5px 8px;font-weight:600;color:#0f172a;white-space:nowrap;border:1px solid #e2e8f0;'>{f['nombre']}</td>
                            {celdas_asig_p}
                            <td style='text-align:center;font-weight:800;color:{color_prom_gen};background:#f8fafc;padding:5px 4px;border:1px solid #e2e8f0;'>{f['prom_gral_str']}</td>
                            <td style='text-align:center;color:#475569;background:#f8fafc;padding:5px 4px;border:1px solid #e2e8f0;'>{f['pct_asist']}%</td>
                            <td style='text-align:center;padding:5px 4px;border:1px solid #e2e8f0;'>{badge_sit}</td>
                            <td style='padding:5px 10px;font-size:0.75rem;color:#475569;border:1px solid #e2e8f0;min-width:240px;white-space:normal;word-break:break-word;line-height:1.3;'>{f['observaciones']}</td>
                        </tr>
                        """

                celdas_prom_pie = ""
                for _, asig_corta, _ in asigs_catalogo:
                    arr = sumas_asig[asig_corta]
                    prom_c = f"{redondear_nota(sum(arr)/len(arr)):.1f}".replace('.', ',') if arr else "—"
                    celdas_prom_pie += f"<th style='text-align:center;font-weight:800;color:#1e293b;padding:5px 3px;border:1px solid #cbd5e1;'>{prom_c}</th>"

                headers_asig_th = "".join([f"<th style='padding:6px 3px;text-align:center;border:1px solid #cbd5e1;font-size:0.75rem;' title='{asig_full}'>{abrev}</th>" for asig_full, _, abrev in asigs_catalogo])

                tabla_pantalla_html = f"""
                <div style='width:100%;overflow-x:auto;border:1px solid #cbd5e1;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.05);background:#ffffff;margin:8px 0 12px 0;'>
                <table style='width:100%;min-width:1300px;border-collapse:collapse;font-size:0.78rem;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'>
                    <thead>
                        <tr style='background:#f1f5f9;color:#0f172a;'>
                            <th style='padding:6px 4px;width:28px;text-align:center;border:1px solid #cbd5e1;'>N°</th>
                            <th style='padding:6px 8px;text-align:left;border:1px solid #cbd5e1;white-space:nowrap;'>Estudiante</th>
                            {headers_asig_th}
                            <th style='padding:6px 4px;width:42px;text-align:center;border:1px solid #cbd5e1;background:#e2e8f0;font-weight:800;'>Prom.</th>
                            <th style='padding:6px 4px;width:44px;text-align:center;border:1px solid #cbd5e1;background:#e2e8f0;'>% Asis</th>
                            <th style='padding:6px 6px;width:115px;text-align:center;border:1px solid #cbd5e1;white-space:nowrap;'>Situación Final</th>
                            <th style='padding:6px 10px;text-align:left;border:1px solid #cbd5e1;min-width:240px;white-space:nowrap;'>Observaciones / Decretos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_html_pantalla}
                    </tbody>
                    <tfoot>
                        <tr style='background:#f8fafc;border-top:2px solid #cbd5e1;'>
                            <th colspan='2' style='text-align:right;padding:6px 8px;border:1px solid #cbd5e1;font-weight:700;color:#334155;'>PROMEDIO CURSO:</th>
                            {celdas_prom_pie}
                            <th style='text-align:center;font-weight:900;color:#008F39;padding:6px 4px;border:1px solid #cbd5e1;background:#e2e8f0;'>{prom_curso_str}</th>
                            <th colspan='3' style='text-align:left;padding:6px 10px;border:1px solid #cbd5e1;font-size:0.73rem;color:#64748b;white-space:nowrap;'>Decreto Supremo N° 67/2018 Mineduc</th>
                        </tr>
                    </tfoot>
                </table>
                </div>
                """

                # Renderizar tabla limpia y adaptativa (eliminando saltos de línea con sangría para que Markdown no lo interprete como código preformateado)
                tabla_pantalla_html_limpia = re.sub(r'\n\s*', ' ', tabla_pantalla_html).strip()


                # Construir HTML oficial para impresión apaisada (Landscape)
                # Título exacto: Preacta de Calificaciones
                # Comuna dinámica de configuración: Mulchén
                # Firmas: Profesor(a) Jefe (nombre desde asignaciones) y Director (con firma gráfica b64)
                filas_html_print = ""
                for f in filas_matriz:
                    if f["es_retirado"]:
                        celdas_asig_ret = "".join(["<td style='text-align:center;padding:3px;color:#94a3b8;'>—</td>" for _ in asigs_catalogo])
                        filas_html_print += f"""
                        <tr style='background-color:#fee2e2;color:#991b1b;'>
                            <td style='text-align:center;padding:3px;font-weight:bold;'>{f['lista']}</td>
                            <td style='padding:3px;font-family:monospace;font-size:8pt;'>{f['rut']}</td>
                            <td style='padding:3px;font-size:8.5pt;font-weight:bold;'>{f['nombre']}</td>
                            {celdas_asig_ret}
                            <td style='text-align:center;font-weight:bold;padding:3px;'>—</td>
                            <td style='text-align:center;padding:3px;'>—</td>
                            <td style='text-align:center;font-weight:bold;color:#dc2626;padding:3px;'>RETIRADO</td>
                            <td style='padding:3px;font-size:7.5pt;color:#b91c1c;'>{f['observaciones']}</td>
                        </tr>
                        """
                    else:
                        celdas_asig_print = ""
                        for _, asig_corta, _ in asigs_catalogo:
                            val = f["promedios_asig"].get(asig_corta, "")
                            es_roja = False
                            try:
                                if float(str(val).replace(',', '.')) < 4.0: es_roja = True
                            except: pass
                            st_roja = "color:#dc2626;font-weight:bold;" if es_roja else ""
                            celdas_asig_print += f"<td style='text-align:center;padding:3px;{st_roja}'>{val if val else '—'}</td>"

                        col_sit = "#166534" if f["situacion"] == "Promovido(a)" else "#991b1b"
                        filas_html_print += f"""
                        <tr>
                            <td style='text-align:center;padding:3px;'>{f['lista']}</td>
                            <td style='padding:3px;font-family:monospace;font-size:8pt;'>{f['rut']}</td>
                            <td style='padding:3px;font-size:8.5pt;'>{f['nombre']}</td>
                            {celdas_asig_print}
                            <td style='text-align:center;font-weight:bold;padding:3px;'>{f['prom_gral_str']}</td>
                            <td style='text-align:center;padding:3px;'>{f['pct_asist']}%</td>
                            <td style='text-align:center;font-weight:bold;color:{col_sit};padding:3px;'>{f['situacion']}</td>
                            <td style='padding:3px;font-size:7.5pt;'>{f['observaciones']}</td>
                        </tr>
                        """

                celdas_prom_pie_print = ""
                for _, asig_corta, _ in asigs_catalogo:
                    arr = sumas_asig[asig_corta]
                    prom_c = f"{redondear_nota(sum(arr)/len(arr)):.1f}".replace('.', ',') if arr else "—"
                    celdas_prom_pie_print += f"<td style='text-align:center;font-weight:bold;padding:3px;'>{prom_c}</td>"

                headers_asig_print = "".join([f"<th style='padding:3px;font-size:7.5pt;'>{abrev}</th>" for _, _, abrev in asigs_catalogo])
                img_tag_print = f'<img src="data:image/png;base64,{insignia_b64}" style="height:42px;width:auto;" />' if insignia_b64 else ''

                # Estampa de firma del director si existe en base64 en configuración
                firma_director_html = (
                    f'<img src="data:image/png;base64,{firma_director_b64}" style="max-height:50px;display:block;margin:0 auto -8px auto;" />'
                    if firma_director_b64 else '<div style="height:45px;"></div>'
                )

                # Token único para que cada clic en imprimir recargue limpiamente el diálogo del navegador
                print_token = int(time.time() * 1000)

                html_doc_impresion = f"""
                <!DOCTYPE html>
                <!-- print_token_{print_token} -->
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Preacta de Calificaciones - {curso_preacta_sel} ({anio_preacta_sel})</title>
                    <style>
                        @page {{
                            size: letter landscape;
                            margin: 8mm 10mm;
                        }}
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                            font-size: 8pt;
                            color: #111827;
                            margin: 0;
                            padding: 0;
                            -webkit-print-color-adjust: exact;
                            print-color-adjust: exact;
                        }}
                        table {{
                            width: 100%;
                            border-collapse: collapse;
                            margin-top: 6px;
                        }}
                        th, td {{
                            border: 1px solid #94a3b8;
                            font-size: 8pt;
                        }}
                        th {{
                            background-color: #f1f5f9 !important;
                            color: #0f172a;
                            font-weight: 700;
                        }}
                        .header-box {{
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            border-bottom: 2px solid #008F39;
                            padding-bottom: 4px;
                            margin-bottom: 6px;
                        }}
                        .firmas-container {{
                            display: flex;
                            justify-content: space-around;
                            margin-top: 35px;
                            page-break-inside: avoid;
                        }}
                        .firma-box {{
                            text-align: center;
                            width: 35%;
                            font-size: 8pt;
                        }}
                    </style>
                </head>
                <body>
                    <div class="header-box">
                        <div style="display:flex;align-items:center;gap:10px;">
                            {img_tag_print}
                            <div>
                                <div style="font-weight:800;font-size:10pt;color:#008F39;">{nombre_colegio}</div>
                                <div style="font-size:7.5pt;color:#475569;">RBD: {rbd_colegio} | Comuna: {comuna_colegio}</div>
                            </div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-weight:900;font-size:13pt;letter-spacing:0.5px;">Preacta de Calificaciones</div>
                            <div style="font-size:8.5pt;color:#334155;">AÑO ESCOLAR {anio_preacta_sel} — CURSO: {curso_preacta_sel}</div>
                        </div>
                        <div style="text-align:right;font-size:7.5pt;color:#475569;">
                            Fecha de Emisión: {fecha_emision_str}<br>
                            Matrícula: {total_activos} Activos {f'+ {total_retirados} Retirados' if total_retirados else ''} | Promovidos: {total_promovidos} ({pct_promovidos}%)
                        </div>
                    </div>

                    <table>
                        <thead>
                            <tr>
                                <th style="width:25px;padding:3px;">N°</th>
                                <th style="width:75px;padding:3px;">RUN</th>
                                <th style="padding:3px;text-align:left;">Apellidos y Nombres</th>
                                {headers_asig_print}
                                <th style="width:38px;padding:3px;">Prom</th>
                                <th style="width:38px;padding:3px;">% Asis</th>
                                <th style="width:80px;padding:3px;">Situación</th>
                                <th style="width:180px;padding:3px;white-space:nowrap;">Observaciones / Decretos</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_html_print}
                            <tr style="background-color:#f8fafc;font-weight:bold;">
                                <td colspan="3" style="text-align:right;padding:3px;font-size:8pt;">PROMEDIO CURSO:</td>
                                {celdas_prom_pie_print}
                                <td style="text-align:center;padding:3px;font-size:8.5pt;">{prom_curso_str}</td>
                                <td colspan="3" style="padding:3px;font-size:7.5pt;color:#64748b;">Decreto Supremo N° 67/2018 Mineduc</td>
                            </tr>
                        </tbody>
                    </table>

                    <div class="firmas-container">
                        <div class="firma-box">
                            <div style="height:45px;"></div>
                            <div style="border-top:1px solid #475569;padding-top:4px;">
                                <b>{profesor_jefe_nombre}</b><br>
                                Profesor(a) Jefe
                            </div>
                        </div>
                        <div class="firma-box">
                            {firma_director_html}
                            <div style="border-top:1px solid #475569;padding-top:4px;">
                                <b>{director_colegio}</b><br>
                                Director del Establecimiento
                            </div>
                        </div>
                    </div>

                    <script>
                        setTimeout(function() {{
                            window.focus();
                            window.print();
                        }}, 150);
                    </script>
                </body>
                </html>
                """

                # Pestañas principales de navegación del módulo Preacta
                tab_preacta, tab_decretos, tab_sige = st.tabs(["📄 Preacta Oficial", "⚖️ Decretos y Observaciones", "💾 Archivos Magnéticos SIGE"])

                with tab_preacta:
                    col_met, col_btn = st.columns([3.8, 1.2])
                    with col_met:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Estudiantes Matriculados", f"{total_activos} Activos", delta=f"{total_retirados} Retirado(s)" if total_retirados > 0 else None, delta_color="inverse")
                        m2.metric("Promedio General Curso", prom_curso_str)
                        m3.metric("Estudiantes Promovidos(as)", f"{total_promovidos} / {total_activos}", delta=f"{pct_promovidos}%")
                    with col_btn:
                        st.write("")
                        st.write("")
                        btn_imprimir = st.button("🖨️ Imprimir Preacta", type="primary", use_container_width=True, key="btn_print_preacta")
                        if btn_imprimir:
                            st.components.v1.html(html_doc_impresion, height=0, scrolling=False)
                            st.toast("🖨️ Abriendo cuadro de impresión oficial...", icon="📄")

                    st.markdown("<hr style='margin:10px 0 12px 0;'>", unsafe_allow_html=True)
                    st.markdown(tabla_pantalla_html_limpia, unsafe_allow_html=True)

                with tab_decretos:
                    st.markdown("#### ⚖️ Gestión de Situación Final y Decretos de Promoción")
                    st.caption("Ajusta la condición final de estudiantes (promovido/reprobado) o registra decretos normativos (ej: Decreto Supremo N° 67/2018) para ser incluidos en el acta oficial.")

                    alumnos_activos_dict = {f"{f['lista']}. {f['nombre']}": f for f in filas_matriz if not f['es_retirado']}
                    if not alumnos_activos_dict:
                        st.info("No hay estudiantes activos en este curso.")
                    else:
                        c_ed1, c_ed2 = st.columns([1.4, 1.0])
                        with c_ed1:
                            nom_sel = st.selectbox("Selecciona Estudiante:", list(alumnos_activos_dict.keys()), key=f"tab_sel_al_{curso_preacta_sel}")
                            obj_sel = alumnos_activos_dict[nom_sel]

                            st.markdown(f"""
                            <div style='background:#f8fafc;padding:12px 14px;border-radius:8px;border:1px solid #e2e8f0;margin:10px 0;'>
                                <div style='font-weight:700;font-size:1.05rem;color:#0f172a;'>{obj_sel['nombre']}</div>
                                <div style='color:#475569;font-size:0.85rem;margin-top:4px;'>
                                    <b>RUN:</b> {obj_sel['rut']} &nbsp;|&nbsp; 
                                    <b>Promedio General:</b> <span style='color:#0284c7;font-weight:700;'>{obj_sel['prom_gral_str']}</span> &nbsp;|&nbsp; 
                                    <b>Asistencia:</b> <span style='font-weight:700;'>{obj_sel['pct_asist']}%</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            idx_rad = 0 if obj_sel.get("situacion", "Promovido(a)") == "Promovido(a)" else 1
                            nueva_sit = st.radio("Situación Final de Promoción:", ["Promovido(a)", "Reprobado(a)"], index=idx_rad, horizontal=True, key=f"tab_radio_sit_{obj_sel['rut_norm']}")
                            obs_val = st.text_area(
                                "Observaciones / Decretos aplicados:",
                                value=obj_sel["observaciones"],
                                placeholder="Ej: Promovido(a) por Consejo de Profesores según Decreto Supremo N° 67/2018 Art. 11...",
                                height=90,
                                key=f"tab_txt_obs_{obj_sel['rut_norm']}"
                            )

                            c_b1, c_b2 = st.columns([1.5, 1.0])
                            with c_b1:
                                if st.button("💾 Guardar Cambios del Estudiante", type="primary", use_container_width=True, key=f"btn_save_tab_{obj_sel['rut_norm']}"):
                                    st.session_state[f"preacta_mod_{curso_preacta_sel}_{obj_sel['rut_norm']}"] = {
                                        "situacion": nueva_sit,
                                        "observaciones": obs_val.strip()
                                    }
                                    st.toast(f"✅ Situación de {obj_sel['nombre']} actualizada.", icon="✨")
                                    st.rerun()
                            with c_b2:
                                k_mod = f"preacta_mod_{curso_preacta_sel}_{obj_sel['rut_norm']}"
                                if k_mod in st.session_state:
                                    if st.button("Restablecer", use_container_width=True, key=f"btn_reset_tab_{obj_sel['rut_norm']}"):
                                        del st.session_state[k_mod]
                                        st.toast(f"Valores de {obj_sel['nombre']} restablecidos por defecto.", icon="🔄")
                                        st.rerun()

                        with c_ed2:
                            st.markdown("##### 📋 Resumen de Excepciones del Curso")
                            casos_especiales = [f for f in filas_matriz if f['es_retirado'] or f['situacion'] != 'Promovido(a)' or f['observaciones']]
                            if casos_especiales:
                                for c in casos_especiales:
                                    es_rojo = c['es_retirado'] or c['situacion'] == 'Reprobado(a)'
                                    badge_col = "#dc2626" if es_rojo else "#0284c7"
                                    bg_col = "#fef2f2" if es_rojo else "#f0f9ff"
                                    st.markdown(f"""
                                    <div style='background:{bg_col};padding:10px 12px;border-radius:6px;border-left:4px solid {badge_col};margin-bottom:8px;font-size:0.83rem;'>
                                        <div style='font-weight:700;color:#1e293b;'>{c['lista']}. {c['nombre']}</div>
                                        <div style='color:#475569;font-size:0.78rem;margin-top:2px;'>Condición: <b style='color:{badge_col};'>{c['situacion']}</b></div>
                                        {f"<div style='color:#334155;font-size:0.75rem;margin-top:3px;'><i>{c['observaciones']}</i></div>" if c['observaciones'] else ""}
                                    </div>
                                    """, unsafe_allow_html=True)
                            else:
                                st.info("No hay excepciones ni observaciones registradas en este curso (todos los estudiantes están promovidos de forma regular).")

                with tab_sige:
                    st.markdown("#### 💾 Generación de Archivos Magnéticos Oficiales para SIGE (Mineduc)")

                    c_cur_sg1, c_cur_sg2 = st.columns([2.5, 1.2])
                    with c_cur_sg1:
                        idx_cur_sg = cursos_disp.index(curso_preacta_sel) if curso_preacta_sel in cursos_disp else 0
                        curso_sige_picker = st.selectbox(
                            "📚 Seleccionar Curso a Generar:",
                            cursos_disp,
                            index=idx_cur_sg,
                            key="sige_picker_course"
                        )
                        if curso_sige_picker != curso_preacta_sel:
                            st.session_state["sel_curso_preacta"] = curso_sige_picker
                            st.rerun()

                    with c_cur_sg2:
                        st.write("")
                        st.write("")
                        chk_excluir_ret = st.checkbox(
                            "Excluir estudiantes retirados",
                            value=True,
                            key=f"sige_excl_ret_{curso_preacta_sel}"
                        )

                    # Parámetros institucionales fijos para SIGE
                    rbd_sige = "4410"
                    dv_sige = "5"
                    if "-" in str(rbd_colegio):
                        p_rbd = str(rbd_colegio).split("-")
                        rbd_sige = p_rbd[0].strip()
                        dv_sige = p_rbd[1].strip()
                    elif rbd_colegio:
                        rbd_sige = str(rbd_colegio).strip()

                    cod_ens_sige = "110"
                    anio_sige = int(anio_preacta_sel)

                    # Extraer grado y letra automáticamente del curso seleccionado
                    m_g = re.search(r'(\d+)', str(curso_preacta_sel))
                    grado_sige = m_g.group(1) if m_g else "1"
                    m_l = re.search(r'\b([A-Za-z])\b', str(curso_preacta_sel))
                    if not m_l:
                        m_l = re.search(r'([A-Da-d])\s*$', str(curso_preacta_sel))
                    letra_sige = m_l.group(1).upper() if m_l else "A"

                    # Filtrar lista de estudiantes según la opción de retirados
                    estudiantes_sige = [f for f in filas_matriz if not (chk_excluir_ret and f['es_retirado'])]

                    if not estudiantes_sige:
                        st.warning(f"No hay estudiantes para procesar en {curso_preacta_sel}.")
                    else:
                        # Mapeo oficial de las 12 asignaturas oficiales a códigos SIGE (Orientación fija en 413)
                        mapa_sige_asigs = {
                            "Lenguaje": 28,
                            "Inglés": 6,
                            "Matemática": 9845,
                            "Historia": 19,
                            "Ciencias": 2280,
                            "Tecnología": 14,
                            "Artes": 5,
                            "Música": 288,
                            "Ed. Física": 517,
                            "Rel. Evang.": 22,
                            "Rel. Cat.": 22,
                            "Orientación": 413
                        }

                        def _descomponer_rut_sige(rut_raw):
                            limpio = str(rut_raw).replace('.', '').replace(' ', '').strip().upper()
                            if '-' in limpio:
                                partes = limpio.split('-')
                                return partes[0].strip(), partes[1].strip()
                            elif len(limpio) >= 2:
                                return limpio[:-1], limpio[-1]
                            return limpio, ""

                        # 1. Generar contenido ARCHIVO TIPO 4 (Calificaciones por Asignatura)
                        lineas_tipo_4 = []
                        total_notas_t4 = 0

                        for al in estudiantes_sige:
                            r_cuerpo, r_dv = _descomponer_rut_sige(al['rut'])
                            if not r_cuerpo:
                                continue

                            for _, asig_corta, _ in asigs_catalogo:
                                val_nota = al["promedios_asig"].get(asig_corta, "")
                                if not val_nota or str(val_nota).strip() in ["—", "None", "nan", ""]:
                                    continue

                                val_str = str(val_nota).strip()
                                cod_asig_num = mapa_sige_asigs.get(asig_corta)
                                if not cod_asig_num:
                                    continue

                                val_upper = val_str.upper()
                                if val_upper in ["MB", "B", "S", "I"]:
                                    nota_num_str = ""
                                    nota_con_str = val_upper
                                else:
                                    n_clean = val_str.replace(',', '.')
                                    try:
                                        f_val = float(n_clean)
                                        nota_num_str = f"{f_val:.1f}"
                                    except:
                                        nota_num_str = n_clean
                                    nota_con_str = ""

                                linea_t4 = f"4\t{rbd_sige}\t{dv_sige}\t{cod_ens_sige}\t{grado_sige}\t{letra_sige}\t{anio_sige}\t{r_cuerpo}\t{r_dv}\t{cod_ens_sige}\t{cod_ens_sige}\t{cod_asig_num}\t{nota_num_str}\t{nota_con_str}\t"
                                lineas_tipo_4.append(linea_t4)
                                total_notas_t4 += 1

                        contenido_tipo_4 = "\r\n".join(lineas_tipo_4) + "\r\n" if lineas_tipo_4 else ""

                        # 2. Generar contenido ARCHIVO TIPO 5 (Situación Final y Promoción)
                        lineas_tipo_5 = []
                        for al in estudiantes_sige:
                            r_cuerpo, r_dv = _descomponer_rut_sige(al['rut'])
                            if not r_cuerpo:
                                continue

                            if al['es_retirado']:
                                prom_str_sige = ""
                                pct_asis_sige = "0"
                                obs_sige = al['observaciones'].strip()
                                sit_sige = "Y"
                                causal_sige = ""
                            else:
                                prom_num = al.get('prom_gral_num', 0.0)
                                prom_str_sige = f"{prom_num:.1f}" if prom_num > 0 else ""
                                try:
                                    pct_asis_sige = str(int(round(float(al.get('pct_asist', 0)))))
                                except:
                                    pct_asis_sige = "0"

                                obs_sige = al.get('observaciones', '').strip()
                                sit_base = al.get('situacion', 'Promovido(a)')
                                if sit_base in ['Promovido(a)', 'P']:
                                    sit_sige = "P"
                                    causal_sige = "1"
                                else:
                                    sit_sige = "R"
                                    causal_sige = "2" if float(pct_asis_sige) < 85 and prom_num >= 4.0 else "1"

                            linea_t5 = f"5\t{rbd_sige}\t{dv_sige}\t{cod_ens_sige}\t{grado_sige}\t{letra_sige}\t{anio_sige}\t{r_cuerpo}\t{r_dv}\t{prom_str_sige}\t{pct_asis_sige}\t{obs_sige}\t{sit_sige}\t{causal_sige}"
                            lineas_tipo_5.append(linea_t5)

                        contenido_tipo_5 = "\r\n".join(lineas_tipo_5) + "\r\n" if lineas_tipo_5 else ""

                        st.markdown("<hr style='margin:10px 0 16px 0;'>", unsafe_allow_html=True)

                        col_arc_t4, col_arc_t5 = st.columns(2)

                        with col_arc_t4:
                            st.markdown(f"""
                            <div style='background:#f0fdf4;padding:14px;border-radius:8px;border:1px solid #bbf7d0;'>
                                <div style='display:flex;align-items:center;gap:8px;'>
                                    <span style='font-size:1.4rem;'>📊</span>
                                    <div>
                                        <b style='color:#166534;font-size:1.02rem;'>Archivo Tipo 4 (.txt)</b>
                                        <div style='font-size:0.8rem;color:#15803d;'>Calificaciones Anuales — {curso_preacta_sel}</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.write("")
                            st.metric("Registros de Calificaciones", f"{total_notas_t4} notas generadas")
                            st.download_button(
                                label="📥 Descargar Archivo Tipo 4 (.txt)",
                                data=contenido_tipo_4.encode("latin1", errors="replace"),
                                file_name=f"SIGE_Tipo4_Calificaciones_{anio_sige}_{grado_sige}{letra_sige}.txt",
                                mime="text/plain",
                                type="primary",
                                use_container_width=True,
                                key=f"btn_dl_t4_{curso_preacta_sel}"
                            )

                        with col_arc_t5:
                            st.markdown(f"""
                            <div style='background:#eff6ff;padding:14px;border-radius:8px;border:1px solid #bfdbfe;'>
                                <div style='display:flex;align-items:center;gap:8px;'>
                                    <span style='font-size:1.4rem;'>🎓</span>
                                    <div>
                                        <b style='color:#1e40af;font-size:1.02rem;'>Archivo Tipo 5 (.txt)</b>
                                        <div style='font-size:0.8rem;color:#1d4ed8;'>Situación Final y Promoción — {curso_preacta_sel}</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.write("")
                            st.metric("Estudiantes Procesados", f"{len(lineas_tipo_5)} alumnos incluidos")
                            st.download_button(
                                label="📥 Descargar Archivo Tipo 5 (.txt)",
                                data=contenido_tipo_5.encode("latin1", errors="replace"),
                                file_name=f"SIGE_Tipo5_Promocion_{anio_sige}_{grado_sige}{letra_sige}.txt",
                                mime="text/plain",
                                type="primary",
                                use_container_width=True,
                                key=f"btn_dl_t5_{curso_preacta_sel}"
                            )


        except Exception as e:
            st.error(f"Error al cargar módulo de Preacta: {e}")
            import traceback; st.code(traceback.format_exc())


elif st.session_state.current_module == 'informes':

    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>📑 Emisión de Informes de Notas</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_inf", use_container_width=True):
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 12px 0;'>", unsafe_allow_html=True)

    sheet_alumnos, _, sheet_notas, _, sheet_asignaciones = get_sheets()
    sheet_asistencia = get_asistencia_sheet()
    sheet_config = get_config_sheet()
    sheet_preacta = get_preacta_sheet()
    sheet_cursos = get_cursos_sheet()

    if not sheet_alumnos or not sheet_notas:
        st.error("❌ Error de conexión con la base de datos.")
    else:
        try:
            # 1. Cargar Configuración del Establecimiento
            conf_data = {}
            if sheet_config:
                for r in sheet_config.get_all_records():
                    conf_data[str(r.get("Clave","")).strip()] = str(r.get("Valor","")).strip()

            nom_colegio = conf_data.get("nombre_colegio", "ESCUELA VILLA LAS PEÑAS")
            region_col  = conf_data.get("region", "BÍOBÍO")
            ciudad_col  = conf_data.get("ciudad", "Mulchén")
            rbd_col     = conf_data.get("rbd", "4410-5")
            director_col = conf_data.get("nombre_director", "RUBÉN MARCOS QUEZADA BALBOA")
            firma_b64   = conf_data.get("firma_director_b64", "")

            # Cargar insignia local institucional en Base64
            insignia_b64_html = ""
            for p_ins in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "insignia.png"), "insignia.png", "C:/SistemaEscolar/insignia.png"]:
                if os.path.exists(p_ins):
                    try:
                        with open(p_ins, "rb") as f_ins:
                            insignia_b64_html = base64.b64encode(f_ins.read()).decode('utf-8')
                        break
                    except Exception:
                        pass

            # 2. Cargar Cursos y Alumnos
            recs_al = sheet_alumnos.get_all_records()
            df_al_inf = pd.DataFrame(recs_al) if recs_al else pd.DataFrame()
            if not df_al_inf.empty: df_al_inf.columns = [str(c).strip() for c in df_al_inf.columns]

            col_c = next((c for c in df_al_inf.columns if 'curs' in c.lower()), 'Curso')
            col_n = next((c for c in df_al_inf.columns if 'nomb' in c.lower()), 'Nombre')
            col_r = next((c for c in df_al_inf.columns if 'rut' in c.lower()), 'RUT')
            col_o = next((c for c in df_al_inf.columns if any(x in c.lower() for x in ['list','orden','n°','nro'])), 'N° Lista')
            col_mat = next((c for c in df_al_inf.columns if 'matr' in c.lower() and 'fec' not in c.lower()), 'N° Matrícula')
            col_f_mat = next((c for c in df_al_inf.columns if 'matr' in c.lower() and ('fec' in c.lower() or 'date' in c.lower())), 'Fecha Matrícula')
            col_baja = next((c for c in df_al_inf.columns if 'baja' in c.lower() or 'retir' in c.lower()), 'Fecha Baja')
            col_f_ing = next((c for c in df_al_inf.columns if any(x in c.lower() for x in ['ingres', 'matric', 'matr_fec'])), None)

            conf_inst_inf = cargar_datos_configuracion_reportes()
            f_inicio_semestre_1_inf = conf_inst_inf.get("s1_ini", datetime.date(datetime.date.today().year, 3, 4))
            f_fin_semestre_1_inf    = conf_inst_inf.get("s1_fin", datetime.date(datetime.date.today().year, 6, 18))
            f_inicio_semestre_2_inf = conf_inst_inf.get("s2_ini", datetime.date(datetime.date.today().year, 7, 6))
            f_fin_semestre_2_inf    = conf_inst_inf.get("s2_fin", datetime.date(datetime.date.today().year, 12, 11))

            cursos_disp = obtener_cursos_oficiales_sistema()

            # Barra de selección
            c_sel1, c_sel2, c_sel3 = st.columns([2, 3, 2.8])
            with c_sel1:
                curso_inf_sel = st.selectbox("📚 Selecciona el Curso:", cursos_disp, key="sel_curso_informes")

            df_curso_inf = df_al_inf[df_al_inf[col_c].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, curso_inf_sel))].copy()
            if not df_curso_inf.empty:
                if col_o in df_curso_inf.columns:
                    df_curso_inf['_ord'] = pd.to_numeric(df_curso_inf[col_o], errors='coerce').fillna(999).astype(int)
                else:
                    df_curso_inf['_ord'] = 1
                df_curso_inf = df_curso_inf.sort_values(by=['_ord'])

            opciones_est = ["Todos los Alumnos del Curso"]
            map_est_inf = {}
            if not df_curso_inf.empty:
                for _, r in df_curso_inf.iterrows():
                    ret_tag = " (RETIRADO)" if col_baja in r and str(r[col_baja]).strip() not in ['', 'nan', 'None'] else ""
                    tag = f"{r[col_n]}{ret_tag}"
                    opciones_est.append(tag)
                    map_est_inf[tag] = r.to_dict()

            with c_sel2:
                alumno_inf_sel = st.selectbox("👤 Selecciona Estudiante:", opciones_est, key="sel_alumno_informes")

            with c_sel3:
                tipo_inf_sel = st.selectbox(
                    "📑 Tipo de Documento:",
                    [
                        "📜 Certificado de Alumno Regular",
                        "🟣 Informe Anual Completo (1° y 2° Semestre)",
                        "🔵 Informe de Notas - 1er Semestre",
                        "🟢 Informe de Notas - 2do Semestre",
                        "🎓 Certificado Anual de Estudios"
                    ],
                    key="sel_tipo_inf"
                )

            st.markdown("<hr style='margin:10px 0 14px 0;border-color:#edf2f7;'>", unsafe_allow_html=True)

            # Subtítulo para informes regulares
            if "Alumno Regular" in tipo_inf_sel:
                subtitulo_inf = "CERTIFICADO DE ALUMNO REGULAR"
            elif "1er Semestre" in tipo_inf_sel:
                subtitulo_inf = "INFORME DE NOTAS - 1ER SEMESTRE"
            elif "2do Semestre" in tipo_inf_sel:
                subtitulo_inf = "INFORME DE NOTAS - 2DO SEMESTRE"
            elif "Certificado Anual" in tipo_inf_sel:
                subtitulo_inf = "CERTIFICADO ANUAL DE ESTUDIOS"
            else:
                subtitulo_inf = "INFORME ANUAL DE CALIFICACIONES"

            # 3. Identificar Profesor Jefe del Curso
            prof_jefe_nombre = obtener_profesor_jefe_curso(curso_inf_sel, sheet_asignaciones)

            # 4. Cargar Notas
            df_notas_all = pd.DataFrame(sheet_notas.get_all_records()) if sheet_notas else pd.DataFrame()
            if not df_notas_all.empty:
                df_notas_all.columns = [str(c).strip() for c in df_notas_all.columns]
                col_r_n = next((c for c in df_notas_all.columns if 'rut' in c.lower()), 'RUT')
                col_c_n = next((c for c in df_notas_all.columns if 'curs' in c.lower()), 'Curso')
                col_a_n = next((c for c in df_notas_all.columns if 'asig' in c.lower()), 'Asignatura')
                col_s_n = next((c for c in df_notas_all.columns if 'sem' in c.lower()), 'Semestre')
                df_notas_all['RUT_NORM'] = df_notas_all[col_r_n].astype(str).str.replace('.','', regex=False).str.strip().str.lower()
            else:
                col_r_n, col_c_n, col_a_n, col_s_n = 'RUT', 'Curso', 'Asignatura', 'Semestre'

            # 5. Cargar Asistencia
            df_asist_all = pd.DataFrame(sheet_asistencia.get_all_records()) if sheet_asistencia else pd.DataFrame()
            if not df_asist_all.empty:
                df_asist_all.columns = [str(c).strip() for c in df_asist_all.columns]

            # Función generadora de HTML para un alumno
            def generar_html_informe_alumno(alumno_dict):
                r_alu = str(alumno_dict.get(col_r, '')).strip()
                r_alu_norm = r_alu.replace('.','').strip().lower()
                nom_alu = str(alumno_dict.get(col_n, '')).strip().upper()
                ord_alu = str(int(alumno_dict.get('_ord', 1)))

                # Fecha actual en formato chileno
                meses_es = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
                hoy = datetime.date.today()
                fecha_str = f"{ciudad_col.upper()}, {hoy.day} de {meses_es[hoy.month - 1]} de {hoy.year}"

                # Asignaturas oficiales
                asigs_oficiales = [
                    "Lengua y Literatura", "Idioma Extranjero Inglés", "Matemática",
                    "Historia, Geografía y Ciencias Sociales", "Ciencias Naturales",
                    "Tecnología", "Música", "Educación Física y Salud",
                    "Religión Evangélica", "Religión Católica", "Orientación", "Artes Visuales"
                ]

                # Filtrar notas del alumno
                df_al_notas = df_notas_all[df_notas_all['RUT_NORM'] == r_alu_norm] if not df_notas_all.empty else pd.DataFrame()

                # Construir filas de la tabla de notas
                filas_tabla_html = ""
                promedios_s1 = []
                promedios_s2 = []
                promedios_finales = []

                modo_s1_solo = "1er Semestre" in tipo_inf_sel
                modo_s2_solo = "2do Semestre" in tipo_inf_sel
                modo_anual   = not modo_s1_solo and not modo_s2_solo


                # Funciones auxiliares para coincidencia flexible y escala 10-70
                def match_asig_inf(nombre_bd, asig_cat_full):
                    nbd = str(nombre_bd).lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').strip()
                    ncat = str(asig_cat_full).lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').strip()
                    if nbd == ncat or nbd in ncat or ncat in nbd: return True
                    if 'matemat' in nbd and 'matemat' in ncat: return True
                    if ('lengua' in nbd or 'lenguaje' in nbd) and ('lengua' in ncat or 'lenguaje' in ncat): return True
                    if 'ingles' in nbd and 'ingles' in ncat: return True
                    if 'ciencias nat' in nbd and 'ciencias nat' in ncat: return True
                    if 'historia' in nbd and 'historia' in ncat: return True
                    if 'musica' in nbd and 'musica' in ncat: return True
                    if 'arte' in nbd and 'arte' in ncat: return True
                    if 'tecnol' in nbd and 'tecnol' in ncat: return True
                    if 'fisic' in nbd and 'fisic' in ncat: return True
                    if 'catolic' in nbd and 'catolic' in ncat: return True
                    if 'evangel' in nbd and 'evangel' in ncat: return True
                    if 'orientac' in nbd and 'orientac' in ncat: return True
                    return False

                def parsear_prom_inf(val_raw):
                    if val_raw is None or str(val_raw).strip() in ['', 'None', 'nan']: return None
                    try:
                        num = float(str(val_raw).replace(',', '.'))
                        if num > 10.0: num = float(redondear_nota(num / 10.0))
                        return num
                    except: return None

                for asig in asigs_oficiales:
                    asig_es_conceptual = any(k in asig.lower() for k in ['religi', 'orientac'])

                    # Semestre 1 (Hasta 10 notas disponibles en el sistema)
                    n_s1 = [""] * 10
                    p1_val = ""
                    if not df_al_notas.empty:
                        m_s1 = df_al_notas[df_al_notas[col_a_n].apply(lambda x: match_asig_inf(x, asig)) & df_al_notas[col_s_n].astype(str).str.contains('1')]
                        if not m_s1.empty:
                            row_s1 = m_s1.iloc[0]
                            for i in range(1, 11):
                                k_n = f"N{i}"
                                if k_n in row_s1 and str(row_s1[k_n]).strip() != "":
                                    val_ni = row_s1[k_n]
                                    if asig_es_conceptual:
                                        n_s1[i-1] = nota_a_concepto(val_ni)
                                    else:
                                        num_ni = parsear_prom_inf(val_ni)
                                        n_s1[i-1] = f"{num_ni:.1f}".replace('.', ',') if num_ni is not None else str(val_ni).strip()
                            p1_raw = row_s1.get("Promedio", "")
                            if asig_es_conceptual:
                                p1_val = nota_a_concepto(p1_raw)
                            else:
                                num_p1 = parsear_prom_inf(p1_raw)
                                if num_p1 is not None:
                                    p1_val = f"{redondear_nota(num_p1):.1f}".replace('.', ',')
                                    promedios_s1.append(float(redondear_nota(num_p1)))

                    # Semestre 2 (Hasta 10 notas disponibles en el sistema)
                    n_s2 = [""] * 10
                    p2_val = ""
                    if not df_al_notas.empty:
                        m_s2 = df_al_notas[df_al_notas[col_a_n].apply(lambda x: match_asig_inf(x, asig)) & df_al_notas[col_s_n].astype(str).str.contains('2')]
                        if not m_s2.empty:
                            row_s2 = m_s2.iloc[0]
                            for i in range(1, 11):
                                k_n = f"N{i}"
                                if k_n in row_s2 and str(row_s2[k_n]).strip() != "":
                                    val_ni = row_s2[k_n]
                                    if asig_es_conceptual:
                                        n_s2[i-1] = nota_a_concepto(val_ni)
                                    else:
                                        num_ni = parsear_prom_inf(val_ni)
                                        n_s2[i-1] = f"{num_ni:.1f}".replace('.', ',') if num_ni is not None else str(val_ni).strip()
                            p2_raw = row_s2.get("Promedio", "")
                            if asig_es_conceptual:
                                p2_val = nota_a_concepto(p2_raw)
                            else:
                                num_p2 = parsear_prom_inf(p2_raw)
                                if num_p2 is not None:
                                    p2_val = f"{redondear_nota(num_p2):.1f}".replace('.', ',')
                                    promedios_s2.append(float(redondear_nota(num_p2)))

                    # Nota Final Asignatura
                    nf_val = ""
                    if asig_es_conceptual:
                        # Para asignaturas conceptuales se toma el concepto del S2 si existe, sino del S1 (sin computar en promedio general)
                        nf_val = p2_val if p2_val else p1_val
                    else:
                        try:
                            p1_flt = float(p1_val.replace(',', '.')) if p1_val else None
                            p2_flt = float(p2_val.replace(',', '.')) if p2_val else None
                            if p1_flt and p2_flt:
                                nf_calc = float(redondear_nota((p1_flt + p2_flt) / 2))
                                nf_val = f"{nf_calc:.1f}".replace('.', ',')
                                promedios_finales.append(nf_calc)
                            elif p1_flt:
                                nf_val = f"{p1_flt:.1f}".replace('.', ',')
                                promedios_finales.append(p1_flt)
                        except:
                            pass

                    # Función para dar formato rojo a notas deficientes (< 4,0 o concepto 'I')
                    def _formato_celda_nota(v, base_cls="nota-cell"):
                        s = str(v).strip()
                        if not s:
                            return f"<td class='{base_cls}'></td>"
                        try:
                            num = float(s.replace(',', '.'))
                            if num < 4.0:
                                return f"<td class='{base_cls} nota-roja-rep'>{s}</td>"
                        except:
                            if s.upper() == 'I':
                                return f"<td class='{base_cls} nota-roja-rep'>{s}</td>"
                        return f"<td class='{base_cls}'>{s}</td>"

                    # Generar celdas según modo
                    if modo_s1_solo:
                        celdas_notas = "".join([_formato_celda_nota(val, "nota-cell") for val in n_s1])
                        c_p1 = _formato_celda_nota(p1_val, "prom-cell")
                        filas_tabla_html += f"<tr><td class='asig-col'>{asig}</td>{celdas_notas}{c_p1}</tr>"
                    elif modo_s2_solo:
                        celdas_notas = "".join([_formato_celda_nota(val, "nota-cell") for val in n_s2])
                        c_p2 = _formato_celda_nota(p2_val, "prom-cell")
                        filas_tabla_html += f"<tr><td class='asig-col'>{asig}</td>{celdas_notas}{c_p2}</tr>"
                    else: # ANUAL
                        c_s1 = "".join([_formato_celda_nota(val, "nota-cell") for val in n_s1])
                        c_s2 = "".join([_formato_celda_nota(val, "nota-cell") for val in n_s2])
                        c_p1 = _formato_celda_nota(p1_val, "prom-cell")
                        c_p2 = _formato_celda_nota(p2_val, "prom-cell")
                        c_nf = _formato_celda_nota(nf_val, "nf-cell")
                        filas_tabla_html += f"<tr><td class='asig-col'>{asig}</td>{c_s1}{c_p1}{c_s2}{c_p2}{c_nf}</tr>"

                # Promedios Generales
                prom_s1_gen = f"{redondear_nota(sum(promedios_s1)/len(promedios_s1)):.1f}".replace('.', ',') if promedios_s1 else ""
                prom_s2_gen = f"{redondear_nota(sum(promedios_s2)/len(promedios_s2)):.1f}".replace('.', ',') if promedios_s2 else ""
                prom_final_gen = f"{redondear_nota(sum(promedios_finales)/len(promedios_finales)):.1f}".replace('.', ',') if promedios_finales else ""

                cls_prom_s1 = "prom-cell-gen nota-roja-rep" if (promedios_s1 and (sum(promedios_s1)/len(promedios_s1)) < 4.0) else "prom-cell-gen"
                cls_prom_s2 = "prom-cell-gen nota-roja-rep" if (promedios_s2 and (sum(promedios_s2)/len(promedios_s2)) < 4.0) else "prom-cell-gen"
                cls_prom_fn = "nf-cell nota-roja-rep" if (promedios_finales and (sum(promedios_finales)/len(promedios_finales)) < 4.0) else "nf-cell"

                # Fila de pie de tabla y encabezados con las 10 notas
                sub_th_10 = "".join([f"<th>N{i}</th>" for i in range(1, 11)])
                if modo_s1_solo:
                    fila_pie = f"<tr class='fila-prom-gen'><td class='asig-col' colspan='11'>PROMEDIO DEL PERÍODO</td><td class='{cls_prom_s1}'>{prom_s1_gen}</td></tr>"
                    th_html = f"<tr><th rowspan='2' class='asig-col'>Asignaturas</th><th colspan='10'>1er Semestre</th><th rowspan='2'>P1</th></tr><tr>{sub_th_10}</tr>"
                elif modo_s2_solo:
                    fila_pie = f"<tr class='fila-prom-gen'><td class='asig-col' colspan='11'>PROMEDIO DEL PERÍODO</td><td class='{cls_prom_s2}'>{prom_s2_gen}</td></tr>"
                    th_html = f"<tr><th rowspan='2' class='asig-col'>Asignaturas</th><th colspan='10'>2do Semestre</th><th rowspan='2'>P2</th></tr><tr>{sub_th_10}</tr>"
                else: # ANUAL
                    fila_pie = (
                        f"<tr class='fila-prom-gen'><td class='asig-col'>Promedio Por Periodos</td><td colspan='10'></td><td class='{cls_prom_s1}'>{prom_s1_gen}</td><td colspan='10'></td><td class='{cls_prom_s2}'>{prom_s2_gen}</td><td class='prom-cell-gen'></td></tr>"
                        f"<tr class='fila-prom-gen'><td class='asig-col' colspan='22'>Promedio Final Alumno</td><td class='{cls_prom_fn}'>{prom_final_gen}</td></tr>"
                    )
                    th_html = f"<tr><th rowspan='2' class='asig-col'>Asignaturas</th><th colspan='10'>1er Semestre</th><th rowspan='2'>P1</th><th colspan='10'>2do Semestre</th><th rowspan='2'>P2</th><th rowspan='2'>NF</th></tr><tr>{sub_th_10}{sub_th_10}</tr>"

                # Calcular Asistencia oficial y exacta mediante la función unificada
                periodo_inf = "s1" if modo_s1_solo else ("s2" if modo_s2_solo else "anual")
                asis_inf = calcular_asistencia_estudiante(alumno_dict, df_asist_all, curso_inf_sel, periodo=periodo_inf, config_inst=conf_inst_inf)
                total_dias_asis = asis_inf["dias_clase"]
                total_inasist = asis_inf["dias_inasist"]
                pct_asis = asis_inf["pct_asist_fmt"]
                label_asist_rec = "Asistencia 1er Semestre(%)" if modo_s1_solo else ("Asistencia 2do Semestre(%)" if modo_s2_solo else "Asistencia Anual(%)")

                # Insignia en Base64 o fallback
                insignia_img_tag = f"<img src='data:image/png;base64,{insignia_b64_html}' style='max-height:65px;max-width:65px;object-fit:contain;'>" if insignia_b64_html else "<div style='font-size:1.8rem;'>🏫</div>"

                # Firma del Director en HTML
                img_firma_tag = f"<img src='data:image/png;base64,{firma_b64}' style='max-height:55px;max-width:180px;object-fit:contain;display:block;margin:0 auto;'>" if firma_b64 else ""

                # ==========================================================
                # CONDICIONAL: CERTIFICADO DE ALUMNO REGULAR, CERTIFICADO ANUAL O INFORME DE NOTAS
                # ==========================================================
                es_modo_regular = "Alumno Regular" in tipo_inf_sel
                es_modo_certificado = "Certificado Anual" in tipo_inf_sel

                if es_modo_regular:
                    # Formato RUN
                    r_alu_fmt = r_alu.strip()
                    val_mat = str(alumno_dict.get(col_mat, '')).strip()
                    if not val_mat or val_mat in ['nan', 'None']:
                        val_mat = str(int(alumno_dict.get('_ord', 1)))

                    val_f_mat = str(alumno_dict.get(col_f_mat, '')).strip()
                    if not val_f_mat or val_f_mat in ['nan', 'None']:
                        val_f_mat = f"01-03-{hoy.year}"

                    # Curso del alumno en palabras (CON letra, en MAYÚSCULAS)
                    _c_reg = str(alumno_dict.get(col_c, curso_inf_sel) or curso_inf_sel).strip()
                    _k_reg = extraer_clave_curso(_c_reg)
                    _niv_reg = _k_reg[0]
                    _num_reg = next((ch for ch in _c_reg if ch.isdigit()), None)
                    # Extraer letra del curso (última letra mayúscula, ej: "3°A" -> "A")
                    _letra_reg = ''
                    for _ch in reversed(_c_reg):
                        if _ch.isalpha() and _ch.upper() in 'ABCDEFGHIJ':
                            _letra_reg = _ch.upper()
                            break
                    _sufijo_letra = f' {_letra_reg}' if _letra_reg else ''
                    _map_reg = {
                        "1": "PRIMER AÑO", "2": "SEGUNDO AÑO", "3": "TERCER AÑO",
                        "4": "CUARTO AÑO", "5": "QUINTO AÑO", "6": "SEXTO AÑO",
                        "7": "SÉPTIMO AÑO", "8": "OCTAVO AÑO"
                    }
                    if _niv_reg == "nt1":
                        curso_reg_palabras = f"PRIMER NIVEL DE TRANSICIÓN (NT1){_sufijo_letra} DE EDUCACIÓN PARVULARIA"
                    elif _niv_reg == "nt2":
                        curso_reg_palabras = f"SEGUNDO NIVEL DE TRANSICIÓN (NT2){_sufijo_letra} DE EDUCACIÓN PARVULARIA"
                    elif _num_reg and _num_reg in _map_reg:
                        curso_reg_palabras = f"{_map_reg[_num_reg]}{_sufijo_letra} DE EDUCACIÓN GENERAL BÁSICA"
                    else:
                        curso_reg_palabras = _c_reg.upper()


                    return f"""
                    <div class="carta-hoja cert-hoja cert-regular-hoja">
                        <!-- ENCABEZADO INSTITUCIONAL CON LÍNEA VERDE Y DATOS MINISTERIALES -->
                        <div class="header-cert-container">
                            <div class="header-cert-insignia">
                                {insignia_img_tag}
                            </div>
                            <div class="header-cert-titulos">
                                <div class="colegio-nombre">{nom_colegio}</div>
                                <div class="doc-subtitulo" style="font-size:1.10rem;letter-spacing:1px;font-weight:800;color:#1a5c32;">CERTIFICADO DE ALUMNO REGULAR</div>
                            </div>
                            <div class="header-cert-datos">
                                <div><b>Región:</b> {region_col.upper()}</div>
                                <div><b>Comuna:</b> {ciudad_col.upper()}</div>
                                <div><b>RBD:</b> {rbd_col}</div>
                                <div><b>Año Escolar:</b> {hoy.year}</div>
                            </div>
                        </div>

                        <!-- CUERPO OFICIAL DEL CERTIFICADO -->
                        <div style="padding:40px 32px 20px 32px;font-size:0.96rem;line-height:2.2;color:#111827;text-align:justify;">

                            <p style="margin-bottom:24px;">
                                La Dirección del Establecimiento Educacional <b>{nom_colegio}</b>, de {ciudad_col},
                            </p>

                            <p style="text-indent:40px;margin-bottom:20px;font-weight:700;font-size:0.97rem;">
                                Certifica que:
                            </p>

                            <p style="text-indent:40px;margin-bottom:24px;">
                                El (La) estudiante <b>{nom_alu}</b>, portador(a) del RUN <b>{r_alu_fmt}</b>,
                                se encuentra debidamente matriculado(a) en este establecimiento con el número
                                de matrícula <b>{val_mat}</b>, cursando actualmente el nivel de
                                <b>{curso_reg_palabras}</b>, en el año escolar <b>{hoy.year}</b>.
                            </p>

                            <p style="text-indent:40px;margin-bottom:32px;">
                                Se extiende el presente certificado a solicitud del (la) interesado(a),
                                para los fines que estime conveniente.
                            </p>
                        </div>


                        <!-- FIRMA OFICIAL CENTRADA -->
                        <div style="margin-top:24px;padding:0 30px;display:flex;justify-content:center;">
                            <div style="text-align:center;width:320px;">
                                <div style="height:60px;display:flex;align-items:flex-end;justify-content:center;margin-bottom:2px;">
                                    {img_firma_tag}
                                </div>
                                <div style="border-top:1.5px solid #374151;padding-top:8px;">
                                    <div style="font-weight:800;font-size:0.88rem;color:#111827;">{director_col}</div>
                                    <div style="font-size:0.78rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.3px;">Director(a) del Establecimiento</div>
                                    <div style="font-size:0.74rem;color:#6b7280;margin-top:2px;">{nom_colegio} &mdash; RBD {rbd_col}</div>
                                </div>
                            </div>
                        </div>

                        <!-- FECHA DEBAJO DE LA FIRMA -->
                        <div style="text-align:right;font-size:0.84rem;color:#374151;font-weight:600;margin-top:20px;padding-right:30px;">
                            {ciudad_col}, {hoy.day} de {meses_es[hoy.month-1]} de {hoy.year}.-
                        </div>
                    </div>
                    """
                if es_modo_certificado:
                    # Formato RUN estricto: sin puntos, solo guion
                    r_alu_sin_puntos = r_alu.replace('.', '').strip()

                    # Leer Preacta para obtener decisión oficial y observaciones del Consejo
                    recs_pre_inf = sheet_preacta.get_all_records() if sheet_preacta else []
                    df_pre_inf = pd.DataFrame(recs_pre_inf) if recs_pre_inf else pd.DataFrame()
                    sit_oficial = None
                    obs_oficial = ""

                    if not df_pre_inf.empty:
                        df_pre_inf.columns = [str(c).strip() for c in df_pre_inf.columns]
                        if 'RUT' in df_pre_inf.columns:
                            df_pre_inf['RUT_NORM'] = df_pre_inf['RUT'].astype(str).str.replace('.', '', regex=False).str.strip().str.lower()
                            coincid_pre = df_pre_inf[df_pre_inf['RUT_NORM'] == r_alu_norm]
                            if not coincid_pre.empty:
                                row_pre = coincid_pre.iloc[-1]
                                sit_oficial = str(row_pre.get('Situacion_Final', '')).strip()
                                obs_oficial = str(row_pre.get('Observaciones', '')).strip()

                    # Fallback si aún no se ha guardado la Preacta: por defecto Promovido(a)
                    if not sit_oficial:
                        sit_oficial = "Promovido(a)"

                    # Conversión formal de curso a texto en palabras
                    c_actual_str = str(alumno_dict.get(col_c, curso_inf_sel) or curso_inf_sel).strip()
                    k_cur = extraer_clave_curso(c_actual_str)
                    nivel_norm, letra_norm = k_cur[0], k_cur[1]

                    # Obtener la letra oficial directamente desde el catálogo de Cursos o clave canónica
                    letra_oficial = letra_norm.upper() if letra_norm else "A"
                    if sheet_cursos:
                        try:
                            for rc in sheet_cursos.get_all_records():
                                if calza_nombre_curso(rc.get("Nombre", ""), c_actual_str):
                                    let_rc = str(rc.get("Letra", "")).strip().upper()
                                    if let_rc:
                                        letra_oficial = let_rc
                                        break
                        except Exception:
                            pass

                    map_curso_palabras = {
                        "1": "Primer Año",
                        "2": "Segundo Año",
                        "3": "Tercer Año",
                        "4": "Cuarto Año",
                        "5": "Quinto Año",
                        "6": "Sexto Año",
                        "7": "Séptimo Año",
                        "8": "Octavo Año"
                    }

                    num_c = next((ch for ch in c_actual_str if ch.isdigit()), None)

                    if nivel_norm == "nt1":
                        nom_curso_palabras = f"Primer Nivel de Transición (NT1) {letra_oficial} de Educación Parvularia"
                        reprobado_curso_palabras = "Primer Nivel de Transición de Educación Parvularia"
                        sig_curso_palabras = "Segundo Nivel de Transición de Educación Parvularia"
                    elif nivel_norm == "nt2":
                        nom_curso_palabras = f"Segundo Nivel de Transición (NT2) {letra_oficial} de Educación Parvularia"
                        reprobado_curso_palabras = "Segundo Nivel de Transición de Educación Parvularia"
                        sig_curso_palabras = "Primer Año de Educación General Básica"
                    elif num_c and num_c in map_curso_palabras:
                        nom_curso_palabras = f"{map_curso_palabras[num_c]} {letra_oficial} de Educación General Básica"
                        reprobado_curso_palabras = f"{map_curso_palabras[num_c]} de Educación General Básica"
                        num_siguiente = str(int(num_c) + 1)
                        if num_siguiente in map_curso_palabras:
                            sig_curso_palabras = f"{map_curso_palabras[num_siguiente]} de Educación General Básica"
                        elif num_siguiente == "9":
                            sig_curso_palabras = "Primer Año de Enseñanza Media"
                        else:
                            sig_curso_palabras = "el siguiente nivel educativo"
                    else:
                        nom_curso_palabras = f"{c_actual_str} de Educación General Básica"
                        reprobado_curso_palabras = f"{c_actual_str} de Educación General Básica"
                        sig_curso_palabras = "el siguiente nivel educativo"

                    if "promov" in sit_oficial.lower():
                        texto_consecuencia = f"ha sido promovido(a) al {sig_curso_palabras}."
                    else:
                        texto_consecuencia = f"ha reprobado el {reprobado_curso_palabras}."

                    # Tabla limpia con Asignaturas y Calificación Final (solo cifras)
                    filas_cert_html = ""
                    for asig in asigs_oficiales:
                        asig_es_conceptual = any(k in asig.lower() for k in ['religi', 'orientac'])
                        p1_val, p2_val = "", ""
                        if not df_al_notas.empty:
                            m_s1 = df_al_notas[df_al_notas[col_a_n].apply(lambda x: match_asig_inf(x, asig)) & df_al_notas[col_s_n].astype(str).str.contains('1')]
                            if not m_s1.empty:
                                p1_raw = m_s1.iloc[0].get("Promedio", "")
                                if asig_es_conceptual:
                                    p1_val = nota_a_concepto(p1_raw)
                                else:
                                    num1 = parsear_prom_inf(p1_raw)
                                    if num1 is not None:
                                        p1_val = f"{num1:.1f}".replace('.', ',')

                            m_s2 = df_al_notas[df_al_notas[col_a_n].apply(lambda x: match_asig_inf(x, asig)) & df_al_notas[col_s_n].astype(str).str.contains('2')]
                            if not m_s2.empty:
                                p2_raw = m_s2.iloc[0].get("Promedio", "")
                                if asig_es_conceptual:
                                    p2_val = nota_a_concepto(p2_raw)
                                else:
                                    num2 = parsear_prom_inf(p2_raw)
                                    if num2 is not None:
                                        p2_val = f"{num2:.1f}".replace('.', ',')

                        nf_val = ""
                        if asig_es_conceptual:
                            nf_val = p2_val if p2_val else p1_val
                        else:
                            try:
                                p1_flt = float(p1_val.replace(',', '.')) if p1_val else None
                                p2_flt = float(p2_val.replace(',', '.')) if p2_val else None
                                if p1_flt and p2_flt:
                                    nf_val = f"{round((p1_flt + p2_flt) / 2.0, 1):.1f}".replace('.', ',')
                                elif p1_flt:
                                    nf_val = f"{p1_flt:.1f}".replace('.', ',')
                                elif p2_flt:
                                    nf_val = f"{p2_flt:.1f}".replace('.', ',')
                            except: pass

                        td_nf = _formato_celda_nota(nf_val, "nf-cell")
                        filas_cert_html += f"<tr><td class='asig-col' style='padding-left:10px;'>{asig}</td>{td_nf}</tr>"

                    # Observaciones format
                    linea_obs_texto = obs_oficial if obs_oficial else "&nbsp;"

                    return f"""
                    <div class="carta-hoja cert-hoja">
                        <!-- ENCABEZADO INSTITUCIONAL CON LÍNEA VERDE Y DATOS MINISTERIALES -->
                        <div class="header-cert-container">
                            <div class="header-cert-insignia">
                                {insignia_img_tag}
                            </div>
                            <div class="header-cert-titulos">
                                <div class="colegio-nombre">{nom_colegio}</div>
                                <div class="doc-subtitulo" style="font-size:1.05rem;letter-spacing:0.8px;">CERTIFICADO ANUAL DE ESTUDIOS</div>
                            </div>
                            <div class="header-cert-datos">
                                <div><b>Región:</b> {region_col.upper()}</div>
                                <div><b>Comuna:</b> {ciudad_col.upper()}</div>
                                <div><b>RBD:</b> {rbd_col}</div>
                                <div><b>Año Escolar:</b> {hoy.year}</div>
                            </div>
                        </div>

                        <!-- NORMATIVAS Y DECRETOS OFICIALES -->
                        <div class="cert-decretos">
                            <div class="cert-dec-line"><span>Plan y Programa de Estudio aprobado por: (Decreto Supremo; Decreto Supremo Exento)</span> <b>N° 628 de 2016</b></div>
                            <div class="cert-dec-line"><span>Reglamento de Evaluación y Promoción Escolar Decreto Supremo Exento</span> <b>N° decreto 67 de 2018</b></div>
                            <div class="cert-dec-line"><span>Documento que lo declara reconocido oficialmente por el Ministerio de Educación de la República de Chile</span> <b>N° 4711 de 1981</b></div>
                        </div>

                        <!-- IDENTIFICACIÓN DEL ESTUDIANTE -->
                        <div class="cert-alumno-intro">
                            <div style="margin-bottom:5px;">Don(a) <b style="font-size:0.88rem;">{nom_alu}</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b style="font-size:0.88rem;">RUN: {r_alu_sin_puntos}</b></div>
                            <div style="margin-bottom:5px;">Alumno(a) de <b style="font-size:0.86rem;">{nom_colegio}</b></div>
                            <div>ha cursado el <b style="font-size:0.86rem;">{nom_curso_palabras}</b> y de acuerdo a las disposiciones reglamentarias vigentes, ha obtenido los siguientes resultados:</div>
                        </div>

                        <!-- TABLA DE CALIFICACIONES FINALES -->
                        <table class="tabla-cert">
                            <thead>
                                <tr>
                                    <th class="asig-col" style="padding-left:12px;text-transform:uppercase;">Asignaturas</th>
                                    <th style="width:140px;text-align:center;">CALIFICACIÓN FINAL<br><span style="font-size:0.70rem;font-weight:600;">CIFRAS</span></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas_cert_html}
                                <tr class="fila-prom-gen">
                                    <td class="asig-col" style="padding-left:12px;">Promedio General</td>
                                    <td class="{cls_prom_fn}" style="text-align:center !important;font-size:0.88rem;">{prom_final_gen}</td>
                                </tr>
                                <tr class="fila-prom-gen">
                                    <td class="asig-col" style="padding-left:12px;">Porcentaje de Asistencia</td>
                                    <td style="text-align:center !important;font-weight:800;font-size:0.88rem;color:#111827;">{pct_asis}%</td>
                                </tr>
                            </tbody>
                        </table>

                        <!-- CONSECUENCIA DE LAS NOTAS -->
                        <div class="cert-consecuencia">
                            En consecuencia, {texto_consecuencia}
                        </div>

                        <!-- OBSERVACIONES -->
                        <div class="cert-observaciones">
                            <div class="cert-obs-lbl">Observaciones:</div>
                            <div class="cert-obs-lineas">
                                <div class="obs-linea-texto">{linea_obs_texto}</div>
                            </div>
                        </div>

                        <!-- FECHA CIUDAD -->
                        <div class="cert-fecha">
                            {ciudad_col.upper()}, {hoy.day} de {meses_es[hoy.month - 1]} de {hoy.year}.
                        </div>

                        <!-- SECCIÓN FIRMAS CON DATOS OFICIALES -->
                        <div class="firmas-container" style="margin-top:20px;">
                            <div class="firma-box">
                                <div class="espacio-firma-grafica"></div>
                                <div class="linea-firma"></div>
                                <div class="firma-nombre">{prof_jefe_nombre}</div>
                                <div class="firma-cargo">NOMBRE Y FIRMA<br>PROFESOR(A) JEFE</div>
                            </div>
                            <div class="firma-box">
                                <div class="espacio-firma-grafica">{img_firma_tag}</div>
                                <div class="linea-firma"></div>
                                <div class="firma-nombre">{director_col}</div>
                                <div class="firma-cargo">NOMBRE, APELLIDOS, FIRMA Y TIMBRE DIRECTOR(A)<br>DEL ESTABLECIMIENTO</div>
                            </div>
                        </div>
                    </div>
                    """

                return f"""
                <div class="carta-hoja">
                    <!-- ENCABEZADO -->
                    <div class="header-container">
                        <div class="header-insignia">
                            {insignia_img_tag}
                        </div>
                        <div class="header-titulos">
                            <div class="colegio-nombre">{nom_colegio}</div>
                            <div class="doc-subtitulo">{subtitulo_inf}</div>
                        </div>
                        <div class="header-espaciador"></div>
                    </div>

                    <!-- FICHA ESTUDIANTE -->
                    <div class="ficha-estudiante">
                        <div class="ficha-row">
                            <div class="ficha-col"><span class="lbl">Nombre:</span> <b>{nom_alu}</b></div>
                            <div class="ficha-col" style="flex:0.7;"><span class="lbl">Rut:</span> <b>{r_alu}</b></div>
                        </div>
                        <div class="ficha-row" style="margin-top:3px;">
                            <div class="ficha-col"><span class="lbl">Curso:</span> <b>{curso_inf_sel}</b></div>
                            <div class="ficha-col" style="flex:0.7;"><span class="lbl">Orden:</span> <b>{ord_alu}</b></div>
                        </div>
                        <div class="ficha-row" style="margin-top:3px;">
                            <div class="ficha-col"><span class="lbl">Profesor Jefe:</span> <b>{prof_jefe_nombre}</b></div>
                        </div>
                    </div>

                    <!-- MATRIZ DE CALIFICACIONES FORMATO CARTA VERTICAL -->
                    <table class="tabla-notas">
                        <thead>
                            {th_html}
                        </thead>
                        <tbody>
                            {filas_tabla_html}
                            {fila_pie}
                        </tbody>
                    </table>

                    <!-- RECUADRO ASISTENCIA -->
                    <div class="recuadro-asistencia">
                        <div>Total Días Trabajados: <b>{total_dias_asis}</b></div>
                        <div>{label_asist_rec}: <b>{pct_asis}%</b></div>
                        <div>Total Días Inasistentes: <b>{total_inasist}</b></div>
                    </div>

                    <!-- SECCIÓN FIRMAS PERFECTAMENTE ALINEADAS -->
                    <div class="firmas-container">
                        <div class="firma-box">
                            <div class="espacio-firma-grafica"></div>
                            <div class="linea-firma"></div>
                            <div class="firma-nombre">{prof_jefe_nombre}</div>
                            <div class="firma-cargo">NOMBRE Y FIRMA PROFESOR(A) JEFE</div>
                        </div>
                        <div class="firma-box">
                            <div class="espacio-firma-grafica">{img_firma_tag}</div>
                            <div class="linea-firma"></div>
                            <div class="firma-nombre">{director_col}</div>
                            <div class="firma-cargo">DIRECTOR(A) DEL ESTABLECIMIENTO</div>
                        </div>
                    </div>

                    <!-- FECHA DEBAJO DE LAS FIRMAS -->
                    <div class="fecha-debajo-firmas">
                        {fecha_str}
                    </div>
                </div>
                """

            # Estilos CSS de alta resolución Carta Vertical estricta (8.5in x 11in)
            css_informe = """
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                <title>Informe de Calificaciones</title>
                <style>
                    @page {
                        size: letter portrait;
                        margin: 10mm 12mm 8mm 12mm;
                    }
                    @media print {
                        html, body {
                            background: #ffffff !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            -webkit-print-color-adjust: exact !important;
                            print-color-adjust: exact !important;
                        }
                        .carta-hoja {
                            box-shadow: none !important;
                            border: none !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            width: 100% !important;
                            max-width: 100% !important;
                            page-break-after: always;
                            page-break-inside: avoid;
                            break-after: page;
                            height: 250mm !important;
                            max-height: 250mm !important;
                            box-sizing: border-box !important;
                        }
                    }
                    * {
                        box-sizing: border-box;
                    }
                    body {
                        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
                        color: #111827;
                        background: #ffffff;
                        margin: 0;
                        padding: 0;
                    }
                    .carta-hoja {
                        width: 100%;
                        max-width: 760px;
                        margin: 0 auto;
                        padding: 12px 16px;
                        box-sizing: border-box;
                    }
                    .header-container {
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        border-bottom: 2.5px solid #008F39;
                        padding-bottom: 8px;
                        margin-bottom: 12px;
                    }
                    .header-insignia {
                        width: 75px;
                        display: flex;
                        align-items: center;
                        justify-content: flex-start;
                    }
                    .header-titulos {
                        text-align: center;
                        flex: 1;
                        padding: 0 10px;
                    }
                    .header-espaciador {
                        width: 75px;
                    }
                    .colegio-nombre {
                        font-size: 1.18rem;
                        font-weight: 800;
                        color: #111827;
                        letter-spacing: 0.5px;
                    }
                    .doc-subtitulo {
                        font-size: 0.98rem;
                        font-weight: 700;
                        color: #166534;
                        margin-top: 3px;
                        letter-spacing: 0.5px;
                    }
                    .fecha-debajo-firmas {
                        text-align: right;
                        font-size: 0.80rem;
                        color: #4b5563;
                        font-weight: 600;
                        margin-top: 14px;
                        padding-right: 24px;
                    }
                    .ficha-estudiante {
                        background: #f9fafb;
                        border: 1px solid #d1d5db;
                        border-radius: 4px;
                        padding: 8px 14px;
                        margin-bottom: 12px;
                        font-size: 0.84rem;
                    }
                    .ficha-row {
                        display: flex;
                        justify-content: space-between;
                    }
                    .ficha-col {
                        flex: 1;
                    }
                    .lbl {
                        color: #4b5563;
                        font-weight: 600;
                    }
                    .tabla-notas {
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 0.76rem;
                        margin-bottom: 12px;
                    }
                    .tabla-notas th, .tabla-notas td {
                        border: 1px solid #9ca3af;
                        padding: 3.5px 2px;
                        text-align: center;
                    }
                    .tabla-notas th {
                        background: #f3f4f6;
                        font-weight: 700;
                        color: #111827;
                        font-size: 0.74rem;
                    }
                    .asig-col {
                        text-align: left !important;
                        padding-left: 6px !important;
                        font-weight: 600;
                        color: #111827;
                        white-space: nowrap;
                    }
                    .nota-cell {
                        width: 20px;
                        font-weight: 500;
                        font-size: 0.78rem;
                        color: #1f2937;
                    }
                    .prom-cell {
                        width: 26px;
                        font-weight: 800;
                        font-size: 0.82rem;
                        background: #f9fafb;
                        color: #111827;
                    }
                    .nf-cell {
                        width: 28px;
                        font-weight: 800;
                        font-size: 0.84rem;
                        background: #f0fdf4;
                        color: #166534;
                        text-align: center !important;
                    }
                    .fila-prom-gen td {
                        font-weight: 800;
                        font-size: 0.84rem;
                        background: #f3f4f6;
                    }
                    .prom-cell-gen {
                        font-weight: 800;
                        font-size: 0.86rem;
                        color: #166534;
                    }
                    .nota-roja-rep {
                        color: #dc2626 !important;
                        font-weight: 800 !important;
                    }
                    .recuadro-asistencia {
                        display: flex;
                        justify-content: space-between;
                        padding: 8px 16px;
                        font-size: 0.82rem;
                        color: #1f2937;
                        font-weight: 600;
                        border-top: 1.5px solid #d1d5db;
                        border-bottom: 1.5px solid #d1d5db;
                        margin-bottom: 20px;
                    }
                    .firmas-container {
                        display: flex;
                        justify-content: space-between;
                        align-items: flex-end;
                        margin-top: 18px;
                        padding: 0 24px;
                    }
                    .firma-box {
                        text-align: center;
                        width: 44%;
                        display: flex;
                        flex-direction: column;
                        justify-content: flex-end;
                    }
                    .espacio-firma-grafica {
                        height: 55px;
                        display: flex;
                        align-items: flex-end;
                        justify-content: center;
                        margin-bottom: 2px;
                    }
                    .linea-firma {
                        border-top: 1.2px solid #374151;
                        margin-bottom: 4px;
                        width: 100%;
                    }
                    .firma-nombre {
                        font-weight: 700;
                        font-size: 0.82rem;
                        color: #111827;
                    }
                    .firma-cargo {
                        font-size: 0.70rem;
                        color: #4b5563;
                        font-weight: 600;
                    }

                    /* ==========================================================
                       ESTILOS ESPECÍFICOS PARA CERTIFICADO ANUAL DE ESTUDIOS
                       ========================================================== */
                    .cert-hoja {
                        padding: 14px 18px !important;
                    }
                    .header-cert-container {
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        border-bottom: 2.5px solid #008F39;
                        padding-bottom: 8px;
                        margin-bottom: 12px;
                    }
                    .header-cert-insignia {
                        width: 75px;
                        text-align: left;
                    }
                    .header-cert-titulos {
                        flex: 1;
                        text-align: center;
                        padding: 0 10px;
                    }
                    .header-cert-datos {
                        text-align: right;
                        font-size: 0.76rem;
                        color: #1f2937;
                        line-height: 1.4;
                    }
                    .cert-decretos {
                        font-size: 0.74rem;
                        color: #374151;
                        line-height: 1.45;
                        margin-bottom: 12px;
                    }
                    .cert-dec-line {
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 3px;
                    }
                    .cert-alumno-intro {
                        font-size: 0.82rem;
                        color: #111827;
                        line-height: 1.5;
                        margin-bottom: 12px;
                    }
                    .tabla-cert {
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 0.80rem;
                        margin-bottom: 12px;
                    }
                    .tabla-cert th, .tabla-cert td {
                        border: 1px solid #4b5563;
                        padding: 3.5px 8px;
                    }
                    .tabla-cert th {
                        background: #f3f4f6;
                        color: #111827;
                        font-weight: 700;
                        font-size: 0.80rem;
                    }
                    .tabla-cert td.nf-cell {
                        text-align: center !important;
                        font-size: 0.86rem;
                        font-weight: 800;
                    }
                    .cert-consecuencia {
                        font-size: 0.84rem;
                        color: #111827;
                        margin: 12px 0 10px 0;
                        font-weight: 600;
                    }
                    .cert-observaciones {
                        font-size: 0.78rem;
                        color: #111827;
                        margin-bottom: 12px;
                    }
                    .cert-obs-lbl {
                        font-weight: 700;
                        margin-bottom: 3px;
                    }
                    .obs-linea-texto {
                        border-bottom: 1px solid #4b5563;
                        min-height: 20px;
                        padding-left: 4px;
                        font-style: italic;
                        font-size: 0.80rem;
                        color: #374151;
                    }
                    .cert-fecha {
                        font-size: 0.80rem;
                        font-weight: 600;
                        color: #111827;
                        margin: 16px 0 12px 0;
                    }
                </style>
            </head>
            <body>
            """

            # 6. Alumnos a Generar
            alumnos_a_generar = []
            if alumno_inf_sel == "Todos los Alumnos del Curso":
                for _, r_a in df_curso_inf.iterrows():
                    alumnos_a_generar.append(r_a.to_dict())
            else:
                alumnos_a_generar.append(map_est_inf[alumno_inf_sel])

            # Botón Streamlit nativo: no requiere vista previa invasiva en pantalla
            c_btn1, c_btn2 = st.columns([2.5, 4.5])
            with c_btn1:
                btn_lanzar_impresion = st.button("🖨️ Imprimir / Guardar PDF", type="primary", use_container_width=True, key="btn_trigger_print")

            if btn_lanzar_impresion:
                html_acumulado = css_informe
                for al_item in alumnos_a_generar:
                    html_acumulado += generar_html_informe_alumno(al_item)
                
                # Identificador de tiempo único para evitar cacheo del navegador
                ts_print = int(time.time() * 1000)
                html_acumulado += f"""
                <!-- ts_{ts_print} -->
                <script>
                    setTimeout(function() {{
                        window.focus();
                        window.print();
                    }}, 150);
                </script>
                </body></html>
                """

                # Iframe invisible con contenido dinamico (ts) para garantizar re-ejecucion sin parametro key
                st.components.v1.html(html_acumulado, height=0, scrolling=False)
                st.success(f"✅ Enviando {len(alumnos_a_generar)} informe(s) a la ventana de impresión...")
        except Exception as e:
            st.error(f"Error al generar los informes: {e}")

elif st.session_state.current_module == 'desarrollo_personal':

    renderizar_insignia_universal()

    col_titulo, col_escape = st.columns([4.2, 1.1])
    with col_titulo:
        st.markdown("<h1 style='margin:0;padding:2px 0;line-height:1.3;'>🌱 Informe de Desarrollo Personal y Social</h1>", unsafe_allow_html=True)
    with col_escape:
        st.markdown("<div class='btn-volver-container' style='padding-top:2px;'>", unsafe_allow_html=True)
        if st.button("🏠 Volver", key="btn_escape_sup_dp", use_container_width=True):
            navigate('home')
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 14px 0;'>", unsafe_allow_html=True)

    sheet_alumnos, _, _, _, sheet_asignaciones = get_sheets()
    sheet_config = get_config_sheet()
    sheet_dp = get_desarrollo_personal_sheet()

    if not sheet_alumnos or not sheet_dp:
        st.error("❌ Error de conexión con la base de datos.")
    else:
        try:
            # 1. Cargar Configuración Institucional
            conf_data = {}
            if sheet_config:
                for r in sheet_config.get_all_records():
                    conf_data[str(r.get("Clave","")).strip()] = str(r.get("Valor","")).strip()

            nom_colegio = conf_data.get("nombre_colegio", "ESCUELA ARTÍSTICA VILLA LAS PEÑAS")
            region_col  = conf_data.get("region", "BÍOBÍO")
            ciudad_col  = conf_data.get("ciudad", "Mulchén")
            rbd_col     = conf_data.get("rbd", "4410-5")
            director_col = conf_data.get("nombre_director", "RUBÉN MARCOS QUEZADA BALBOA")
            firma_b64   = conf_data.get("firma_director_b64", "")

            # Cargar insignia local institucional en Base64
            insignia_b64_html = ""
            for p_ins in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "insignia.png"), "insignia.png", "C:/SistemaEscolar/insignia.png"]:
                if os.path.exists(p_ins):
                    try:
                        with open(p_ins, "rb") as f_ins:
                            insignia_b64_html = base64.b64encode(f_ins.read()).decode('utf-8')
                        break
                    except Exception:
                        pass

            # 2. Cargar Cursos y Alumnos
            recs_al = sheet_alumnos.get_all_records()
            df_al_dp = pd.DataFrame(recs_al) if recs_al else pd.DataFrame()
            if not df_al_dp.empty:
                df_al_dp.columns = [str(c).strip() for c in df_al_dp.columns]

            col_c = next((c for c in df_al_dp.columns if 'curs' in c.lower()), 'Curso')
            col_n = next((c for c in df_al_dp.columns if 'nomb' in c.lower()), 'Nombre')
            col_r = next((c for c in df_al_dp.columns if 'rut' in c.lower()), 'RUT')
            col_o = next((c for c in df_al_dp.columns if any(x in c.lower() for x in ['list','orden','n°','nro'])), 'N° Lista')
            col_baja = next((c for c in df_al_dp.columns if 'baja' in c.lower() or 'retir' in c.lower()), 'Fecha Baja')

            cursos_disp = obtener_cursos_oficiales_sistema()

            # Definición Oficial de Dimensiones y Criterios
            DIMENSIONES_CRITERIOS = [
                (
                    "RESPONSABILIDAD",
                    [
                        ("C1", "1.- El estudiante manifiesta responsabilidad y puntualidad en el cumplimiento de sus deberes escolares."),
                        ("C2", "2.- El estudiante manifiesta interés y preocupación por su aprendizaje."),
                        ("C3", "3.- El estudiante manifiesta respeto y aceptación por las normas de trabajo acordadas, cumpliendo cada una de ellas.")
                    ]
                ),
                (
                    "INTERACCIÓN Y PARTICIPACIÓN",
                    [
                        ("C4", "1.- El estudiante interactúa con sus pares y/o funcionarios cumpliendo con las normas de convivencia establecidas."),
                        ("C5", "2.- El estudiante participa de las diversas actividades programadas por el establecimiento."),
                        ("C6", "3.- El estudiante contribuye a lograr una buena convivencia en su curso.")
                    ]
                ),
                (
                    "TRABAJO ESCOLAR",
                    [
                        ("C7", "1.- El estudiante , dadas las instrucciones, es capaz de realizar un trabajo autónomo en las diversas actividades pedagógicas."),
                        ("C8", "2.- El estudiante demuestra iniciativa en el trabajo escolar individual y grupal."),
                        ("C9", "3.- El estudiante comunica oportunamente al profesor (a) las dificultades que le impidan realizar las actividades solicitadas.")
                    ]
                ),
                (
                    "CRECIMIENTO PERSONAL",
                    [
                        ("C10", "1.- El estudiante es capaz de aceptar situaciones desfavorables, en la realización y desarrollo del trabajo."),
                        ("C11", "2.- El estudiante plantea nuevos desafíos frente a las limitaciones o dificultades que se le presentan en el trabajo pedagógico y en el aspecto emocional."),
                        ("C12", "3.- El estudiante reconoce sus errores y/o dificultades y actúa en consecuencia para mejorar.")
                    ]
                )
            ]
            OPCIONES_CONCEPTO = ["Siempre", "Generalmente", "Ocasionalmente", "No Observado"]

            # Año escolar automático
            anio_dp_sel = datetime.date.today().year

            # Barra Superior de Filtros: Curso, Periodo y Estudiante
            c_f1, c_f2, c_f3 = st.columns([2.5, 2.5, 4.0])
            with c_f1:
                curso_dp_sel = st.selectbox("📚 Curso:", cursos_disp, key="sel_curso_dp")
            with c_f2:
                periodo_dp_sel = st.selectbox("⏳ Periodo:", ["Primer Semestre", "Segundo Semestre", "Anual"], key="sel_periodo_dp")

            # Filtrar alumnos del curso
            df_curso_dp = df_al_dp[df_al_dp[col_c].astype(str).str.strip().apply(lambda x: calza_nombre_curso(x, curso_dp_sel))].copy()
            if not df_curso_dp.empty:
                if col_o in df_curso_dp.columns:
                    df_curso_dp['_ord'] = pd.to_numeric(df_curso_dp[col_o], errors='coerce').fillna(999).astype(int)
                else:
                    df_curso_dp['_ord'] = 1
                df_curso_dp = df_curso_dp.sort_values(by=['_ord'])

            opciones_alumnos = []
            map_alumnos_dp = {}
            if not df_curso_dp.empty:
                for idx_al, (_, r) in enumerate(df_curso_dp.iterrows()):
                    r_dict = r.to_dict()
                    # Identificador único para evitar colisiones si dos alumnos tienen el mismo nombre
                    tag_id = f"{r_dict.get(col_r, idx_al)}_{r_dict.get(col_o, idx_al)}"
                    map_alumnos_dp[tag_id] = r_dict
                    opciones_alumnos.append(tag_id)

            with c_f3:
                if opciones_alumnos:
                    alumno_dp_tag = st.selectbox(
                        "👤 Estudiante:",
                        opciones_alumnos,
                        format_func=lambda tid: str(map_alumnos_dp[tid].get(col_n, "")).strip().upper(),
                        key="sel_alumno_dp"
                    )
                    alumno_sel_data = map_alumnos_dp.get(alumno_dp_tag, {})
                else:
                    st.info("No hay alumnos en el curso seleccionado.")
                    alumno_sel_data = {}

            # Obtener Profesor(a) Jefe
            prof_jefe_nombre = obtener_profesor_jefe_curso(curso_dp_sel, sheet_asignaciones)

            st.markdown("<hr style='margin:10px 0 16px 0;border-color:#edf2f7;'>", unsafe_allow_html=True)

            if alumno_sel_data:
                rut_actual = str(alumno_sel_data.get(col_r, "")).strip()
                rut_norm = rut_actual.replace(".", "").replace("-", "").upper()
                nombre_actual = str(alumno_sel_data.get(col_n, "")).strip()
                orden_actual = str(alumno_sel_data.get(col_o, "-")).strip()

                # Cargar evaluaciones guardadas en Google Sheets
                recs_dp_all = sheet_dp.get_all_records() if sheet_dp else []
                eval_existente = None
                fila_dp_indice = None

                for idx, r_dp in enumerate(recs_dp_all, start=2): # Cabecera es fila 1
                    r_anio = str(r_dp.get("Año", "")).strip()
                    r_per = str(r_dp.get("Periodo", "")).strip()
                    r_rut = str(r_dp.get("RUT", "")).replace(".", "").replace("-", "").upper().strip()
                    if r_anio == str(anio_dp_sel).strip() and r_per == str(periodo_dp_sel).strip() and r_rut == rut_norm:
                        eval_existente = r_dp
                        fila_dp_indice = idx
                        break

                # Mostrar tarjeta informativa del alumno
                st.markdown(
                    f"""
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;margin-bottom:16px;">
                        <span style="color:#008F39;font-weight:700;font-size:0.95rem;">👤 {nombre_actual}</span>
                        &nbsp;&nbsp;·&nbsp;&nbsp;<b>RUN:</b> {rut_actual}
                        &nbsp;&nbsp;·&nbsp;&nbsp;<b>Curso:</b> {curso_dp_sel}
                        &nbsp;&nbsp;·&nbsp;&nbsp;<b>N° Orden:</b> {orden_actual}
                        &nbsp;&nbsp;·&nbsp;&nbsp;<b>Prof. Jefe:</b> {prof_jefe_nombre}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Formulario de criterios
                conceptos_seleccionados = {}
                
                for dim_nombre, lista_crit in DIMENSIONES_CRITERIOS:
                    st.markdown(
                        f"""
                        <div style='background:#f0fdf4;padding:8px 14px;border-radius:6px;font-weight:700;color:#166534;font-size:1.02rem;margin:16px 0 10px 0;border-left:5px solid #008F39;box-shadow:0 1px 2px rgba(0,0,0,0.02);'>
                            {dim_nombre}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    for c_code, c_texto in lista_crit:
                        # Valor previo guardado
                        val_previo = eval_existente.get(c_code, "Siempre") if eval_existente else "Siempre"
                        if val_previo not in OPCIONES_CONCEPTO:
                            val_previo = "Siempre"
                        idx_val = OPCIONES_CONCEPTO.index(val_previo)

                        col_crit_txt, col_crit_sel = st.columns([3.8, 1.2])
                        with col_crit_txt:
                            st.markdown(f"<div style='font-size:0.95rem;font-weight:500;color:#1e293b;line-height:1.42;padding-top:5px;'>{c_texto}</div>", unsafe_allow_html=True)
                        with col_crit_sel:
                            k_widget = f"sel_c_{c_code}_{rut_norm}_{periodo_dp_sel}_{anio_dp_sel}"
                            conceptos_seleccionados[c_code] = st.selectbox(
                                "Concepto",
                                OPCIONES_CONCEPTO,
                                index=idx_val,
                                key=k_widget,
                                label_visibility="collapsed"
                            )

                # Campo de Observaciones
                st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
                obs_previa = str(eval_existente.get("Observaciones", "")).strip() if eval_existente else ""
                obs_input = st.text_area(
                    "📝 Observaciones Generales (opcional):",
                    value=obs_previa,
                    height=85,
                    key=f"obs_dp_{rut_norm}_{periodo_dp_sel}_{anio_dp_sel}",
                    placeholder="Ingrese observaciones cualitativas pedagógicas o formativas..."
                )

                # Botones de Acción
                c_btn_guardar, c_btn_imp_ind, c_btn_imp_cur = st.columns([1.5, 1.5, 1.5])

                # 1. BOTÓN GUARDAR
                with c_btn_guardar:
                    if st.button("💾 Guardar Evaluación", type="primary", use_container_width=True, key="btn_save_dp"):
                        try:
                            ahora_str = obtener_ahora_chile().strftime("%Y-%m-%d %H:%M:%S")
                            fila_datos = [
                                str(anio_dp_sel),
                                str(periodo_dp_sel),
                                str(curso_dp_sel),
                                str(rut_actual),
                                str(nombre_actual),
                                conceptos_seleccionados.get("C1", "Siempre"),
                                conceptos_seleccionados.get("C2", "Siempre"),
                                conceptos_seleccionados.get("C3", "Siempre"),
                                conceptos_seleccionados.get("C4", "Siempre"),
                                conceptos_seleccionados.get("C5", "Siempre"),
                                conceptos_seleccionados.get("C6", "Siempre"),
                                conceptos_seleccionados.get("C7", "Siempre"),
                                conceptos_seleccionados.get("C8", "Siempre"),
                                conceptos_seleccionados.get("C9", "Siempre"),
                                conceptos_seleccionados.get("C10", "Siempre"),
                                conceptos_seleccionados.get("C11", "Siempre"),
                                conceptos_seleccionados.get("C12", "Siempre"),
                                str(obs_input).strip(),
                                ahora_str
                            ]

                            if fila_dp_indice:
                                # Actualizar fila existente
                                range_upd = f"A{fila_dp_indice}:S{fila_dp_indice}"
                                sheet_dp.update(values=[fila_datos], range_name=range_upd)
                            else:
                                # Nueva fila
                                sheet_dp.append_row(fila_datos)

                            st.success(f"✅ ¡Evaluación de {nombre_actual} guardada exitosamente!")
                            time.sleep(0.8)
                            st.rerun()
                        except Exception as err_save:
                            st.error(f"Error al guardar la evaluación: {err_save}")

                # Generador HTML para Impresión Institucional Oficial
                def construir_html_informe_dp(al_data, conceptos_dict, obs_texto):
                    nom_al = str(al_data.get(col_n, "")).strip().upper()
                    rut_al = str(al_data.get(col_r, "")).strip()
                    ord_al = str(al_data.get(col_o, "-")).strip()
                    
                    # Fecha en formato formal chileno
                    dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                    meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                    hoy = datetime.date.today()
                    fecha_str = f"{ciudad_col.upper()}, {dias_es[hoy.weekday()]}, {hoy.day} de {meses_es[hoy.month-1]} de {hoy.year}."

                    # Firma Director
                    firma_img_tag = ""
                    if firma_b64:
                        firma_img_tag = f'<img src="data:image/png;base64,{firma_b64}" alt="Firma y Timbre">'

                    # Filas de la tabla
                    filas_html = ""
                    for dim_nom, crit_items in DIMENSIONES_CRITERIOS:
                        filas_html += f"""
                        <tr class="fila-dim">
                            <td colspan="2">{dim_nom}</td>
                        </tr>
                        """
                        for cod_c, txt_c in crit_items:
                            val_c = conceptos_dict.get(cod_c, "No Observado")
                            filas_html += f"""
                            <tr class="fila-crit">
                                <td class="col-crit">{txt_c}</td>
                                <td class="col-conc">{val_c}</td>
                            </tr>
                            """

                    # Imagen Insignia
                    insignia_tag = ""
                    if insignia_b64_html:
                        insignia_tag = f'<img src="data:image/png;base64,{insignia_b64_html}" alt="Insignia">'

                    html_doc = f"""
                    <div class="carta-hoja">
                        <!-- ENCABEZADO INSTITUCIONAL -->
                        <div class="header-container">
                            <div class="header-insignia">
                                {insignia_tag}
                            </div>
                            <div class="header-titulos">
                                <div class="colegio-nombre">{nom_colegio}</div>
                                <div class="doc-subtitulo">INFORME DE DESARROLLO PERSONAL Y SOCIAL</div>
                            </div>
                            <div class="header-datos">
                                <div><span class="lbl">Región:</span> {region_col}</div>
                                <div><span class="lbl">Comuna:</span> {ciudad_col.upper()}</div>
                                <div><span class="lbl">RBD:</span> {rbd_col}</div>
                                <div><span class="lbl">Año Escolar:</span> {anio_dp_sel}</div>
                                <div><span class="lbl">Periodo:</span> {periodo_dp_sel}</div>
                            </div>
                        </div>

                        <!-- FICHA DEL ESTUDIANTE -->
                        <div class="ficha-estudiante">
                            <div class="ficha-row">
                                <div class="ficha-col" style="flex:1.8;">
                                    <span class="lbl">ALUMNO (A):</span> <b>{nom_al}</b>
                                </div>
                                <div class="ficha-col" style="text-align:right;">
                                    <span class="lbl">RUN:</span> <b>{rut_al}</b>
                                </div>
                            </div>
                            <div class="ficha-row" style="margin-top:5px;">
                                <div class="ficha-col">
                                    <span class="lbl">CURSO:</span> <b>{curso_dp_sel}</b>
                                </div>
                                <div class="ficha-col" style="text-align:center;">
                                    <span class="lbl">N° ORDEN:</span> <b>{ord_al}</b>
                                </div>
                                <div class="ficha-col" style="text-align:right;">
                                    <span class="lbl">PROF. JEFE:</span> <b>{prof_jefe_nombre}</b>
                                </div>
                            </div>
                        </div>

                        <!-- TABLA DE DIMENSIONES Y CONCEPTOS -->
                        <table class="tabla-evaluacion">
                            <thead>
                                <tr>
                                    <th style="text-align:left;padding-left:8px;">DIMENSIONES</th>
                                    <th style="width:130px;">Concepto</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas_html}
                            </tbody>
                        </table>

                        <!-- RECUADRO DE OBSERVACIONES -->
                        <div class="recuadro-obs">
                            <div class="obs-titulo">Observaciones:</div>
                            <div class="obs-contenido">{obs_texto if obs_texto else 'Sin observaciones registradas.'}</div>
                        </div>

                        <!-- SECCIÓN FIRMAS PERFECTAMENTE ALINEADAS -->
                        <div class="firmas-container">
                            <div class="firma-box">
                                <div class="espacio-firma-grafica"></div>
                                <div class="linea-firma"></div>
                                <div class="firma-nombre">{prof_jefe_nombre}</div>
                                <div class="firma-cargo">PROFESOR(A) JEFE</div>
                            </div>
                            <div class="firma-box">
                                <div class="espacio-firma-grafica">{firma_img_tag}</div>
                                <div class="linea-firma"></div>
                                <div class="firma-nombre">{director_col}</div>
                                <div class="firma-cargo">NOMBRE, APELLIDOS, FIRMA Y TIMBRE DIRECTOR(A) DEL ESTABLECIMIENTO</div>
                            </div>
                        </div>

                        <!-- FECHA -->
                        <div class="fecha-pie">
                            {fecha_str}
                        </div>
                    </div>
                    """
                    return html_doc

                css_impresion_dp = """
                <!DOCTYPE html>
                <html lang="es">
                <head>
                    <meta charset="UTF-8">
                    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                    <title>Informe de Desarrollo Personal y Social</title>
                    <style>
                        @page {
                            size: letter portrait;
                            margin: 10mm 12mm 8mm 12mm;
                        }
                        @media print {
                            html, body {
                                background: #ffffff !important;
                                margin: 0 !important;
                                padding: 0 !important;
                                -webkit-print-color-adjust: exact !important;
                                print-color-adjust: exact !important;
                            }
                            .carta-hoja {
                                box-shadow: none !important;
                                border: none !important;
                                margin: 0 !important;
                                padding: 0 !important;
                                width: 100% !important;
                                max-width: 100% !important;
                                page-break-after: always;
                                page-break-inside: avoid;
                                break-after: page;
                                height: 250mm !important;
                                max-height: 250mm !important;
                                box-sizing: border-box !important;
                            }
                            .carta-hoja:last-child {
                                page-break-after: auto !important;
                                break-after: auto !important;
                            }
                        }
                        * {
                            box-sizing: border-box;
                        }
                        body {
                            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
                            color: #111827;
                            background: #ffffff;
                            margin: 0;
                            padding: 0;
                        }
                        .carta-hoja {
                            width: 100%;
                            max-width: 760px;
                            margin: 0 auto;
                            padding: 12px 16px;
                            box-sizing: border-box;
                        }
                        .header-container {
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            border-bottom: 2.5px solid #008F39;
                            padding-bottom: 8px;
                            margin-bottom: 12px;
                        }
                        .header-insignia {
                            width: 80px;
                            text-align: left;
                        }
                        .header-insignia img {
                            max-height: 80px;
                            max-width: 80px;
                            object-fit: contain;
                        }
                        .header-titulos {
                            text-align: center;
                            flex: 1;
                            padding: 0 10px;
                        }
                        .colegio-nombre {
                            font-size: 1.18rem;
                            font-weight: 800;
                            color: #111827;
                            letter-spacing: 0.5px;
                            text-transform: uppercase;
                        }
                        .doc-subtitulo {
                            font-size: 0.98rem;
                            font-weight: 700;
                            color: #166534;
                            margin-top: 3px;
                            letter-spacing: 0.5px;
                        }
                        .header-datos {
                            text-align: right;
                            font-size: 0.78rem;
                            color: #4b5563;
                            font-weight: 600;
                            line-height: 1.4;
                            min-width: 130px;
                        }
                        .ficha-estudiante {
                            background: #f9fafb;
                            border: 1px solid #d1d5db;
                            border-radius: 4px;
                            padding: 8px 14px;
                            margin-bottom: 12px;
                            font-size: 0.84rem;
                        }
                        .ficha-row {
                            display: flex;
                            justify-content: space-between;
                        }
                        .ficha-col {
                            flex: 1;
                        }
                        .lbl {
                            color: #4b5563;
                            font-weight: 600;
                        }
                        .tabla-evaluacion {
                            width: 100%;
                            border-collapse: collapse;
                            font-size: 0.80rem;
                            margin-bottom: 12px;
                        }
                        .tabla-evaluacion th {
                            border: 1px solid #9ca3af;
                            padding: 4px 6px;
                            background: #f3f4f6;
                            font-weight: 700;
                            color: #111827;
                            font-size: 0.78rem;
                        }
                        .fila-dim td {
                            background: #eaf5ee !important;
                            color: #166534 !important;
                            font-weight: 800 !important;
                            font-size: 0.84rem !important;
                            border: 1px solid #9ca3af !important;
                            padding: 4px 8px !important;
                            text-transform: uppercase;
                            letter-spacing: 0.3px;
                        }
                        .fila-crit td {
                            border: 1px solid #d1d5db;
                            padding: 3.5px 8px;
                        }
                        .col-crit {
                            text-align: left;
                            font-size: 0.80rem;
                            color: #1f2937;
                            line-height: 1.35;
                        }
                        .col-conc {
                            text-align: center;
                            width: 130px;
                            font-weight: 700;
                            font-size: 0.80rem;
                            color: #111827;
                            background: #f9fafb;
                        }
                        .recuadro-obs {
                            background: #f9fafb;
                            border: 1px solid #d1d5db;
                            border-radius: 4px;
                            padding: 6px 10px;
                            margin-bottom: 14px;
                            min-height: 48px;
                            font-size: 0.80rem;
                        }
                        .obs-titulo {
                            font-weight: 700;
                            color: #166534;
                            margin-bottom: 2px;
                            font-size: 0.80rem;
                        }
                        .obs-contenido {
                            color: #374151;
                            font-style: italic;
                            line-height: 1.35;
                        }
                        .firmas-container {
                            display: flex;
                            justify-content: space-between;
                            align-items: flex-end;
                            margin-top: 18px;
                            padding: 0 24px;
                        }
                        .firma-box {
                            text-align: center;
                            width: 44%;
                            display: flex;
                            flex-direction: column;
                            justify-content: flex-end;
                        }
                        .espacio-firma-grafica {
                            height: 55px;
                            display: flex;
                            align-items: flex-end;
                            justify-content: center;
                            margin-bottom: 2px;
                        }
                        .espacio-firma-grafica img {
                            max-height: 55px;
                            max-width: 170px;
                            object-fit: contain;
                        }
                        .linea-firma {
                            border-top: 1.2px solid #374151;
                            margin-bottom: 4px;
                            width: 100%;
                        }
                        .firma-nombre {
                            font-weight: 700;
                            font-size: 0.82rem;
                            color: #111827;
                        }
                        .firma-cargo {
                            font-size: 0.70rem;
                            color: #4b5563;
                            font-weight: 600;
                        }
                        .fecha-pie {
                            font-size: 0.78rem;
                            color: #4b5563;
                            font-weight: 600;
                            margin-top: 12px;
                            text-transform: uppercase;
                        }
                    </style>
                </head>
                <body>
                """

                # Limpiar cualquier payload residual previo
                if "imprimir_dp_payload" in st.session_state:
                    del st.session_state["imprimir_dp_payload"]

                # 2. BOTÓN IMPRIMIR INDIVIDUAL
                with c_btn_imp_ind:
                    if st.button("🖨️ Imprimir Alumno", use_container_width=True, key="btn_imp_ind_dp"):
                        ts_dp_ind = int(time.time() * 1000)
                        html_ind = css_impresion_dp
                        html_ind += construir_html_informe_dp(alumno_sel_data, conceptos_seleccionados, obs_input)
                        html_ind += f"""
                        <!-- ts_{ts_dp_ind} -->
                        <script>
                            setTimeout(function() {{
                                window.focus();
                                window.print();
                            }}, 150);
                        </script>
                        </body></html>
                        """
                        st.components.v1.html(html_ind, height=0, scrolling=False)

                # 3. BOTÓN IMPRIMIR CURSO COMPLETO
                with c_btn_imp_cur:
                    if st.button("📑 Imprimir Todo el Curso", use_container_width=True, key="btn_imp_cur_dp"):
                        ts_dp_cur = int(time.time() * 1000)
                        html_curso = css_impresion_dp
                        total_alumnos = len(df_curso_dp)

                        dict_evals_curso = {}
                        if sheet_dp:
                            for r_dp in sheet_dp.get_all_records():
                                if str(r_dp.get("Año", "")).strip() == str(anio_dp_sel).strip() and str(r_dp.get("Periodo", "")).strip() == str(periodo_dp_sel).strip():
                                    r_rut_clean = str(r_dp.get("RUT", "")).replace(".", "").replace("-", "").upper().strip()
                                    dict_evals_curso[r_rut_clean] = r_dp

                        for _, r_al_cur in df_curso_dp.iterrows():
                            al_cur_dict = r_al_cur.to_dict()
                            r_norm_cur = str(al_cur_dict.get(col_r, "")).replace(".", "").replace("-", "").upper().strip()
                            eval_al = dict_evals_curso.get(r_norm_cur, {})

                            conceptos_al = {}
                            for _, lista_c in DIMENSIONES_CRITERIOS:
                                for c_k, _ in lista_c:
                                    conceptos_al[c_k] = eval_al.get(c_k, "Siempre")
                            obs_al = eval_al.get("Observaciones", "")

                            html_curso += construir_html_informe_dp(al_cur_dict, conceptos_al, obs_al)

                        html_curso += f"""
                        <!-- ts_{ts_dp_cur} -->
                        <script>
                            setTimeout(function() {{
                                window.focus();
                                window.print();
                            }}, 150);
                        </script>
                        </body></html>
                        """
                        st.components.v1.html(html_curso, height=0, scrolling=False)

        except Exception as e:
            st.error(f"Error al cargar el módulo de Desarrollo Personal: {e}")

else:
    # Insignia Institucional Centrada
    renderizar_insignia_universal()

    st.header(f"Sección en construcción: {st.session_state.current_module.capitalize()}")

    st.write("")
    if st.button("⬅ Volver al Dashboard Principal", key="btn_volver_fallback"):
        navigate('home')
        st.rerun()
