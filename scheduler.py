# scheduler.py
import os
import sys
import schedule
import time
from datetime import date
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
import notion_db as nc
from gmail_monitor import revisar_correos_nuevos

load_dotenv()

twilio     = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MI_NUMERO  = os.getenv("MI_WHATSAPP_NUMBER")
BOT_NUMERO = os.getenv("TWILIO_WHATSAPP_NUMBER")

UMBRAL_ALERTA = 0.80  # avisa al 80% de uso del presupuesto

def _cop(valor: float) -> str:
    return f"${int(valor):,}".replace(",", ".")

def enviar_whatsapp(mensaje: str):
    twilio.messages.create(body=mensaje, from_=BOT_NUMERO, to=MI_NUMERO)

# ──────────────────────────────────────────
# Alertas de deudas
# ──────────────────────────────────────────

def alerta_deudas_proximas(dias: int):
    proximas = nc.deudas_proximas(dias)
    if not proximas:
        return

    lineas = [f"🔔 Pagos que vencen en {dias} días:\n"]
    for d in proximas:
        if d.get("tabla") == "familiar":
            dueno = d.get("dueno", "familiar")
            origen = f"👨‍👩‍👧 {dueno}"
        else:
            origen = "👤 tuyo"

        fijo = " (fijo)" if d.get("es_fijo") else ""
        lineas.append(
            f"• {d['gasto']}{fijo} — {origen}\n"
            f"  Cuota: {_cop(d['monto_final'])} | "
            f"Vence: {d['fecha']}"
            + (f" | Quedan: {d['pagos_restantes']} pagos" if not d.get("es_fijo") else "")
        )

    enviar_whatsapp("\n".join(lineas))

# ──────────────────────────────────────────
# Alertas de presupuesto
# ──────────────────────────────────────────

def alerta_presupuesto():
    categorias = nc.leer_presupuesto()
    mensajes_exceso      = []
    mensajes_preventivos = []

    for c in categorias:
        destinado  = c["valor_destinado"]
        disponible = c["presupuesto"]
        nombre     = c["nombre"]
        alerta     = c["alerta"]

        if destinado <= 0:
            continue

        comprometido = destinado - disponible
        porcentaje   = comprometido / destinado if destinado > 0 else 0

        if alerta == "😭":
            # Notion confirma que se pasó
            exceso = abs(disponible) if disponible < 0 else comprometido - destinado
            mensajes_exceso.append(
                f"🚨 {nombre}: presupuesto excedido\n"
                f"   Destinado {_cop(destinado)} | Comprometido {_cop(comprometido)}"
            )
        elif alerta == "👍" or alerta == "😁":
            # Notion dice que está bien — no alertar sin importar el porcentaje
            continue
        elif porcentaje >= UMBRAL_ALERTA:
            # Notion no marcó alerta pero estamos cerca del límite
            mensajes_preventivos.append(
                f"⚠️ {nombre}: vas al {int(porcentaje * 100)}%\n"
                f"   Te quedan {_cop(disponible)} de {_cop(destinado)}"
            )

    if mensajes_exceso:
        enviar_whatsapp("💸 Presupuesto excedido:\n\n" + "\n\n".join(mensajes_exceso))
    if mensajes_preventivos:
        enviar_whatsapp("💰 Alerta de presupuesto:\n\n" + "\n\n".join(mensajes_preventivos))
# ──────────────────────────────────────────
# Alertas de facturas (Gmail)
# ──────────────────────────────────────────

def alerta_facturas_hogar():
    facturas = revisar_correos_nuevos(horas_atras=48)
    if not facturas:
        return

    lineas = ["🏠 Facturas del hogar recibidas:\n"]
    for f in facturas:
        if f["extraido"]:
            fecha_str = f" | Vence: {f['fecha_vencimiento']}" if f["fecha_vencimiento"] else ""
            monto_str = f"${int(f['monto']):,}".replace(",", ".")
            lineas.append(f"{f['nombre']}\n  💵 {monto_str}{fecha_str}")
        else:
            lineas.append(
                f"{f['nombre']}\n"
                f"  ⚠️ No pude leer el monto — revisa: \"{f['asunto'][:40]}\""
            )

    enviar_whatsapp("\n\n".join(lineas))

# ──────────────────────────────────────────
# Revisión diaria completa
# ──────────────────────────────────────────

def revisar_todo():
    print(f"[{date.today()}] Iniciando revisión diaria...")
    alerta_deudas_proximas(7)
    alerta_deudas_proximas(3)
    alerta_presupuesto()
    alerta_facturas_hogar()
    print(f"[{date.today()}] Revisión completada.")

# ──────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────

if __name__ == "__main__":
    if "--once" in sys.argv:
        # Modo GitHub Actions: corre una vez y termina
        revisar_todo()
    else:
        # Modo local: loop para desarrollo
        print("Scheduler activo — revisión diaria a las 8:00am")
        revisar_todo()  # ejecutar al arrancar para verificar
        schedule.every().day.at("08:00").do(revisar_todo)
        while True:
            schedule.run_pending()
            time.sleep(60)