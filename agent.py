# agent.py
import os
import json
from anthropic import Anthropic
from datetime import date
from dotenv import load_dotenv
import notion_db as nc

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

TOOLS = [
    {
        "name": "consultar_presupuesto",
        "description": (
            "Consulta el estado actual del presupuesto mensual. "
            "Retorna cada categoría con valor destinado, comprometido y disponible. "
            "Úsalo cuando pregunten cuánto queda, cómo va el mes, "
            "o si puede hacer un gasto."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "consultar_deudas",
        "description": (
            "Consulta deudas activas personales y opcionalmente familiares. "
            "Incluye cuota, pagos restantes, fecha y tarjeta asociada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "incluir_familiares": {
                    "type": "boolean",
                    "description": "Si true incluye deudas de Papás. Default false."
                }
            },
            "required": []
        }
    },
    {
        "name": "consultar_tarjetas",
        "description": (
            "Consulta resumen de tarjetas: cupo total, disponible, "
            "saldo personal y de otros."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
    "name": "registrar_gasto_efectivo",
    "description": (
        "Registra un gasto o ingreso en efectivo o débito en Gastos esporádicos. "
        "Usa tipo 'Gasto' para gastos y 'Ingreso' para ingresos recibidos. "
        "NO usar para compras con tarjeta de crédito."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nombre":    {"type": "string",  "description": "Descripción. Ej: 'Mercado semanal' o 'Pago freelance'"},
            "monto":     {"type": "number",  "description": "Valor en COP"},
            "tipo":      {"type": "string",  "enum": ["Gasto", "Ingreso"], "description": "Gasto o Ingreso"},
            "categoria": {
                "type": "string",
                "enum": ["Comida", "Transporte", "Salud", "Entretenimiento",
                         "Hogar", "Educación", "Ropa", "Tecnología", "Otros"]
            },
            "fecha":     {"type": "string",  "description": "YYYY-MM-DD. Opcional."},
            "notas":     {"type": "string",  "description": "Contexto adicional. Opcional."}
        },
        "required": ["nombre", "monto", "tipo", "categoria"]
    }
    },
    {
        "name": "listar_tarjetas_disponibles",
        "description": (
            "Lista las tarjetas con su ID. "
            "Llamar SIEMPRE antes de registrar_compra_tarjeta."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "registrar_compra_tarjeta",
        "description": (
            "Registra una compra con tarjeta de crédito en Deudas Personal. "
            "Preguntar siempre: nombre, monto total, cuotas, interés y tarjeta. "
            "NO usar para efectivo o débito."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gasto":      {"type": "string"},
                "monto":      {"type": "number",  "description": "Valor total en COP"},
                "cuotas":     {"type": "integer", "description": "Número de cuotas"},
                "interes":    {"type": "string",  "enum": ["si", "no"]},
                "credito_id": {"type": "string",  "description": "Page ID de la tarjeta"},
                "fecha":      {"type": "string",  "description": "YYYY-MM-DD. Opcional."}
            },
            "required": ["gasto", "monto", "cuotas", "interes", "credito_id"]
        }
    },
    {
        "name": "deudas_proximas_a_vencer",
        "description": "Revisa deudas que vencen en los próximos N días.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dias": {"type": "integer", "description": "Días hacia adelante. Usar 7 o 3."}
            },
            "required": ["dias"]
        }
    }
]

def ejecutar_herramienta(nombre: str, args: dict) -> dict:
    if nombre == "consultar_presupuesto":
        return {"categorias": nc.leer_presupuesto()}

    if nombre == "consultar_deudas":
        resultado = {"personales": nc.leer_deudas_personal()}
        if args.get("incluir_familiares"):
            resultado["familiares"] = nc.leer_deudas_papas()
        return resultado

    if nombre == "consultar_tarjetas":
        return {"tarjetas": nc.leer_creditos()}

    if nombre == "registrar_gasto_efectivo":
        nc.registrar_gasto_efectivo(
            nombre    = args["nombre"],
            monto     = args["monto"],
            categoria = args["categoria"],
            fecha     = args.get("fecha"),
            notas     = args.get("notas", ""),
            tipo      = args.get("tipo", "Gasto")
        )
        return {"ok": True, "mensaje": f"✅ '{args['nombre']}' registrado como {args.get('tipo', 'Gasto')}"}

    if nombre == "listar_tarjetas_disponibles":
        tarjetas = nc.leer_creditos()
        return {"tarjetas": [{"id": t["id"], "nombre": t["tarjeta"]} for t in tarjetas]}

    if nombre == "registrar_compra_tarjeta":
        nc.registrar_compra_tarjeta(
            gasto      = args["gasto"],
            monto      = args["monto"],
            cuotas     = args["cuotas"],
            interes    = args["interes"],
            credito_id = args["credito_id"],
            fecha      = args.get("fecha")
        )
        return {"ok": True, "mensaje": f"✅ '{args['gasto']}' registrado en Deudas Personal"}

    if nombre == "deudas_proximas_a_vencer":
        return {"deudas": nc.deudas_proximas(args["dias"])}

    return {"error": f"Herramienta '{nombre}' no encontrada"}

SYSTEM = f"""Eres el asistente financiero personal de tu usuario. Hablas por WhatsApp en español colombiano.

TABLAS DISPONIBLES:
- Deudas Personal: deudas activas propias con cuotas, fechas y tarjetas
- Deudas Papás: deudas familiares que administras (Caro, Mamá, Papá)
- Créditos: resumen de tarjetas con cupo, saldo y tasas de interés
- Presupuesto mensual: categorías Fijos, Deudas, Ahorros, Emergencias
- Gastos esporádicos: gastos en efectivo del mes (única tabla donde escribes)

REGLAS:
1. Efectivo o débito → registrar_gasto_efectivo
2. Tarjeta de crédito → registrar_compra_tarjeta (pedir datos, listar tarjetas, confirmar antes de guardar)
3. Nunca modificar Deudas Papás, Créditos ni Presupuesto
4. Montos siempre en formato COP: $1.250.000
5. Al mostrar presupuesto incluir siempre: destinado, comprometido, disponible este mes y próximo
6. Si alerta de Notion es 😭 avisar con énfasis. Si es 👍 confirmar que va bien
7. Respuestas cortas y directas — estamos en WhatsApp
8. Si el mensaje viene con prefijo [Audio transcrito]: procesarlo igual que texto normal

Fecha hoy: {date.today().strftime("%d/%m/%Y")}
Salario base: $2.900.000 COP"""

def procesar_mensaje(texto: str, historial: list) -> tuple[str, list]:
    historial = historial + [{"role": "user", "content": texto}]

    while True:
        respuesta = client.messages.create(
            model = "claude-sonnet-4-5",
            max_tokens = 1024,
            system     = SYSTEM,
            tools      = TOOLS,
            messages   = historial
        )
        historial.append({"role": "assistant", "content": respuesta.content})

        if respuesta.stop_reason == "end_turn":
            texto_final = next(
                (b.text for b in respuesta.content if hasattr(b, "text")), ""
            )
            return texto_final, historial

        if respuesta.stop_reason == "tool_use":
            tool_results = []
            for block in respuesta.content:
                if block.type == "tool_use":
                    resultado = ejecutar_herramienta(block.name, block.input)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(resultado, ensure_ascii=False, default=str)
                    })
            historial.append({"role": "user", "content": tool_results})