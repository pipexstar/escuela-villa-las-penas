"""
utils/notifications.py — Servicio de Notificaciones Push para Portal de Apoderados
Envía notificaciones Web Push automáticas a los teléfonos de los apoderados
cuando se registra un atraso o retiro.
"""
import threading
import json
import streamlit as st
from pywebpush import webpush, WebPushException

def _enviar_push_a_suscripcion(sub_row, titulo, mensaje, url="/", priv_key=None, email=None, client=None):
    try:
        sub_info = {
            "endpoint": sub_row["endpoint"],
            "keys": {
                "p256dh": sub_row["p256dh"],
                "auth": sub_row["auth"]
            }
        }
        payload = json.dumps({
            "title": titulo,
            "body": mensaje,
            "url": url,
            "icon": "icons/icon-192.png",
            "badge": "icons/badge-72.png"
        })
        
        if not priv_key:
            try:
                priv_key = st.secrets.get("VAPID_PRIVATE_KEY")
            except Exception:
                pass
        if not email:
            try:
                email = st.secrets.get("VAPID_EMAIL", "mailto:escuelavillalaspenas@gmail.com")
            except Exception:
                email = "mailto:escuelavillalaspenas@gmail.com"
        
        if not priv_key:
            return

        webpush(
            subscription_info=sub_info,
            data=payload,
            vapid_private_key=priv_key,
            vapid_claims={"sub": email}
        )
    except WebPushException as ex:
        # Si la suscripción expiró o fue revocada en el teléfono (404/410), la limpiamos
        if hasattr(ex, "response") and ex.response is not None and ex.response.status_code in (404, 410):
            try:
                if client is None:
                    from utils.database import get_supabase_client
                    client = get_supabase_client()
                if client:
                    client.table("push_subscriptions").delete().eq("id", sub_row["id"]).execute()
            except Exception:
                pass
    except Exception:
        pass

def notificar_apoderados_rut(rut: str, titulo: str, mensaje: str, url: str = "/"):
    """
    Busca todas las suscripciones push vinculadas al RUT y envía la alerta en segundo plano.
    Captura credenciales en el hilo principal de Streamlit para evitar pérdidas de contexto.
    """
    try:
        from utils.database import get_supabase_client
        supabase_client = get_supabase_client()
        vapid_key = st.secrets.get("VAPID_PRIVATE_KEY")
        vapid_sub_email = st.secrets.get("VAPID_EMAIL", "mailto:escuelavillalaspenas@gmail.com")
    except Exception:
        supabase_client = None
        vapid_key = None
        vapid_sub_email = None

    def _worker(client, priv_key, email):
        try:
            if client is None:
                from utils.database import get_supabase_client
                client = get_supabase_client()
            
            rut_clean = str(rut).replace(".", "").strip().upper()
            
            # Buscar suscripciones asociadas a este RUT
            res = client.table("push_subscriptions").select("*").or_(f"rut.eq.{rut_clean},rut.eq.{rut}").execute()
            subs = res.data or []
            
            for sub in subs:
                _enviar_push_a_suscripcion(sub, titulo, mensaje, url, priv_key=priv_key, email=email, client=client)
        except Exception:
            pass

    threading.Thread(target=_worker, args=(supabase_client, vapid_key, vapid_sub_email), daemon=True).start()
