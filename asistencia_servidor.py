import os
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
import uvicorn
import toml
from supabase import create_client

from utils.asistencia_funcionarios import (
    procesar_escaneo_qr_supabase,
    generar_payload,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Cargar secrets
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
SECRETS = toml.load(SECRETS_PATH) if os.path.exists(SECRETS_PATH) else {}
SCANNER_PIN = SECRETS.get("scanner_access_key", "1234")

_supabase_client = None


def obtener_supabase():
    global _supabase_client
    if _supabase_client is None:
        url = SECRETS.get("SUPABASE_URL")
        key = SECRETS.get("SUPABASE_KEY")
        _supabase_client = create_client(url, key)
    return _supabase_client


async def vista_funcionario_pwa(request):
    ruta = os.path.join(TEMPLATES_DIR, "funcionario.html")
    with open(ruta, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


async def vista_tablet(request):
    ruta = os.path.join(TEMPLATES_DIR, "tablet.html")
    with open(ruta, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


async def servir_manifest(request):
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"), media_type="application/manifest+json")


async def servir_sw(request):
    return FileResponse(
        os.path.join(STATIC_DIR, "sw.js"),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


async def api_buscar_funcionario(request):
    rut = request.path_params.get("rut", "").strip()
    client = obtener_supabase()
    try:
        resp = client.table("funcionarios").select("rut, nombre, rol, estado").eq("rut", rut).limit(1).execute()
        if resp.data:
            f = resp.data[0]
            if str(f.get("estado", "")).lower() == "inactivo":
                return JSONResponse({"ok": False, "mensaje": f"El funcionario {f['nombre']} figura como Inactivo."}, status_code=400)
            return JSONResponse({"ok": True, "funcionario": {"id": f["rut"], "nombre": f["nombre"], "rol": f.get("rol", "")}})
        return JSONResponse({"ok": False, "mensaje": f"Funcionario con RUT {rut} no encontrado en la nómina."}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "mensaje": str(e)}, status_code=500)


async def api_generar_payload_qr(request):
    rut = request.path_params.get("rut", "").strip()
    client = obtener_supabase()
    try:
        resp = client.table("funcionarios").select("rut, nombre, rol, estado").eq("rut", rut).limit(1).execute()
        if not resp.data:
            return JSONResponse({"ok": False, "mensaje": f"RUT {rut} no encontrado."}, status_code=404)
        f = resp.data[0]
        payload = generar_payload(f["rut"])
        return JSONResponse({"ok": True, "payload": payload, "funcionario": {"id": f["rut"], "nombre": f["nombre"]}})
    except Exception as e:
        return JSONResponse({"ok": False, "mensaje": str(e)}, status_code=500)


async def api_scan(request):
    try:
        body = await request.json()
        payload = body.get("payload", "")
        tipo = body.get("tipo", "auto")
        resultado = procesar_escaneo_qr_supabase(payload, tipo_deseado=tipo)
        return JSONResponse(resultado)
    except Exception as e:
        return JSONResponse({"ok": False, "mensaje": f"Error procesando escaneo: {str(e)}"}, status_code=500)


async def api_verificar_pin(request):
    try:
        body = await request.json()
        pin = str(body.get("pin", "")).strip()
        if pin == str(SCANNER_PIN).strip():
            return JSONResponse({"ok": True})
        return JSONResponse({"ok": False, "mensaje": "PIN inválido."}, status_code=401)
    except Exception as e:
        return JSONResponse({"ok": False, "mensaje": str(e)}, status_code=400)


routes = [
    Route("/", endpoint=vista_funcionario_pwa, methods=["GET"]),
    Route("/manifest.json", endpoint=servir_manifest, methods=["GET"]),
    Route("/sw.js", endpoint=servir_sw, methods=["GET"]),
    Route("/tablet", endpoint=vista_tablet, methods=["GET"]),
    Route("/api/funcionario/{rut}", endpoint=api_buscar_funcionario, methods=["GET"]),
    Route("/api/qr-payload/{rut}", endpoint=api_generar_payload_qr, methods=["GET"]),
    Route("/api/scan", endpoint=api_scan, methods=["POST"]),
    Route("/api/verificar-pin", endpoint=api_verificar_pin, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory=STATIC_DIR), name="static"),
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 SERVIDOR ASISTENCIA SUPABASE - ESCUELA VILLA LAS PEÑAS")
    print("=" * 60)
    print("📱 Credencial Funcionario (PWA): http://0.0.0.0:8000/")
    print("📷 Escáner Tablet (Portería):    http://0.0.0.0:8000/tablet")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
