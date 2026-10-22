# Plan y Diseño Aprobado: Modernización Módulos Alumnos y Funcionarios

Este documento registra los acuerdos de diseño y la arquitectura acordada para continuar el desarrollo del sistema escolar en cualquier sesión.

---

## 1. Módulo: Alumnos (`main.py` -> `elif current_module == 'alumnos':`)
### Estructura de la Pantalla:
- **Pestañas superiores (Separación limpia):**
  1. `📋 Gestión y Ficha de Alumnos` (Pantalla principal)
  2. `📤 Carga Masiva (Excel / CSV)` (Separada para evitar scroll y ruido visual)

### En la pestaña principal (`📋 Gestión y Ficha de Alumnos`):
- **Barra de filtros superior:**
  - Selector de Curso (`1° Básico`, `2° Básico`, ... y opción especial `"🔍 Todos los Cursos (Búsqueda Global)"`).
  - Campo de búsqueda instantánea: `🔍 Buscar por Nombre o RUT` (permite encontrar un alumno al instante sin saber el curso).
  - Casilla/Filtro rápido: `[x] Ocultar retirados` (muestra solo alumnos activos por defecto).
- **Diseño Master-Detail (2 Columnas):**
  - **Columna Izquierda (Tabla Interactiva):**
    - Se elimina el dropdown repetitivo de alumnos.
    - Se usa selección por fila en la tabla.
    - Muestra: `N° Lista`, `RUT`, `Nombre`, `Curso` (si es búsqueda global), `Estado`.
    - Botón visible arriba: `➕ Nuevo Alumno` (limpia el formulario para registrar uno nuevo en el curso seleccionado).
  - **Columna Derecha (Ficha de Edición en Vivo):**
    - Al hacer **clic en cualquier fila de la tabla**, se cargan automáticamente los datos del alumno.
    - **`RUT`:** Se muestra visible pero **bloqueado (`disabled=True`)**, para evitar inconsistencias históricas en notas o asistencia.
    - Campos editables: `N° Lista`, `Nombre Completo`, `Estado (Activo / Retirado)`, `Teléfono Apoderado`, `Fecha Nacimiento`, `Fecha Ingreso`.
    - Botón: `💾 Guardar Cambios`.
    - Sección desplegable protegida: `🗑️ Eliminar Alumno` (con advertencia y confirmación).

---

## 2. Módulo: Funcionarios (`main.py` -> `elif current_module == 'funcionarios':`)
### Estructura de la Pantalla:
- **Pestañas superiores:**
  1. `📋 Nómina de Funcionarios y Claves`
  2. `📤 Carga Masiva (Excel / CSV)`

### En la pestaña principal (`📋 Nómina de Funcionarios`):
- **Barra de filtros superior (Escalabilidad para 50+ profesores):**
  - Campo de búsqueda en vivo: `🔍 Buscar por Nombre o RUT`.
  - Filtro por Rol: `[Todos | Solo Profesores | Solo Inspectores | Equipo Directivo]`.
- **Diseño Master-Detail (2 Columnas):**
  - **Columna Izquierda (Tabla Interactiva):**
    - Se elimina el dropdown repetitivo.
    - Selección directa por fila en tabla.
    - Muestra: `RUT`, `Nombre`, `Rol`, `Estado`.
    - Botón visible arriba: `➕ Nuevo Funcionario`.
  - **Columna Derecha (Ficha de Edición):**
    - Al hacer clic en un funcionario de la tabla, se carga su información al instante.
    - **`RUT`:** Mostrado pero **bloqueado (`disabled=True`)**.
    - Campos editables: `Nombre Completo`, `Rol Institucional`, `Clave PIN (4 dígitos)`, `Estado (Activo / Inactivo)`.
    - Botón: `💾 Guardar Cambios`.
    - Eliminación protegida: no permite borrar la cuenta `admin`.

---

## 3. Módulo: Cursos (`main.py` -> `elif current_module == 'cursos':`)
### Estructura de la Pantalla:
- **Pestañas superiores (Solo 2 pestañas limpias):**
  1. `📋 Cursos Actuales` (Listado con su letra oficial `A`, `B`, etc. y edición de Profesor Jefe)
  2. `➕ Crear Nuevo Curso` (Formulario con nivel oficial desplegable y letra oficial `A`, `B`, `C`, `D` + Profesor Jefe)

### Estándar Oficial con Letra:
- Todos los cursos del sistema se denominan oficialmente integrando su nivel y letra (ej: `1° Básico A`, `NT1 A`), coincidiendo con los estudiantes y eliminando duplicados en todos los selectores.
- En la creación, el usuario selecciona el nivel (ej: `1° Básico`) y la letra (ej: `A`), registrándose automáticamente como `1° Básico A`.

### En la pestaña principal (`📋 Cursos Actuales`):
- **Buscador en vivo superior:**
  - `🔍 Buscar Curso` (filtro instantáneo por nombre o profesor jefe).
- **Diseño Master-Detail (2 Columnas):**
  - **Columna Izquierda (Tabla):**
    - Muestra: `Curso` (ej. `1° Básico A`), `Letra` (`A`), `Profesor(a) Jefe`.
    - Selección por fila.
  - **Columna Derecha (Ficha de Edición):**
    - Campos: `Curso Oficial` y `Letra` (bloqueados para proteger consistencia) y `Profesor(a) Jefe` (dropdown dinámico de profesores activos).
    - Botón: `💾 Guardar Jefatura` (sincroniza automáticamente la jefatura en la pestaña `Asignaciones`).
    - Popover: `🗑️ Eliminar` (elimina el curso del catálogo).

### Validación Estricta y Mapeo en Carga Masiva:
- Al subir el Excel/CSV de alumnos, el sistema soporta archivos con o sin letra (mapea `1° Básico` a `1° Básico A` automáticamente) y valida que pertenezcan al catálogo oficial.

---

## 4. Reglas y Restricciones del Proyecto
1. **NO abrir navegador automáticamente:** El usuario prueba manualmente.
2. **RUT de ejemplo en código/placeholders:** Usar siempre genéricos como `12345678-9`, nunca datos personales.
3. **Backend:** Google Sheets a través de `utils/database.py`.
