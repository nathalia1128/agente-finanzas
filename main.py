# main.py
import os
import tempfile
import httpx
from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from agent import procesar_mensaje
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

_historiales: dict[str, list] = {}

# Whisper activo si hay clave de Gemini
WHISPER_ACTIVO = bool(os.getenv("GEMINI_API_KEY"))

# ──────────────────────────────────────────
# Transcripción con Gemini (opcional)
# ──────────────────────────────────────────

async def transcribir_audio(media_url: str) -> str:
    """Descarga el audio de Twilio y lo transcribe con Gemini."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    async with httpx.AsyncClient() as http:
        response = await http.get(
            media_url,
            auth=(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        )

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=f.read(), mime_type="audio/ogg"),
                    "Transcribe exactamente lo que dice este audio en español. "
                    "Devuelve solo el texto transcrito, sin comentarios adicionales."
                ]
            )
        return response.text.strip()
    finally:
        os.unlink(tmp_path)
# ──────────────────────────────────────────
# Webhook principal de WhatsApp
# ──────────────────────────────────────────

@app.post("/whatsapp")
async def webhook_whatsapp(
    From: str  = Form(...),
    Body: str  = Form(""),
    MediaUrl0: str           = Form(None),
    MediaContentType0: str   = Form(None),
):
    numero    = From
    historial = _historiales.get(numero, [])[-20:]

    es_audio = (
        MediaUrl0 is not None
        and MediaContentType0 is not None
        and "audio" in MediaContentType0
    )

    if es_audio:
        if WHISPER_ACTIVO:
            try:
                texto_transcrito = await transcribir_audio(MediaUrl0)
                texto = f"[Audio transcrito]: {texto_transcrito}"
            except Exception:
                twiml = MessagingResponse()
                twiml.message("Recibí tu audio pero hubo un error al transcribirlo. Escríbeme el mensaje.")
                return Response(content=str(twiml), media_type="application/xml")
        else:
            twiml = MessagingResponse()
            twiml.message("Recibí tu audio pero la transcripción no está activa. Escríbeme el mensaje.")
            return Response(content=str(twiml), media_type="application/xml")
    else:
        texto = Body.strip()

    if not texto:
        twiml = MessagingResponse()
        twiml.message("No entendí el mensaje. ¿Puedes escribirlo de nuevo?")
        return Response(content=str(twiml), media_type="application/xml")

    try:
        respuesta_texto, historial_nuevo = procesar_mensaje(texto, historial)
        _historiales[numero] = historial_nuevo[-10:]
    except Exception as e:
        import traceback
        traceback.print_exc()

        # Limpiar historial en cualquier error y reintentar
        _historiales[numero] = []
        try:
            respuesta_texto, historial_nuevo = procesar_mensaje(texto, [])
            _historiales[numero] = historial_nuevo[-10:]
        except Exception as e2:
            traceback.print_exc()
            respuesta_texto = f"Error: {str(e2)}"

    twiml = MessagingResponse()
    twiml.message(respuesta_texto)
    return Response(content=str(twiml), media_type="application/xml")

@app.get("/health")
def health():
    return {"status": "ok"}