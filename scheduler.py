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

def _cop(valor: float) -> str:
    return f"${int(valor):,}".replace(",", ".")

def enviar_whatsapp(mensaje: str):
    twilio.messages.create(body=mensaje, from_=BOT_NUMERO, to=MI_NUMERO)

def deudas_vencidas():
    """Retorna deudas cuya fecha ya pasó y aún tienen pagos pendientes."""
    hoy = date.today()
    vencidas = []

    for deuda in nc.leer_deudas_personal(incluir_fijos=True):
        if not deuda["fecha"]:
            continue
        if date.fromisoformat(deuda["fecha"]) < hoy:
            deuda["tabla"] = "personal"
            vencidas.append(deuda)

    for deuda in nc.leer_deudas_papas(incluir_fijos=True):
        if not deuda["fecha"]:
            continue
        if date.fromisoformat(deuda["fecha"]) < hoy:
            deuda["tabla"] = "familiar"
            vencidas.append(deuda)

    return sorted(vencidas, key=lambda d: d["fecha"])

# ──────────────────────────────────────────
# Revisión diaria completa — todo en un mensaje
# ──────────────────────────────────────────

def revisar_todo():
    print(f"[{date.today()}] Iniciando revisión diaria...")
    lineas = [f"📊 *Resumen diario — {date.today().strftime('%d/%m/%Y')}*\n"]
    hay_contenido = False

    # ── Deudas vencidas ──────────────────────────
    vencidas = deudas_vencidas()
    if vencidas:
        hay_contenido = True
        lineas.append("🚨 *PAGOS VENCIDOS — ATENCIÓN INMEDIATA:*")
        for d in vencidas:
            if d.get("tabla") == "familiar":
                origen = f"👨‍👩‍👧 {d.get('dueno', 'familiar')}"
            else:
                origen = "👤 tuyo"
            dias_vencido = (date.today() - date.fromisoformat(d["fecha"])).days
            fijo = " (fijo)" if d.get("es_fijo") else ""
            lineas.append(
                f"⛔ {d['gasto']}{fijo} — {origen}\n"
                f"  Cuota: {_cop(d['monto_final'])} | "
                f"Venció hace {dias_vencido} días | "
                f"Fecha: {d['fecha']}"
            )
        lineas.append("")

    # ── Deudas próximas ──────────────────────────
    for dias in [3, 7]:
        proximas = nc.deudas_proximas(dias)
        if proximas:
            hay_contenido = True
            lineas.append(f"🔔 *Pagos que vencen en {dias} días:*")
            for d in proximas:
                if d.get("tabla") == "familiar":
                    dueno = d.get("dueno", "familiar")
                    origen = f"👨‍👩‍👧 {dueno}"
                else:
                    origen = "👤 tuyo"
                fijo = " (fijo)" if d.get("es_fijo") else ""
                lineas.append(
                    f"• {d['gasto']}{fijo} — {origen}\n"
                    f"  Cuota: {_cop(d['monto_final'])} | Vence: {d['fecha']}"
                    + (f" | Quedan: {d['pagos_restantes']} pagos" if not d.get("es_fijo") else "")
                )
            lineas.append("")

    # ── Presupuesto ──────────────────────────────
    categorias = nc.leer_presupuesto()
    alertas_presupuesto = []
    for c in categorias:
        destinado  = c["valor_destinado"]
        disponible = c["presupuesto"]
        alerta     = c["alerta"]

        if destinado <= 0:
            continue

        if alerta == "😭":
            comprometido = destinado - disponible
            alertas_presupuesto.append(
                f"🚨 {c['nombre']}: presupuesto excedido\n"
                f"  Destinado {_cop(destinado)} | Comprometido {_cop(comprometido)}"
            )
        elif alerta == "⚠️":
            alertas_presupuesto.append(
                f"⚠️ {c['nombre']}: acercándose al límite\n"
                f"  Te quedan {_cop(disponible)} de {_cop(destinado)}"
            )
        # 😁 → silencio, todo bien

    if alertas_presupuesto:
        hay_contenido = True
        lineas.append("💰 *Presupuesto:*")
        lineas.extend(alertas_presupuesto)
        lineas.append("")

    # ── Facturas Gmail ───────────────────────────
    facturas = revisar_correos_nuevos(horas_atras=72)
    if facturas:
        hay_contenido = True
        lineas.append("🏠 *Facturas del hogar:*")
        for f in facturas:
            fecha_llegada = f.get("fecha_llegada", "")
            fecha_llegada_str = f" | Recibida: {fecha_llegada}" if fecha_llegada else ""
            if f["extraido"]:
                fecha_vence = f" | Vence: {f['fecha_vencimiento']}" if f["fecha_vencimiento"] else ""
                lineas.append(f"• {f['nombre']}{fecha_llegada_str}\n  💵 {_cop(f['monto'])}{fecha_vence}")
            else:
                lineas.append(f"• {f['nombre']}{fecha_llegada_str}\n  ⚠️ revisa \"{f['asunto'][:35]}\"")

    # ── Enviar solo si hay algo relevante ────────
    if hay_contenido:
        enviar_whatsapp("\n".join(lineas))
        print(f"[{date.today()}] Alerta enviada.")
    else:
        print(f"[{date.today()}] Sin novedades — no se envía mensaje.")

# ──────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────

if __name__ == "__main__":
    if "--once" in sys.argv:
        revisar_todo()
    else:
        print("Scheduler activo — revisión diaria a las 8:00am")
        revisar_todo()
        schedule.every().day.at("08:00").do(revisar_todo)
        while True:
            schedule.run_pending()
            time.sleep(60)