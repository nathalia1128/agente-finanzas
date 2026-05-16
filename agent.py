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
        "name": "consultar_beneficios_tarjeta",
        "description": (
            "Busca en internet los beneficios actualizados de una tarjeta de crédito específica. "
            "Usar cuando el usuario pregunte qué tarjeta usar para un tipo de compra, "
            "o quiera saber los beneficios de alguna de sus tarjetas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tarjeta": {
                    "type": "string",
                    "description": "Nombre de la tarjeta. Ej: 'Rappi Card', 'Nu Colombia', 'Bancolombia Amex Gold', 'Bancolombia Mastercard e-Card'"
                },
                "consulta": {
                    "type": "string",
                    "description": "Qué quiere saber. Ej: 'beneficios en restaurantes', 'cashback', 'puntos'"
                }
            },
            "required": ["tarjeta"]
        }
    },
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
    },
    {
        "name": "consultar_gastos_por_categoria",
        "description": (
            "Consulta los gastos esporádicos del mes agrupados por categoría. "
            "Muestra total, porcentaje y detalle por categoría. "
            "Usar cuando pregunten por gastos en transporte, comida, etc., "
            "o por el desglose de gastos del mes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mes":  {"type": "integer", "description": "Mes (1-12). Opcional, default mes actual."},
                "anio": {"type": "integer", "description": "Año. Opcional, default año actual."}
            },
            "required": []
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

    if nombre == "consultar_gastos_por_categoria":
        return nc.leer_gastos_por_categoria(
            mes  = args.get("mes"),
            anio = args.get("anio")
        )

    if nombre == "consultar_beneficios_tarjeta":
        # Usar web search via Anthropic
        tarjeta  = args["tarjeta"]
        consulta = args.get("consulta", "beneficios y ventajas")
        
        respuesta_web = client.messages.create(
            model    = "claude-sonnet-4-5",
            max_tokens = 512,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": f"Busca los beneficios actuales de la tarjeta de crédito {tarjeta} en Colombia. Específicamente: {consulta}. Dame información concreta y actualizada."
            }]
        )
        
        texto_resultado = ""
        for block in respuesta_web.content:
            if hasattr(block, "text"):
                texto_resultado += block.text
        
        return {"beneficios": texto_resultado or "No encontré información actualizada sobre esa tarjeta."}

    return {"error": f"Herramienta '{nombre}' no encontrada"}

SYSTEM = f"""Eres un asistente financiero personal especializado. Tu única área de expertise son las finanzas personales del usuario.

ACCESO A DATOS:
Tienes acceso a estas fuentes reales del usuario:
- Gastos esporádicos: gastos en efectivo del mes con categorías
- Deudas Personal: cuotas activas con fechas y tarjetas
- Deudas Papás: deudas familiares que el usuario administra
- Créditos: tarjetas con cupo, saldo y tasas de interés
- Presupuesto mensual: categorías Fijos, Deudas, Ahorros con alertas

REGLAS ESTRICTAS:
1. Solo respondes preguntas de finanzas personales — si te preguntan algo fuera de ese tema responde: "Solo puedo ayudarte con temas de finanzas personales."
2. NUNCA inventes datos — si no tienes el dato, usa una herramienta para buscarlo. Si la herramienta no lo retorna, di claramente: "No tengo ese dato disponible."
3. Cuando des consejos o recomendaciones SIEMPRE basalos en los datos reales del usuario — nunca en generalidades inventadas.
4. Si el usuario pregunta por un dato específico (ej: "¿cuánto gasté en transporte?") SIEMPRE llama la herramienta correspondiente antes de responder.
5. Distingue claramente entre datos reales y recomendaciones: primero muestra el dato, luego la recomendación si aplica.

FORMATO DE RESPUESTA:
- Montos siempre en COP: $1.250.000
- Respuestas cortas — estamos en WhatsApp
- Sin markdown, sin asteriscos
- Si la alerta de Notion es 😭 avisar con énfasis
- Si es 👍 o 😁 confirmar que va bien

CONSEJOS Y RECOMENDACIONES:
Puedes dar consejos de finanzas personales cuando:
- El usuario lo pida explícitamente
- Detectes una alerta de presupuesto excedido
- El usuario esté cerca de su límite de deudas
- Veas oportunidad de optimizar basado en sus datos reales
Siempre fundamenta el consejo en los números reales del usuario, nunca en generalidades.

FLUJO PARA REGISTRAR:
- Efectivo o débito → registrar_gasto_efectivo
- Tarjeta de crédito → listar_tarjetas_disponibles → confirmar → registrar_compra_tarjeta

Fecha hoy: {date.today().strftime("%d/%m/%Y")}
Salario base: $2.900.000 COP"""

# Palabras que indican consulta compleja — usa Sonnet
PALABRAS_SONNET = {
    "analiza", "análisis", "recomienda", "recomendación", "explica",
    "consejo", "debería", "conviene", "estrategia", "optimiza",
    "compara", "qué tan", "por qué", "cómo mejorar", "qué hago"
}

def _elegir_modelo(texto: str) -> str:
    texto_lower = texto.lower()
    for palabra in PALABRAS_SONNET:
        if palabra in texto_lower:
            return "claude-sonnet-4-5"
    return "claude-haiku-4-5-20251001"

def procesar_mensaje(texto: str, historial: list) -> tuple[str, list]:
    historial = historial + [{"role": "user", "content": texto}]
    modelo = _elegir_modelo(texto)

    while True:
        respuesta = client.messages.create(
            model      = modelo,
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