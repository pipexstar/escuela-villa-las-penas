"""
pages/qr_funcionario.py — Credencial QR Digital para Funcionarios
Cada funcionario accede a esta página y ve su código QR del día,
listo para mostrar al escáner de la entrada.
"""

import streamlit as st
from utils.asistencia_funcionarios import generar_qr_data_url, obtener_supabase_seguro
from datetime import date

st.set_page_config(
    page_title="Mi QR de Asistencia",
    page_icon="🪪",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Estilos ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main { background: #0f172a; }
  section[data-testid="stMain"] { background: #0f172a; }
  [data-testid="stAppViewContainer"] { background: #0f172a; }
  .block-container { padding-top: 2rem; }
  .tarjeta-qr {
    background: white;
    border-radius: 24px;
    padding: 24px;
    text-align: center;
    max-width: 380px;
    margin: 0 auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }
  .tarjeta-qr img { width: 100%; border-radius: 12px; }
  .nombre-func { font-size: 1.3rem; font-weight: 800; color: #1e293b; margin: 12px 0 4px; }
  .rol-func    { font-size: 0.95rem; color: #64748b; margin-bottom: 8px; }
  .rut-func    { font-size: 0.85rem; color: #94a3b8; }
  .fecha-badge {
    display: inline-block;
    background: #e0f2fe; color: #0369a1;
    border-radius: 50px; padding: 4px 14px;
    font-size: 0.8rem; font-weight: 600; margin-top: 10px;
  }
  .aviso {
    background: #fef3c7; border-radius: 12px;
    padding: 10px 16px; margin: 16px auto;
    max-width: 380px; font-size: 0.85rem; color: #92400e;
    text-align: center;
  }
  h2 { color: #38bdf8 !important; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ─── Obtener RUT desde query params o sesión ───────────────────────────────────
params = st.query_params
rut_param = params.get("rut", "")

# ─── Selección de funcionario ─────────────────────────────────────────────────
st.markdown("## 🪪 Mi Credencial QR")

# Cargar lista de funcionarios para el selector
@st.cache_data(ttl=300, show_spinner=False)
def _cargar_funcionarios():
    try:
        sb = obtener_supabase_seguro()
        res = sb.table("funcionarios").select("rut, nombre, rol")\
            .neq("rut", "admin").order("nombre").execute()
        return res.data or []
    except Exception:
        return []

funcionarios = _cargar_funcionarios()

if rut_param and any(f["rut"] == rut_param for f in funcionarios):
    # Acceso directo por URL con RUT (ej: ?rut=10811850-4)
    rut_sel = rut_param
else:
    # Selector manual
    st.markdown("<p style='color:#94a3b8;text-align:center;'>Selecciona tu nombre para ver tu QR de hoy.</p>",
                unsafe_allow_html=True)
    opciones = {f["nombre"]: f["rut"] for f in funcionarios}
    nombre_sel = st.selectbox("Selecciona tu nombre", [""] + list(opciones.keys()),
                               label_visibility="collapsed")
    if not nombre_sel:
        st.markdown("<div class='aviso'>👆 Selecciona tu nombre para ver tu QR del día.</div>",
                    unsafe_allow_html=True)
        st.stop()
    rut_sel = opciones[nombre_sel]

# ─── Generar y mostrar el QR ───────────────────────────────────────────────────
func_info = next((f for f in funcionarios if f["rut"] == rut_sel), {})
nombre    = func_info.get("nombre", rut_sel)
rol       = func_info.get("rol", "Funcionario")
hoy_str   = date.today().strftime("%d/%m/%Y")

with st.spinner("Generando QR..."):
    qr_data_url = generar_qr_data_url(rut_sel)

if qr_data_url:
    st.markdown(f"""
    <div class="tarjeta-qr">
      <img src="{qr_data_url}" alt="QR de asistencia">
      <div class="nombre-func">{nombre}</div>
      <div class="rol-func">{rol}</div>
      <div class="rut-func">RUT: {rut_sel}</div>
      <div class="fecha-badge">📅 Válido solo hoy: {hoy_str}</div>
    </div>
    <div class="aviso">
      ⚠️ Este QR caduca a medianoche. Mañana se genera uno nuevo automáticamente.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Botón para cambiar de funcionario
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Ver QR de otro funcionario", use_container_width=True):
            st.query_params.clear()
            st.rerun()

    # Instrucciones de uso
    with st.expander("❓ ¿Cómo usar esta credencial?"):
        st.markdown("""
        1. **Guarda esta página** en la pantalla de inicio de tu celular (menú del navegador → *Agregar a pantalla de inicio*)
        2. Al llegar al colegio, **abre la app** y muestra este QR al escáner de la entrada
        3. El QR se renueva automáticamente cada día — no es necesario hacer nada
        4. Si alguien intenta usar un QR de otro día, el sistema lo rechazará automáticamente
        """)
else:
    st.error("No se pudo generar el QR. Verifica la conexión con Supabase.")
