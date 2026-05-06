# gmail_monitor.py
import os
import base64
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

REMITENTES_HOGAR = {
    "factura.virtual@clientescol.enel.com":  "⚡ Luz (Enel)",
    "facturacioncolombia@grupovanti.com":     "🔥 Gas (Vanti)",
    "facturavirtual@acueducto.com.co":        "💧 Agua (Acueducto)",
    "facturaelectronica@etbtufactura.com":    "🌐 Internet (ETB)",
    "wilsonfox18@hotmail.com":               "👤 Wilson",
}

# Reemplaza PATRONES_MONTO
PATRONES_MONTO = [
    r"monto[:\s]+\$?([\d.,]+)",   # formato Gemini: "MONTO: 85000"
    r"total\s+a\s+pagar[:\s]+\$?([\d.,]+)",
    r"valor\s+a\s+pagar[:\s]+\$?([\d.,]+)",
    r"valor\s+factura[:\s]+\$?([\d.,]+)",
    r"total\s+factura[:\s]+\$?([\d.,]+)",
    r"monto\s+a\s+pagar[:\s]+\$?([\d.,]+)",
    r"pague[:\s]+\$?([\d.,]+)",
    r"tu\s+factura\s+es\s+de[:\s]+\$?([\d.,]+)",
    r"valor\s+total[:\s]+\$?([\d.,]+)",
    r"\$\s*([\d]{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?)",
]

# Reemplaza PATRONES_FECHA
PATRONES_FECHA = [
    r"fecha[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",  # formato Gemini
    r"fecha\s+(?:l[ií]mite|vencimiento|de\s+pago|l[íi]mite\s+de\s+pago)[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    r"vence[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    r"pagar\s+antes\s+del[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    r"fecha\s+l[íi]mite[:\s]+(\d{1,2}\s+\w+[\/\-]\d{2,4})",
    r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
    # Formato Enel: "29 ABR/2026" o "15 MAY/2026"
    r"(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[\/\-]\d{4})",
    r"fecha[:\s]+(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[\/\-]\d{4})",
]

def _extraer_texto_adjuntos(payload, service, message_id: str) -> str:
    """Extrae texto de adjuntos — soporta PDF, imagen JPEG y ZIP con PDF adentro."""
    texto = ""

    if "parts" in payload:
        for part in payload["parts"]:
            mime      = part.get("mimeType", "")
            att_id    = part.get("body", {}).get("attachmentId")

            if att_id and mime in ("image/jpeg", "image/png"):
                # Factura como imagen — leer con Gemini
                try:
                    attachment = service.users().messages().attachments().get(
                        userId="me", messageId=message_id, id=att_id
                    ).execute()
                    import base64
                    data = attachment.get("data", "")
                    if data:
                        img_bytes = base64.urlsafe_b64decode(data + "==")
                        texto += _extraer_imagen_con_gemini(img_bytes, mime)
                except Exception:
                    pass

            elif att_id and mime == "application/zip":
                # ZIP — descomprimir y buscar PDF adentro
                try:
                    attachment = service.users().messages().attachments().get(
                        userId="me", messageId=message_id, id=att_id
                    ).execute()
                    import base64, zipfile, io
                    data = attachment.get("data", "")
                    if data:
                        zip_bytes = base64.urlsafe_b64decode(data + "==")
                        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                            for nombre_archivo in z.namelist():
                                if nombre_archivo.lower().endswith(".pdf"):
                                    pdf_bytes  = z.read(nombre_archivo)
                                    texto_pdf  = ""
                                    try:
                                        import pypdf
                                        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                                        for page in reader.pages:
                                            texto_pdf += page.extract_text() or ""
                                    except Exception:
                                        pass
                                    if len(texto_pdf.strip()) < 50:
                                        texto_pdf = _extraer_pdf_con_gemini(pdf_bytes)
                                    texto += texto_pdf
                except Exception:
                    pass

            elif att_id and mime == "application/pdf":
                # PDF directo
                try:
                    attachment = service.users().messages().attachments().get(
                        userId="me", messageId=message_id, id=att_id
                    ).execute()
                    import base64, io
                    data = attachment.get("data", "")
                    if data:
                        pdf_bytes = base64.urlsafe_b64decode(data + "==")
                        texto_pdf = ""
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                            for page in reader.pages:
                                texto_pdf += page.extract_text() or ""
                        except Exception:
                            pass
                        if len(texto_pdf.strip()) < 50:
                            texto_pdf = _extraer_pdf_con_gemini(pdf_bytes)
                        texto += texto_pdf
                except Exception:
                    pass

            # Recursar en partes anidadas
            texto += _extraer_texto_adjuntos(part, service, message_id)

    return texto

def _extraer_pdf_con_gemini(pdf_bytes: bytes) -> str:
    import os
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return ""
    try:
        from google import genai
        from google.genai import types
        import tempfile

        client = genai.Client(api_key=gemini_key)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=f.read(), mime_type="application/pdf"),
                    "Extrae el monto total a pagar y la fecha límite de pago de esta factura. "
                    "Devuelve solo esos datos en formato: MONTO: xxx FECHA: xxx"
                ]
            )
        os.unlink(tmp_path)
        return response.text.strip()
    except Exception:
        return ""


def _extraer_imagen_con_gemini(img_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    import os
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return ""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                "Extrae el monto total a pagar y la fecha límite de pago de esta factura. "
                "Devuelve solo esos datos en formato: MONTO: xxx FECHA: xxx"
            ]
        )
        return response.text.strip()
    except Exception:
        return ""

def _extraer_html_email(payload) -> str:
    """Extrae el HTML crudo del correo."""
    mime = payload.get("mimeType", "")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
    if "parts" in payload:
        for part in payload["parts"]:
            resultado = _extraer_html_email(part)
            if resultado:
                return resultado
    return ""


def _extraer_datos_con_gemini(html: str) -> str:
    """Manda el HTML del correo a Gemini para extraer monto y fecha."""
    import os
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return ""
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)

        # Limpiar el HTML para reducir tokens
        texto_limpio = re.sub(r"<[^>]+>", " ", html)
        texto_limpio = re.sub(r"\s+", " ", texto_limpio).strip()[:3000]

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=(
                f"Del siguiente texto de una factura de servicio público, "
                f"extrae el monto total a pagar y la fecha límite de pago. "
                f"Responde SOLO en este formato exacto:\n"
                f"MONTO: [número sin símbolos]\n"
                f"FECHA: [fecha]\n\n"
                f"Texto: {texto_limpio}"
            )
        )
        return response.text.strip()
    except Exception:
        return ""

def _get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def _extraer_texto_email(payload) -> str:
    texto    = ""
    mime     = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            texto = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
    elif mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html  = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
            texto = re.sub(r"<[^>]+>", " ", html)
            texto = re.sub(r"\s+", " ", texto)
    elif "parts" in payload:
        for part in payload["parts"]:
            texto += _extraer_texto_email(part)
    return texto

def _limpiar_monto(raw: str) -> float | None:
    raw = raw.strip().replace(" ", "")
    if re.match(r"^\d{1,3}(\.\d{3})+$", raw):
        return float(raw.replace(".", ""))
    if re.match(r"^\d{1,3}(,\d{3})+$", raw):
        return float(raw.replace(",", ""))
    if re.match(r"^\d+$", raw):
        return float(raw)
    return None

def _extraer_monto(texto: str) -> float | None:
    texto_lower = texto.lower()
    for patron in PATRONES_MONTO:
        match = re.search(patron, texto_lower, re.IGNORECASE)
        if match:
            valor = _limpiar_monto(match.group(1))
            if valor and valor > 1000:
                return valor
    return None

def _extraer_fecha_vencimiento(texto: str) -> str | None:
    texto_lower = texto.lower()
    for patron in PATRONES_FECHA:
        match = re.search(patron, texto_lower, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def _normalizar_remitente(header_from: str) -> str | None:
    match = re.search(r"[\w.\-+]+@[\w.\-]+", header_from.lower())
    if match:
        email = match.group(0)
        if email in REMITENTES_HOGAR:
            return email
    return None

def revisar_correos_nuevos(horas_atras: int = 24) -> list[dict]:
    service    = _get_gmail_service()
    from_query = " OR ".join([f"from:{e}" for e in REMITENTES_HOGAR])
    query      = f"({from_query}) newer_than:{horas_atras}h"

    results  = service.users().messages().list(
        userId="me", q=query, maxResults=20
    ).execute()
    mensajes = results.get("messages", [])
    if not mensajes:
        return []

    facturas = []
    for msg in mensajes:
        detalle = service.users().messages().get(
    userId="me", id=msg["id"], format="full"
).execute()

        headers          = {h["name"]: h["value"] for h in detalle["payload"]["headers"]}
        remitente_raw    = headers.get("From", "")
        email_remitente  = _normalizar_remitente(remitente_raw)
        if not email_remitente:
            continue

        texto = _extraer_texto_email(detalle["payload"])

        # Si el texto es muy corto, buscar en adjuntos
        if len(texto.strip()) < 50:
            texto_adjunto = _extraer_texto_adjuntos(detalle["payload"], service, msg["id"])
            if texto_adjunto:
                texto = texto_adjunto

        # Si sigue sin datos útiles, mandar el HTML completo a Gemini
        if len(texto.strip()) < 50 or (_extraer_monto(texto) is None):
            html_texto = _extraer_html_email(detalle["payload"])
            if html_texto and len(html_texto) > 100:
                texto_gemini = _extraer_datos_con_gemini(html_texto)
                if texto_gemini:
                    texto = texto_gemini
        monto  = _extraer_monto(texto)
        fecha  = _extraer_fecha_vencimiento(texto)

        facturas.append({
            "remitente": email_remitente,
            "nombre":    REMITENTES_HOGAR[email_remitente],
            "asunto":    headers.get("Subject", "(sin asunto)"),
            "monto":     monto,
            "fecha_vencimiento": fecha,
            "extraido":  monto is not None,
        })
    return facturas