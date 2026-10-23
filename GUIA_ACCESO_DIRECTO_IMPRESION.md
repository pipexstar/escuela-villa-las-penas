# 🖨️ Guía Rápida: Configuración de Impresión Térmica Automática
**Escuela Villa Las Peñas**

Esta guía te permitirá dejar configurada la impresión automática del **Justificativo de Atrasos (8 cm x 8 cm)** sin que aparezca ninguna ventana emergente en pantalla.

---

### Paso 1: Configurar la Impresora Predeterminada en Windows
1. En el computador donde está conectada la ticketera, presiona la tecla `Windows` y escribe **Impresoras y escáneres**.
2. Busca tu **impresora térmica de 80mm**.
3. Haz clic sobre ella y selecciona **Establecer como predeterminada** (o *Administrar > Establecer como predeterminada*).

---

### Paso 2: Crear el Acceso Directo Silencioso en el Escritorio

#### Opción A (Recomendada - Google Chrome):
1. En el escritorio de Windows, haz **clic derecho** en un espacio vacío.
2. Selecciona **Nuevo > Acceso directo**.
3. En la casilla que dice *"Escriba la ubicación del elemento"*, copia y pega exactamente esto:

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk-printing --user-data-dir="%TEMP%\kiosk_escuela" "https://gestionescolarevlp.streamlit.app"
```

*(Si Chrome está instalado en 32 bits, la ruta es `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`)*.

4. Haz clic en **Siguiente**, ponle de nombre: `Sistema Escolar - Atrasos` y haz clic en **Finalizar**.

---

#### Opción B (Si utilizas Microsoft Edge):
Si en ese equipo navegan con Microsoft Edge, el comando en el acceso directo es:

```cmd
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk-printing --user-data-dir="%TEMP%\kiosk_escuela" "https://gestionescolarevlp.streamlit.app"
```

---

### ¿Cómo funcionará a partir de ese momento?
* Cada vez que abras el sistema desde ese acceso directo, al presionar **"Confirmar Registro de Atraso"**, la impresora térmica cortará el papel de **8x8 cm** en menos de 1 segundo de forma totalmente automática y silenciosa.
