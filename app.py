import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Escuela Villa Las Peñas", page_icon="🏫", layout="wide")

# --- CSS Personalizado ---
def local_css():
    st.markdown("""
    <style>
    .reportview-container {
        background: #F4F6F6;
    }
    /* Estilos para el sidebar en la nueva versión de Streamlit */
    [data-testid="stSidebar"] {
        background-color: #008F39;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    h1, h2, h3 {
        color: #008F39;
    }
    /* Botones primarios */
    .stButton>button {
        color: white;
        background-color: #008F39;
        border-radius: 5px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #006b2b;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- Conexión a Google Sheets ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gspread_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets. Verifica que el archivo 'credenciales.json' esté en la misma carpeta que este script. Detalle: {e}")
        return None

def get_sheet(client, sheet_name):
    try:
        try:
            spreadsheet = client.open_by_key("1CaxvcMB7dhRsaXEGw-2uDMF26pwCH4Rlc4daCc3VoLg")
        except Exception:
            spreadsheet = client.open("BD_Escuela_Villa_Las_Peñas")
        try:
            return spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
    except Exception as e:
        st.error(f"Error al abrir la hoja de cálculo 'BD_Escuela_Villa_Las_Peñas'. Asegúrate de haberla compartido con el correo de la cuenta de servicio. Detalle: {e}")
        return None

client = get_gspread_client()

# --- Barra Lateral ---
st.sidebar.title("Escuela Villa Las Peñas")
# st.sidebar.image("https://cdn-icons-png.flaticon.com/512/167/167707.png", width=100) # Logo opcional
st.sidebar.markdown("---")
modulo = st.sidebar.radio("Navegación", ["Registro de Movimientos", "Gestión de Alumnos", "Panel de Notas"])

# --- Lógica de los Módulos ---

if modulo == "Registro de Movimientos":
    st.header("📝 Registro de Movimientos")
    st.write("Registra atrasos y retiros de alumnos.")
    
    if client:
        sheet_alumnos = get_sheet(client, "Alumnos")
        sheet_registros = get_sheet(client, "Registros")
        
        with st.form("registro_form"):
            col1, col2 = st.columns(2)
            with col1:
                rut = st.text_input("RUT del Alumno (Ej: 12345678-9)")
                tipo = st.selectbox("Tipo de Movimiento", ["Atraso", "Retiro"])
            with col2:
                motivo = st.text_area("Motivo")
                
            submitted = st.form_submit_button("Guardar Registro")
            
            if submitted:
                if not rut:
                    st.warning("Por favor, ingresa el RUT del alumno.")
                else:
                    # Validar si el alumno existe
                    alumno_encontrado = False
                    if sheet_alumnos:
                        try:
                            alumnos_data = sheet_alumnos.get_all_records()
                            df_alumnos = pd.DataFrame(alumnos_data)
                            if not df_alumnos.empty and 'RUT' in df_alumnos.columns:
                                alumno = df_alumnos[df_alumnos['RUT'] == rut]
                                if alumno.empty:
                                    st.warning("El RUT ingresado no se encuentra en la base de alumnos. El registro se guardará de todas formas, pero se recomienda verificar.")
                                else:
                                    nombre_alumno = alumno.iloc[0].get('Nombre', 'Desconocido')
                                    st.success(f"Alumno verificado: {nombre_alumno}")
                                    alumno_encontrado = True
                        except Exception as e:
                            pass # Si no hay datos aún, no advertir
                    
                    # Guardar registro
                    if sheet_registros:
                        try:
                            # Asegurar que existan los encabezados
                            if not sheet_registros.row_values(1):
                                sheet_registros.append_row(["Fecha", "Hora", "RUT", "Tipo", "Motivo"])
                            
                            now = datetime.datetime.now()
                            fecha = now.strftime("%Y-%m-%d")
                            hora = now.strftime("%H:%M:%S")
                            sheet_registros.append_row([fecha, hora, rut, tipo, motivo])
                            st.success("✅ Registro guardado exitosamente en Google Sheets.")
                        except Exception as e:
                            st.error(f"Error al guardar el registro: {e}")

elif modulo == "Gestión de Alumnos":
    st.header("👥 Gestión de Alumnos")
    st.write("Carga masiva de alumnos desde un archivo CSV.")
    
    if client:
        sheet_alumnos = get_sheet(client, "Alumnos")
        
        uploaded_file = st.file_uploader("Sube un archivo CSV con columnas: RUT, Nombre, Curso, Teléfono Apoderado", type=['csv'])
        if uploaded_file is not None:
            try:
                # Intentar leer con punto y coma primero (común en Excel español)
                try:
                    df = pd.read_csv(uploaded_file, sep=';')
                    if len(df.columns) < 4: # Si falló, intentar con coma
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',')
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',')

                st.write("Vista previa de los datos:")
                st.dataframe(df.head())
                
                required_cols = ["RUT", "Nombre", "Curso", "Teléfono Apoderado"]
                
                # Comprobación más laxa de nombres de columnas ignorando mayúsculas y espacios
                cols_upper = [c.strip().upper() for c in df.columns]
                req_cols_upper = [c.upper() for c in required_cols]
                
                if all(col in cols_upper for col in req_cols_upper):
                    if st.button("Guardar Alumnos en Google Sheets"):
                        if sheet_alumnos:
                            with st.spinner('Guardando datos... esto puede tomar unos segundos'):
                                sheet_alumnos.clear()
                                sheet_alumnos.update([df.columns.values.tolist()] + df.values.tolist())
                            st.success("✅ Alumnos guardados/actualizados correctamente en la pestaña 'Alumnos'.")
                else:
                    st.error(f"El archivo debe contener las siguientes columnas (sin importar mayúsculas): {', '.join(required_cols)}")
                    st.write("Columnas encontradas:", df.columns.tolist())
            except Exception as e:
                st.error(f"Error al procesar el archivo CSV: {e}")

elif modulo == "Panel de Notas":
    st.header("📊 Panel de Notas")
    
    if client:
        sheet_notas = get_sheet(client, "Notas")
        
        tab1, tab2 = st.tabs(["Carga Masiva", "Buscador por RUT"])
        
        with tab1:
            st.subheader("Carga Masiva de Notas")
            uploaded_file = st.file_uploader("Sube un archivo CSV con notas (Columnas: RUT, Nota)", type=['csv'])
            if uploaded_file is not None:
                try:
                    try:
                        df = pd.read_csv(uploaded_file, sep=';')
                        if len(df.columns) < 2:
                            uploaded_file.seek(0)
                            df = pd.read_csv(uploaded_file, sep=',')
                    except:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',')
                        
                    st.write("Vista previa:")
                    st.dataframe(df.head())
                    
                    cols_upper = [c.strip().upper() for c in df.columns]
                    if "RUT" in cols_upper and "NOTA" in cols_upper:
                        if st.button("Guardar Notas en Google Sheets"):
                            if sheet_notas:
                                with st.spinner('Guardando notas...'):
                                    if not sheet_notas.row_values(1):
                                        sheet_notas.append_row(["Fecha", "RUT", "Nota"])
                                        
                                    now = datetime.datetime.now().strftime("%Y-%m-%d")
                                    # Asegurar nombres de columnas correctos para el df
                                    # Renombrar si es necesario
                                    col_mapping = {c: c.strip().upper() for c in df.columns}
                                    df = df.rename(columns=col_mapping)
                                    df_guardar = df[['RUT', 'NOTA']].copy()
                                    df_guardar['Fecha'] = now
                                    df_guardar = df_guardar[['Fecha', 'RUT', 'NOTA']]
                                    
                                    sheet_notas.append_rows(df_guardar.values.tolist())
                                st.success("✅ Notas cargadas exitosamente en la pestaña 'Notas'.")
                    else:
                        st.error("El archivo debe contener las columnas: RUT, Nota.")
                except Exception as e:
                    st.error(f"Error al procesar: {e}")
                    
        with tab2:
            st.subheader("Buscador de Notas por Alumno")
            search_rut = st.text_input("Ingresa el RUT del alumno para buscar sus notas:")
            if st.button("Buscar"):
                if search_rut and sheet_notas:
                    try:
                        notas_data = sheet_notas.get_all_records()
                        df_notas = pd.DataFrame(notas_data)
                        if not df_notas.empty and any(c.upper() == 'RUT' for c in df_notas.columns):
                            # Encontrar la columna rut exacta
                            rut_col = [c for c in df_notas.columns if c.upper() == 'RUT'][0]
                            resultados = df_notas[df_notas[rut_col] == search_rut]
                            
                            if not resultados.empty:
                                st.write(f"Notas registradas para **{search_rut}**:")
                                st.dataframe(resultados)
                                
                                nota_col = [c for c in resultados.columns if c.upper() == 'NOTA']
                                if nota_col:
                                    nota_c = nota_col[0]
                                    # Convertir a numérico, reemplazando comas por puntos si es necesario
                                    resultados[nota_c] = resultados[nota_c].astype(str).str.replace(',', '.')
                                    resultados[nota_c] = pd.to_numeric(resultados[nota_c], errors='coerce')
                                    promedio = resultados[nota_c].mean()
                                    st.info(f"**Promedio: {promedio:.2f}**")
                            else:
                                st.warning("No se encontraron notas para este RUT.")
                        else:
                            st.info("No hay datos de notas registrados aún.")
                    except Exception as e:
                        st.error(f"Error al buscar notas: {e}")
                else:
                    st.warning("Ingresa un RUT válido.")
