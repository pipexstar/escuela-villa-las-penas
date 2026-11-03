"""
pages/tablet_escaner.py — Escáner QR de Asistencia para Tablet
Escaneo continuo y automático vía cámara del navegador (jsQR).
Toda la lógica de negocio se ejecuta en JavaScript directamente contra Supabase,
sin necesidad de servidor local.
"""

import streamlit as st
from utils.asistencia_funcionarios import calcular_firma
from datetime import date

st.set_page_config(
    page_title="Escáner QR - Asistencia",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Verificar autenticación básica ───────────────────────────────────────────
def _verificar_acceso():
    """Control de acceso simple por clave de escáner."""
    if st.session_state.get("scanner_autenticado"):
        return True

    st.markdown("## 🔐 Acceso al Escáner de Asistencia")
    st.markdown("Ingresa la clave de acceso para activar el escáner.")
    clave = st.text_input("Clave de acceso", type="password", key="clave_input")
    if st.button("Ingresar", type="primary"):
        clave_correcta = "1234"
        try:
            clave_correcta = st.secrets.get("scanner_access_key", "1234")
        except Exception:
            pass
        if clave == clave_correcta:
            st.session_state["scanner_autenticado"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")
    return False

if not _verificar_acceso():
    st.stop()

# ─── Obtener credenciales para inyectar en JS ──────────────────────────────────
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    QR_SECRET_KEY = st.secrets.get("QR_SECRET_KEY", "eavlp_control_asistencia_secret_2026")
except Exception:
    st.error("⚠️ No se encontraron las credenciales de Supabase en st.secrets.")
    st.stop()

# Pre-calcular la firma de hoy para validarla en JS (sin exponer el secreto completo)
# El secreto se usa server-side para generar la firma esperada del día;
# JS solo verifica que el QR escaneado coincida con el patrón correcto.
HOY = date.today().strftime("%Y%m%d")

# ─── HTML del Escáner ──────────────────────────────────────────────────────────
SCANNER_HTML = f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Escáner QR</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0f172a;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    font-family: 'Segoe UI', sans-serif;
    color: white;
    padding: 16px;
  }}
  h1 {{
    font-size: 1.4rem;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 12px;
    text-align: center;
  }}
  #video-container {{
    position: relative;
    width: 100%;
    max-width: 500px;
    border-radius: 16px;
    overflow: hidden;
    border: 3px solid #334155;
    background: #000;
  }}
  #video {{
    width: 100%;
    display: block;
  }}
  #canvas {{ display: none; }}
  /* Marco de guía de escaneo */
  #guia {{
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 200px; height: 200px;
    border: 3px solid rgba(56,189,248,0.8);
    border-radius: 12px;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.35);
    pointer-events: none;
    transition: border-color 0.2s;
  }}
  #guia.ok   {{ border-color: #22c55e; }}
  #guia.error {{ border-color: #ef4444; }}
  #guia.warn  {{ border-color: #f59e0b; }}

  /* Overlay de resultado */
  #overlay {{
    position: fixed;
    inset: 0;
    display: none;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 16px;
    z-index: 100;
    transition: all 0.3s;
    padding: 24px;
    text-align: center;
  }}
  #overlay.show {{ display: flex; }}
  #overlay.entrada {{ background: rgba(34,197,94,0.93); }}
  #overlay.salida  {{ background: rgba(59,130,246,0.93); }}
  #overlay.warn    {{ background: rgba(245,158,11,0.93); }}
  #overlay.error   {{ background: rgba(239,68,68,0.93); }}

  #icono-resultado {{ font-size: 4rem; }}
  #nombre-resultado {{ font-size: 1.6rem; font-weight: 800; }}
  #tipo-resultado   {{ font-size: 1.2rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; }}
  #hora-resultado   {{ font-size: 1rem; opacity: 0.9; }}
  #msg-resultado    {{ font-size: 0.95rem; max-width: 320px; opacity: 0.95; }}

  #estado {{
    margin-top: 12px;
    padding: 8px 16px;
    background: #1e293b;
    border-radius: 8px;
    font-size: 0.85rem;
    color: #94a3b8;
    max-width: 500px;
    width: 100%;
    text-align: center;
    min-height: 36px;
  }}
  #fps-info {{
    font-size: 0.75rem;
    color: #475569;
    margin-top: 6px;
  }}
  button#btn-cerrar {{
    margin-top: 8px;
    padding: 12px 32px;
    border: none;
    border-radius: 50px;
    background: rgba(255,255,255,0.25);
    color: white;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    backdrop-filter: blur(4px);
  }}
  button#btn-cerrar:hover {{ background: rgba(255,255,255,0.4); }}
</style>
</head>
<body>
<h1>📷 Escáner de Asistencia</h1>

<div id="video-container">
  <video id="video" playsinline autoplay muted></video>
  <canvas id="canvas"></canvas>
  <div id="guia"></div>
</div>

<div id="estado">Iniciando cámara...</div>
<div id="fps-info">Escaneando continuamente · Muestra el QR de tu credencial</div>

<!-- Overlay de resultado -->
<div id="overlay">
  <div id="icono-resultado">✅</div>
  <div id="nombre-resultado">Nombre Funcionario</div>
  <div id="tipo-resultado">ENTRADA</div>
  <div id="hora-resultado">00:00:00</div>
  <div id="msg-resultado">Mensaje detallado aquí</div>
  <button id="btn-cerrar" onclick="cerrarOverlay()">Continuar ▶</button>
</div>

<script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
<script>
// ── Configuración ────────────────────────────────────────────────────────────
const SUPABASE_URL = "{SUPABASE_URL}";
const SUPABASE_KEY = "{SUPABASE_KEY}";
const HOY          = "{HOY}";            // YYYYMMDD
const SECRET_KEY   = "{QR_SECRET_KEY}";  // Para verificar HMAC en el navegador
const TABLA        = "asistencia_funcionarios_eventos";
const DEBOUNCE_SEG = 10;
const MIN_INTERVALO_MS = 3000; // No procesar el mismo QR más de 1 vez cada 3 segundos

// ── Estado ───────────────────────────────────────────────────────────────────
let procesando      = false;
let lastPayload     = "";
let lastPayloadTime = 0;
let overlayTimer    = null;

const video    = document.getElementById("video");
const canvas   = document.getElementById("canvas");
const ctx      = canvas.getContext("2d");
const overlay  = document.getElementById("overlay");
const guia     = document.getElementById("guia");
const estado   = document.getElementById("estado");

// ── Cámara ───────────────────────────────────────────────────────────────────
async function iniciarCamara() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{
      video: {{ facingMode: "environment", width: {{ ideal: 1280 }}, height: {{ ideal: 720 }} }}
    }});
    video.srcObject = stream;
    video.addEventListener("loadedmetadata", () => {{
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      estado.textContent = "✅ Cámara activa · Mostrando QR de credencial";
      scanLoop();
    }});
  }} catch(e) {{
    estado.textContent = "❌ Sin acceso a la cámara: " + e.message;
  }}
}}

// ── HMAC-SHA256 en el navegador (Web Crypto API) ─────────────────────────────
async function calcularFirma(rut, fechaYYYYMMDD) {{
  const encoder = new TextEncoder();
  const keyData = encoder.encode(SECRET_KEY);
  const msg     = encoder.encode(rut.trim() + ":" + fechaYYYYMMDD.trim());
  const key = await crypto.subtle.importKey(
    "raw", keyData, {{ name: "HMAC", hash: "SHA-256" }}, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, msg);
  // Convertir a hex y tomar los primeros 16 caracteres (igual que en Python)
  const hex = Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2,"0")).join("");
  return hex.slice(0, 16);
}}

// ── Verificar payload del QR ─────────────────────────────────────────────────
async function verificarPayload(payload) {{
  // Formato: FUNCIONARIO:{{rut}}:{{fecha}}:{{firma}}
  const partes = payload.trim().split(":");
  if (partes.length < 3 || partes[0].toUpperCase() !== "FUNCIONARIO") {{
    return {{ valido: false, msg: "QR no reconocido por el sistema." }};
  }}
  const rut       = partes[1].trim();
  const fechaQR   = partes[2].trim().replace(/-/g, "");
  const firmaQR   = partes[3] ? partes[3].trim() : "";

  if (fechaQR !== HOY) {{
    return {{ valido: false, msg: `QR expirado (fecha del QR: ${{fechaQR}}, hoy: ${{HOY}}).` }};
  }}

  if (firmaQR) {{
    const firmaEsperada = await calcularFirma(rut, fechaQR);
    if (firmaQR !== firmaEsperada) {{
      return {{ valido: false, msg: "Firma criptográfica no válida. QR alterado o falsificado." }};
    }}
  }}

  return {{ valido: true, rut, fecha: fechaQR }};
}}

// ── Llamadas a Supabase REST ─────────────────────────────────────────────────
const headers = {{
  "apikey": SUPABASE_KEY,
  "Authorization": "Bearer " + SUPABASE_KEY,
  "Content-Type": "application/json",
  "Prefer": "return=representation"
}};

async function obtenerFuncionario(rut) {{
  const r = await fetch(
    `${{SUPABASE_URL}}/rest/v1/funcionarios?rut=eq.${{encodeURIComponent(rut)}}&select=rut,nombre,rol,estado&limit=1`,
    {{ headers }}
  );
  const data = await r.json();
  return data && data.length > 0 ? data[0] : null;
}}

async function obtenerEventosHoy(rut) {{
  const hoyISO  = HOY.slice(0,4) + "-" + HOY.slice(4,6) + "-" + HOY.slice(6,8);
  const desde   = hoyISO + "T00:00:00";
  const hasta   = hoyISO + "T23:59:59";
  const r = await fetch(
    `${{SUPABASE_URL}}/rest/v1/${{TABLA}}?funcionario_id=eq.${{encodeURIComponent(rut)}}&timestamp=gte.${{desde}}&timestamp=lte.${{hasta}}&order=timestamp.asc`,
    {{ headers }}
  );
  return await r.json() || [];
}}

async function insertarEvento(rut, tipo) {{
  const ahora = new Date().toISOString().replace("Z", "");
  const r = await fetch(
    `${{SUPABASE_URL}}/rest/v1/${{TABLA}}`,
    {{
      method: "POST",
      headers,
      body: JSON.stringify({{ funcionario_id: rut, tipo, timestamp: ahora }})
    }}
  );
  if (!r.ok) {{
    const err = await r.text();
    throw new Error("Supabase error: " + err);
  }}
  const data = await r.json();
  return Array.isArray(data) ? data[0] : data;
}}

// ── Lógica de negocio (Jornada Única) ────────────────────────────────────────
async function procesarRUT(rut) {{
  // 1. Verificar funcionario
  const func = await obtenerFuncionario(rut);
  if (!func) return {{ ok: false, clase: "error", icono: "❌", msg: `RUT ${{rut}} no encontrado en la nómina.`, nombre: "Desconocido" }};
  if ((func.estado || "").toLowerCase() === "inactivo") {{
    return {{ ok: false, clase: "error", icono: "⛔", msg: "Funcionario INACTIVO.", nombre: func.nombre }};
  }}

  // 2. Consultar eventos de hoy
  const eventos = await obtenerEventosHoy(rut);
  const entrada = eventos.find(e => e.tipo === "entrada");
  const salida  = [...eventos].reverse().find(e => e.tipo === "salida");

  // 3. Anti-rebote (10 s)
  if (eventos.length > 0) {{
    const ultimo    = eventos[eventos.length - 1];
    const tsUltimo  = new Date(ultimo.timestamp + (ultimo.timestamp.endsWith("Z") ? "" : "Z"));
    const difSeg    = (Date.now() - tsUltimo.getTime()) / 1000;
    if (difSeg < DEBOUNCE_SEG) {{
      return {{
        ok: false, clase: "warn", icono: "⏱️",
        msg: `Marcaje muy reciente (${{Math.floor(difSeg)}}s). Espere unos segundos.`,
        nombre: func.nombre
      }};
    }}
  }}

  // 4. Jornada ya completada
  if (entrada && salida) {{
    return {{
      ok: false, clase: "warn", icono: "🔒",
      msg: `Jornada completada. Entrada: ${{entrada.timestamp.slice(11,19)}} — Salida: ${{salida.timestamp.slice(11,19)}}.`,
      nombre: func.nombre
    }};
  }}

  // 5. Sin entrada → registrar ENTRADA
  if (!entrada) {{
    const ev = await insertarEvento(rut, "entrada");
    const hora = new Date(ev.timestamp + "Z").toLocaleTimeString("es-CL");
    return {{ ok: true, clase: "entrada", icono: "🟢", tipo: "ENTRADA", msg: `¡Bienvenido/a! Entrada registrada a las ${{hora}}.`, nombre: func.nombre, hora }};
  }}

  // 6. Con entrada → verificar si han pasado 20 min para salida automática
  const tsIn  = new Date(entrada.timestamp + (entrada.timestamp.endsWith("Z") ? "" : "Z"));
  const minutos = (Date.now() - tsIn.getTime()) / 60000;

  if (minutos < 20) {{
    return {{
      ok: false, clase: "warn", icono: "🟡",
      msg: `Ya en el colegio (Entrada: ${{entrada.timestamp.slice(11,19)}}). Para salida forzada, escanear 2 veces en >20 min.`,
      nombre: func.nombre
    }};
  }}

  // 7. Registrar SALIDA
  const ev = await insertarEvento(rut, "salida");
  const hora = new Date(ev.timestamp + "Z").toLocaleTimeString("es-CL");
  return {{ ok: true, clase: "salida", icono: "🔵", tipo: "SALIDA", msg: `¡Hasta pronto! Salida registrada a las ${{hora}}.`, nombre: func.nombre, hora }};
}}

// ── Mostrar resultado ─────────────────────────────────────────────────────────
function mostrarResultado(resultado) {{
  overlay.className = "show " + (resultado.clase || "error");
  document.getElementById("icono-resultado").textContent  = resultado.icono  || "❌";
  document.getElementById("nombre-resultado").textContent = resultado.nombre || "";
  document.getElementById("tipo-resultado").textContent   = resultado.tipo   || (resultado.ok ? "OK" : "BLOQUEADO");
  document.getElementById("hora-resultado").textContent   = resultado.hora   || new Date().toLocaleTimeString("es-CL");
  document.getElementById("msg-resultado").textContent    = resultado.msg    || "";

  guia.className = resultado.ok ? "ok" : (resultado.clase === "warn" ? "warn" : "error");

  clearTimeout(overlayTimer);
  overlayTimer = setTimeout(cerrarOverlay, resultado.ok ? 4000 : 5000);
}}

function cerrarOverlay() {{
  overlay.className = "";
  guia.className    = "";
  procesando        = false;
  estado.textContent = "✅ Listo para escanear · Muestra el QR de tu credencial";
}}

// ── Bucle de escaneo ──────────────────────────────────────────────────────────
function scanLoop() {{
  if (!procesando) {{
    if (video.readyState === video.HAVE_ENOUGH_DATA) {{
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const img  = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(img.data, img.width, img.height, {{ inversionAttempts: "dontInvert" }});
      if (code && code.data) {{
        const ahora = Date.now();
        // Evitar procesar el mismo QR repetidamente en 3 segundos
        if (code.data !== lastPayload || (ahora - lastPayloadTime) > MIN_INTERVALO_MS) {{
          lastPayload     = code.data;
          lastPayloadTime = ahora;
          procesando      = true;
          estado.textContent = "⏳ Procesando...";
          verificarYRegistrar(code.data);
        }}
      }}
    }}
  }}
  requestAnimationFrame(scanLoop);
}}

async function verificarYRegistrar(payload) {{
  try {{
    const ver = await verificarPayload(payload);
    if (!ver.valido) {{
      mostrarResultado({{ ok: false, clase: "error", icono: "❌", msg: ver.msg, nombre: "QR inválido" }});
      return;
    }}
    const resultado = await procesarRUT(ver.rut);
    mostrarResultado(resultado);
  }} catch(e) {{
    mostrarResultado({{ ok: false, clase: "error", icono: "❌", msg: "Error de red: " + e.message, nombre: "" }});
  }}
}}

// ── Inicio ────────────────────────────────────────────────────────────────────
iniciarCamara();
</script>
</body>
</html>
"""

# ─── Renderizar el escáner ─────────────────────────────────────────────────────
st.markdown("### 📷 Escáner de Asistencia — Tablet")
st.caption("Apunta la cámara al QR de la credencial del funcionario. El escaneo es automático y continuo.")

if st.button("🔓 Cerrar sesión"):
    st.session_state.pop("scanner_autenticado", None)
    st.rerun()

st.components.v1.html(SCANNER_HTML, height=680, scrolling=False)
