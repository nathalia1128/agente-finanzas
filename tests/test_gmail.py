from dotenv import load_dotenv
load_dotenv()
import os
from twilio.rest import Client as TwilioClient
from gmail_monitor import revisar_correos_nuevos

# Parchear scheduler para usar 72h en lugar de 24h
import scheduler
def alerta_test():
    facturas = revisar_correos_nuevos(horas_atras=72)
    print(f"[debug] facturas: {len(facturas)}")
    if not facturas:
        print("Sin facturas — no se envía nada")
        return

    lineas = ["🏠 Facturas del hogar recibidas:\n"]
    for f in facturas:
        if f["extraido"]:
            fecha_str = f" | Vence: {f['fecha_vencimiento']}" if f["fecha_vencimiento"] else ""
            lineas.append(f"{f['nombre']}\n  💵 ${int(f['monto']):,}{fecha_str}".replace(",", "."))
        else:
            lineas.append(f"{f['nombre']}\n  ⚠️ No pude leer el monto")

    mensaje = "\n\n".join(lineas)
    print(f"Enviando:\n{mensaje}")

    twilio    = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    twilio.messages.create(
        body=mensaje,
        from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
        to=os.getenv("MI_WHATSAPP_NUMBER")
    )
    print("Enviado")

alerta_test()