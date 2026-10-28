"""
utils/database.py — Backend Supabase (PostgreSQL)
Reemplaza la conexión a Google Sheets con una capa de compatibilidad
que imita la interfaz de gspread.Worksheet para que main.py funcione
sin cambios.
"""

import streamlit as st
from supabase import create_client, Client


# ─────────────────────────────────────────────────────────────────────────────
# CONEXIÓN
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase_client() -> Client:
    """Crea y cachea el cliente de Supabase para toda la sesión."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ─────────────────────────────────────────────────────────────────────────────
# CLASE DE COMPATIBILIDAD (imita gspread.Worksheet)
# ─────────────────────────────────────────────────────────────────────────────

class SupabaseSheet:
    """
    Envuelve una tabla de Supabase con la interfaz de gspread.Worksheet.
    Métodos implementados: get_all_records, clear, update, append_row,
    append_rows, row_values, get_all_values, find.
    """

    def __init__(self, client: Client, table: str,
                 display_to_db: dict, db_to_display: dict,
                 ordered_display: list):
        """
        Args:
            client          : cliente Supabase
            table           : nombre de la tabla en PostgreSQL
            display_to_db   : {'Nombre columna UI': 'nombre_db', ...}
            db_to_display   : {'nombre_db': 'Nombre columna UI', ...}
            ordered_display : lista ordenada de nombres UI (para append_row posicional)
        """
        self._client = client
        self._table = table
        self._d2db = display_to_db
        self._db2d = db_to_display
        self._cols = ordered_display

    # ── Normalización de nombres ────────────────────────────────────────────

    def _to_db(self, display_name: str) -> str:
        """Convierte nombre de UI a nombre de columna en DB."""
        name = str(display_name).strip()
        if name in ('_id', 'id', 'ID'):
            return 'id'
        if name in self._d2db:
            return self._d2db[name]
        # Búsqueda insensible a mayúsculas
        nl = name.lower()
        if nl in ('_id', 'id'):
            return 'id'
        for k, v in self._d2db.items():
            if k.lower() == nl:
                return v
        # Fallback: lowercase con guion bajo
        return name.lower().replace(' ', '_').replace('°', '').replace('n°_', 'numero_')

    def _row_to_display(self, db_row: dict) -> dict:
        """Convierte un registro de DB a dict con nombres de UI, preservando _id."""
        result = {}
        for db_col, val in db_row.items():
            if db_col == 'id':
                result['_id'] = val
                continue
            display = self._db2d.get(db_col, db_col)
            result[display] = val if val is not None else ''
        return result

    def delete_by_id(self, record_id):
        """Elimina un registro específico por su ID primario."""
        try:
            self._client.table(self._table).delete().eq('id', record_id).execute()
            return True
        except Exception as e:
            print(f"[SupabaseSheet] delete_by_id '{self._table}': {e}")
            raise e

    def delete_records(self, filters: dict):
        """Elimina registros que coincidan con un conjunto de filtros clave=valor."""
        try:
            q = self._client.table(self._table).delete()
            for col, val in filters.items():
                db_col = self._d2db.get(col, col.lower())
                q = q.eq(db_col, val)
            q.execute()
            return True
        except Exception as e:
            print(f"[SupabaseSheet] delete_records '{self._table}': {e}")
            raise e

    # ── Métodos principales ────────────────────────────────────────────────

    def get_all_records(self, **kwargs) -> list:
        """Devuelve todos los registros como lista de dicts con nombres de UI (paginado para superar límites de PostgREST)."""
        try:
            PAGE_SIZE = 1000
            offset = 0
            all_rows = []
            while True:
                resp = self._client.table(self._table).select("*").range(offset, offset + PAGE_SIZE - 1).execute()
                batch = resp.data or []
                all_rows.extend(batch)
                if len(batch) < PAGE_SIZE:
                    break
                offset += PAGE_SIZE
            return [self._row_to_display(r) for r in all_rows]
        except Exception as e:
            print(f"[SupabaseSheet] get_all_records '{self._table}': {e}")
            return []


    def clear(self):
        """Elimina todos los registros de la tabla (con blindaje de seguridad en tablas críticas)."""
        # BLINDAJE DE SEGURIDAD ESTRICTO:
        # Prevenir vaciado ciego en tablas sensibles de la escuela (notas, asistencia, alumnos, etc.)
        # para que un error en el flujo jamás borre registros masivamente.
        tablas_protegidas = ['notas', 'asistencia', 'registros', 'alumnos', 'funcionarios']
        if self._table in tablas_protegidas:
            print(f"[SupabaseSheet] BLINDAJE DE SEGURIDAD: clear() masivo bloqueado en tabla crítica '{self._table}'. Los cambios se realizan de forma atómica y quirúrgica.")
            return

        try:
            self._client.table(self._table).delete().gte('id', 0).execute()
        except Exception as e:
            print(f"[SupabaseSheet] clear '{self._table}': {e}")

    def update(self, values, range_name=None):
        """
        Compatibilidad con gspread sheet.update(values=[headers] + rows).
        Si se pasa range_name y values tiene 1 fila, es una actualización de fila puntual.
        """
        if not values:
            return

        # Caso 1: Actualización de fila individual (ej: sheet_notas.update(values=[fila_data], range_name='A5:P5'))
        if len(values) == 1 and range_name:
            row = values[0]
            record = {}
            for i, display_col in enumerate(self._cols):
                db_col = self._d2db.get(display_col, display_col.lower())
                if db_col == 'id':
                    continue
                val = row[i] if i < len(row) else None
                if val is None or str(val).strip() in ('', 'nan', 'None', 'NaT', 'NULL'):
                    record[db_col] = None
                else:
                    if self._table == 'notas' and db_col in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n10', 'promedio']:
                        val_str = str(val).strip().upper()
                        if val_str == 'MB':
                            record[db_col] = 7.0
                        elif val_str == 'B':
                            record[db_col] = 5.5
                        elif val_str == 'S':
                            record[db_col] = 4.5
                        elif val_str == 'I':
                            record[db_col] = 3.0
                        else:
                            try:
                                record[db_col] = float(val_str.replace(',', '.'))
                            except ValueError:
                                record[db_col] = None
                    else:
                        record[db_col] = val

            try:
                if self._table == 'notas':
                    self._client.table(self._table).upsert(record, on_conflict='rut,asignatura,semestre').execute()
                elif self._table == 'asistencia':
                    self._client.table(self._table).upsert(record, on_conflict='fecha,curso,tipo').execute()
                elif self._table == 'alumnos':
                    self._client.table(self._table).upsert(record, on_conflict='rut').execute()
                elif self._table == 'funcionarios':
                    self._client.table(self._table).upsert(record, on_conflict='rut').execute()
                else:
                    self._client.table(self._table).insert(record).execute()
            except Exception as e:
                print(f"[SupabaseSheet] update single-row '{self._table}': {e}")
                raise e
            return

        if len(values) < 2:
            return

        headers = [str(h).strip() for h in values[0]]
        data_rows = values[1:]
        records = []
        for row in data_rows:
            padded = list(row) + [''] * len(headers)
            record = {}
            skip = True
            for i, h in enumerate(headers):
                db_col = self._to_db(h)
                if db_col in ('id', '_id'):
                    continue
                val = padded[i]
                # Normalizar None y cadenas vacías
                if val is None or str(val).strip() in ('', 'nan', 'None', 'NaT', 'NULL'):
                    record[db_col] = None
                else:
                    if self._table == 'notas' and db_col in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n10', 'promedio']:
                        val_str = str(val).strip().replace(',', '.')
                        try:
                            record[db_col] = float(val_str)
                        except ValueError:
                            record[db_col] = str(val).strip()
                    else:
                        record[db_col] = val
                    skip = False
            if not skip:
                records.append(record)

        if records:
            try:
                # Insertar en lotes de 500 para evitar límites de payload
                BATCH = 500
                for i in range(0, len(records), BATCH):
                    batch_data = records[i:i+BATCH]
                    if self._table == 'notas':
                        self._client.table(self._table).upsert(batch_data, on_conflict='rut,asignatura,semestre').execute()
                    elif self._table == 'asistencia':
                        self._client.table(self._table).upsert(batch_data, on_conflict='fecha,curso,tipo').execute()
                    elif self._table == 'alumnos':
                        self._client.table(self._table).upsert(batch_data, on_conflict='rut').execute()
                    elif self._table == 'funcionarios':
                        self._client.table(self._table).upsert(batch_data, on_conflict='rut').execute()
                    else:
                        self._client.table(self._table).insert(batch_data).execute()
            except Exception as e:
                print(f"[SupabaseSheet] update '{self._table}': {e}")
                raise e

    def append_row(self, row_values, **kwargs):
        """Inserta o actualiza una fila usando el orden de columnas predefinido."""
        try:
            record = {}
            for i, display_col in enumerate(self._cols):
                db_col = self._d2db.get(display_col, display_col.lower())
                if db_col == 'id':
                    continue
                val = row_values[i] if i < len(row_values) else None
                if val is None or str(val).strip() in ('', 'nan', 'None', 'NaT', 'NULL'):
                    record[db_col] = None
                else:
                    if self._table == 'notas' and db_col in ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8', 'n9', 'n10', 'promedio']:
                        val_str = str(val).strip().upper()
                        if val_str == 'MB':
                            record[db_col] = 7.0
                        elif val_str == 'B':
                            record[db_col] = 5.5
                        elif val_str == 'S':
                            record[db_col] = 4.5
                        elif val_str == 'I':
                            record[db_col] = 3.0
                        else:
                            try:
                                record[db_col] = float(val_str.replace(',', '.'))
                            except ValueError:
                                record[db_col] = None
                    else:
                        record[db_col] = val

            if self._table == 'notas':
                self._client.table(self._table).upsert(record, on_conflict='rut,asignatura,semestre').execute()
            elif self._table == 'asistencia':
                self._client.table(self._table).upsert(record, on_conflict='fecha,curso,tipo').execute()
            elif self._table == 'alumnos':
                self._client.table(self._table).upsert(record, on_conflict='rut').execute()
            elif self._table == 'funcionarios':
                self._client.table(self._table).upsert(record, on_conflict='rut').execute()
            else:
                self._client.table(self._table).insert(record).execute()
        except Exception as e:
            print(f"[SupabaseSheet] append_row '{self._table}': {e}")
            raise e

    def append_rows(self, rows_values, **kwargs):
        """Inserta o actualiza múltiples filas."""
        for row in rows_values:
            self.append_row(row)

    def row_values(self, n: int) -> list:
        """Para n=1 devuelve los nombres de columnas UI; para n>1 devuelve []."""
        if n == 1:
            return list(self._cols)
        return []

    def get_all_values(self) -> list:
        """Devuelve todos los datos como lista de listas [headers] + [rows]."""
        records = self.get_all_records()
        if not records:
            return [list(self._cols)]
        rows = [[r.get(h, '') for h in self._cols] for r in records]
        return [list(self._cols)] + rows

    def find(self, query, in_column=None):
        """Búsqueda básica. Devuelve None si no encuentra (compatibilidad)."""
        return None

    def __bool__(self):
        """Permite usar `if sheet_alumnos:` como en el código original."""
        return True


# ─────────────────────────────────────────────────────────────────────────────
# MAPEOS DE COLUMNAS POR TABLA
# Formato: "Nombre en UI" → "columna_en_db"
# ─────────────────────────────────────────────────────────────────────────────

def _make_sheet(client, table, mapping):
    """Crea un SupabaseSheet a partir de un mapping {display: db}."""
    db_to_display = {v: k for k, v in mapping.items()}
    ordered = list(mapping.keys())
    return SupabaseSheet(client, table, mapping, db_to_display, ordered)


ALUMNOS_MAP = {
    "N° Lista":            "numero_lista",
    "N° Matrícula":        "numero_matricula",
    "RUT":                 "rut",
    "Nombre":              "nombre",
    "Curso":               "curso",
    "Fecha Nacimiento":    "fecha_nacimiento",
    "Fecha Matrícula":     "fecha_matricula",
    "Fecha Alta":          "fecha_ingreso",
    "Fecha Baja":          "fecha_baja",
    "Estado":              "estado",
    "Teléfono Apoderado":  "telefono_apoderado",
}

REGISTROS_MAP = {
    "Fecha":       "fecha",
    "Hora":        "hora",
    "RUT":         "rut",
    "Nombre":      "nombre",
    "Tipo":        "tipo",
    "Motivo":      "motivo",
    "Apoderado":   "apoderado",
    "Vinculo":     "vinculo",
    "Curso":       "curso",
}

NOTAS_MAP = {
    "RUT":        "rut",
    "Nombre":     "nombre",
    "Curso":      "curso",
    "Asignatura": "asignatura",
    "Semestre":   "semestre",
    "N1":  "n1",  "N2":  "n2",  "N3":  "n3",
    "N4":  "n4",  "N5":  "n5",  "N6":  "n6",
    "N7":  "n7",  "N8":  "n8",  "N9":  "n9",
    "N10": "n10", "Promedio": "promedio",
}

FUNCIONARIOS_MAP = {
    "RUT":    "rut",
    "Nombre": "nombre",
    "Rol":    "rol",
    "PIN":    "pin",
    "Estado": "estado",
}

ASIGNACIONES_MAP = {
    "RUT_Profesor":    "rut_profesor",
    "Nombre_Profesor": "nombre_profesor",
    "Curso":           "curso",
    "Asignatura":      "asignatura",
}

ASISTENCIA_MAP = {
    "Fecha": "fecha",
    "Curso": "curso",
    "Datos": "datos",
    "Tipo":  "tipo",
}

CONFIG_MAP = {
    "Clave": "clave",
    "Valor": "valor",
}

PREACTA_MAP = {
    "Año":              "anio",
    "Curso":            "curso",
    "RUT":              "rut",
    "Nombre":           "nombre",
    "Promedio_General": "promedio_general",
    "Asistencia":       "asistencia",
    "Situacion_Final":  "situacion_final",
    "Observaciones":    "observaciones",
    "Fecha_Cierre":     "fecha_cierre",
}

DESARROLLO_PERSONAL_MAP = {
    "Año":             "anio",
    "Periodo":         "periodo",
    "Curso":           "curso",
    "RUT":             "rut",
    "Nombre":          "nombre",
    "C1":  "c1",  "C2":  "c2",  "C3":  "c3",
    "C4":  "c4",  "C5":  "c5",  "C6":  "c6",
    "C7":  "c7",  "C8":  "c8",  "C9":  "c9",
    "C10": "c10", "C11": "c11", "C12": "c12",
    "Observaciones":   "observaciones",
    "Fecha_Registro":  "fecha_registro",
}

CURSOS_MAP = {
    "Nombre":           "nombre",
    "Letra":            "letra",
    "Profesor_Jefe":    "profesor_jefe",
    "RUT_Profesor_Jefe":"rut_profesor_jefe",
}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES PÚBLICAS (mismas firmas que el database.py original con gspread)
# ─────────────────────────────────────────────────────────────────────────────

def get_sheets():
    """
    Devuelve los objetos SupabaseSheet para las 5 tablas principales.
    Firma idéntica al original: (sheet_alumnos, sheet_registros, sheet_notas,
                                  sheet_funcionarios, sheet_asignaciones)
    """
    try:
        client = get_supabase_client()
        sheet_alumnos      = _make_sheet(client, "alumnos",      ALUMNOS_MAP)
        sheet_registros    = _make_sheet(client, "registros",    REGISTROS_MAP)
        sheet_notas        = _make_sheet(client, "notas",        NOTAS_MAP)
        sheet_funcionarios = _make_sheet(client, "funcionarios", FUNCIONARIOS_MAP)
        sheet_asignaciones = _make_sheet(client, "asignaciones", ASIGNACIONES_MAP)
        return sheet_alumnos, sheet_registros, sheet_notas, sheet_funcionarios, sheet_asignaciones
    except Exception as e:
        print(f"[database] get_sheets error: {e}")
        return None, None, None, None, None


def get_asistencia_sheet():
    """Devuelve el SupabaseSheet para la tabla 'asistencia'."""
    try:
        client = get_supabase_client()
        return _make_sheet(client, "asistencia", ASISTENCIA_MAP)
    except Exception as e:
        print(f"[database] get_asistencia_sheet error: {e}")
        return None


def get_config_sheet():
    """Devuelve el SupabaseSheet para la tabla 'configuracion'."""
    try:
        client = get_supabase_client()
        return _make_sheet(client, "configuracion", CONFIG_MAP)
    except Exception as e:
        print(f"[database] get_config_sheet error: {e}")
        return None


def get_preacta_sheet():
    """Devuelve el SupabaseSheet para la tabla 'preacta'."""
    try:
        client = get_supabase_client()
        return _make_sheet(client, "preacta", PREACTA_MAP)
    except Exception as e:
        print(f"[database] get_preacta_sheet error: {e}")
        return None


def get_desarrollo_personal_sheet():
    """Devuelve el SupabaseSheet para la tabla 'desarrollo_personal'."""
    try:
        client = get_supabase_client()
        return _make_sheet(client, "desarrollo_personal", DESARROLLO_PERSONAL_MAP)
    except Exception as e:
        print(f"[database] get_desarrollo_personal_sheet error: {e}")
        return None


def get_cursos_sheet():
    """Devuelve el SupabaseSheet para la tabla 'cursos'."""
    try:
        client = get_supabase_client()
        return _make_sheet(client, "cursos", CURSOS_MAP)
    except Exception as e:
        print(f"[database] get_cursos_sheet error: {e}")
        return None
