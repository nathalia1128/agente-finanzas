import httpx
import os
from notion_client import Client
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.getenv("NOTION_TOKEN"))
_TOKEN = os.getenv("NOTION_TOKEN")
_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

DB_DEUDAS_PERSONAL = os.getenv("DB_DEUDAS_PERSONAL")
DB_DEUDAS_PAPAS    = os.getenv("DB_DEUDAS_PAPAS")
DB_CREDITOS        = os.getenv("DB_CREDITOS")
DB_PRESUPUESTO     = os.getenv("DB_PRESUPUESTO")
DB_GASTOS          = os.getenv("DB_GASTOS")
DB_METAS           = os.getenv("DB_METAS")
DB_CONFIG          = os.getenv("DB_CONFIG")

# ──────────────────────────────────────────
# Helper central para queries
# ──────────────────────────────────────────

def _query(database_id: str, filter_obj: dict = None, sorts: list = None) -> list:
    """Ejecuta queries usando httpx con timeout y reintentos."""
    body = {}
    if filter_obj:
        body["filter"] = filter_obj
    if sorts:
        body["sorts"] = sorts

    pages  = []
    cursor = None

    while True:
        if cursor:
            body["start_cursor"] = cursor

        # Reintentar hasta 3 veces si hay timeout
        for intento in range(3):
            try:
                r = httpx.post(
                    f"https://api.notion.com/v1/databases/{database_id}/query",
                    headers=_HEADERS,
                    json=body,
                    timeout=30.0  # 30 segundos
                )
                r.raise_for_status()
                break  # éxito — salir del loop de reintentos
            except httpx.TimeoutException:
                if intento == 2:  # último intento
                    raise
                import time
                time.sleep(3)  # esperar 3 segundos antes de reintentar

        data = r.json()
        pages.extend(data.get("results", []))

        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break

    return pages

# ──────────────────────────────────────────
# Helpers de extracción
# ──────────────────────────────────────────

def _titulo(props, campo):
    t = props.get(campo, {}).get("title", [])
    return t[0]["plain_text"] if t else ""

def _numero(props, campo):
    return props.get(campo, {}).get("number") or 0

def _formula_numero(props, campo):
    return props.get(campo, {}).get("formula", {}).get("number") or 0

def _formula_string(props, campo):
    return props.get(campo, {}).get("formula", {}).get("string") or ""

def _select(props, campo):
    s = props.get(campo, {}).get("select")
    return s["name"] if s else ""

def _checkbox(props, campo):
    return props.get(campo, {}).get("checkbox", False)

def _fecha(props, campo):
    d = props.get(campo, {}).get("date")
    return d["start"] if d else None

def _rollup_numero(props, campo):
    return props.get(campo, {}).get("rollup", {}).get("number") or 0

def _relaciones(props, campo):
    return [r["id"] for r in props.get(campo, {}).get("relation", [])]

def _formula_cop(props, campo) -> float:
    """Lee una fórmula que devuelve string en formato COP y lo convierte a float."""
    f = props.get(campo, {}).get("formula", {})
    
    # Algunos registros devuelven número directo
    if f.get("type") == "number":
        return f.get("number") or 0
    
    # Otros devuelven string con formato "$1.250.000" o "1250000"
    raw = f.get("string") or ""
    if not raw:
        return 0
    
    # Limpiar: quitar $, espacios, y convertir puntos de miles
    limpio = raw.replace("$", "").replace(" ", "").replace(",", "")
    # Formato colombiano usa punto como separador de miles
    # Si tiene más de un punto, todos son separadores de miles
    if limpio.count(".") > 1:
        limpio = limpio.replace(".", "")
    elif limpio.count(".") == 1:
        # Podría ser decimal o separador de miles
        partes = limpio.split(".")
        if len(partes[1]) == 3:
            # Es separador de miles: "75.300" → 75300
            limpio = limpio.replace(".", "")
        # Si no, es decimal real — dejarlo
    
    try:
        return float(limpio)
    except ValueError:
        return 0

# ──────────────────────────────────────────
# Lectura: Deudas Personal
# ──────────────────────────────────────────

def leer_deudas_personal(incluir_fijos=False):
    """
    incluir_fijos=False → solo deudas con cuotas finitas (no 888888)
    incluir_fijos=True  → todas las deudas activas
    """
    pages = _query(
        DB_DEUDAS_PERSONAL,
        filter_obj={"property": "# pagos", "number": {"greater_than": 0}},
        sorts=[{"property": "Fecha", "direction": "ascending"}]
    )
    deudas = []
    for page in pages:
        p = page["properties"]
        pagos = _numero(p, "# pagos")
        es_fijo = pagos >= 888888

        if es_fijo and not incluir_fijos:
            continue

        deudas.append({
            "id":              page["id"],
            "gasto":           _titulo(p, "Gasto"),
            "monto":           _numero(p, "Monto"),
            "monto_final":     _formula_cop(p, "Monto final "),
            "total_pagado":    _formula_numero(p, "Total pagado"),
            "cuotas":          _numero(p, "Cuotas"),
            "pagos_restantes": pagos,
            "es_fijo":         es_fijo,
            "porcentaje_pago": _formula_string(p, "Porcentaje de pago"),
            "interes":         _select(p, "Interes"),
            "interes_mv":      _rollup_numero(p, "Interes M.V."),
            "fecha":           _fecha(p, "Fecha"),
            "pago_fijo":       _checkbox(p, "Pago fijo"),
            "creditos_ids":    _relaciones(p, "Créditos"),
        })
    return deudas


def leer_deudas_papas(incluir_fijos=False):
    pages = _query(
        DB_DEUDAS_PAPAS,
        filter_obj={"property": "# pagos", "number": {"greater_than": 0}},
        sorts=[{"property": "Fecha", "direction": "ascending"}]
    )
    deudas = []
    for page in pages:
        p = page["properties"]
        pagos = _numero(p, "# pagos")
        es_fijo = pagos >= 888888

        if es_fijo and not incluir_fijos:
            continue

        deudas.append({
            "id":              page["id"],
            "gasto":           _titulo(p, "Gasto"),
            "monto":           _numero(p, "Monto"),
            "monto_final":     _formula_cop(p, "Monto final"),
            "total_pagado":    _formula_numero(p, "Total pagado"),
            "cuotas":          _numero(p, "Cuotas"),
            "pagos_restantes": pagos,
            "es_fijo":         es_fijo,
            "interes":         _select(p, "Interes"),
            "dueno":           _select(p, "Dueño de la deuda"),
            "fecha":           _fecha(p, "Fecha"),
            "pago_fijo":       _checkbox(p, "Pago fijo"),
            "tarjeta_ids":     _relaciones(p, "Tarjeta"),
        })
    return deudas


def deudas_proximas(dias: int):
    """
    Retorna deudas que vencen en los próximos N días.
    Incluye fijos recurrentes porque también tienen fecha.
    Excluye deudas sin fecha.
    """
    hoy    = date.today()
    limite = hoy + timedelta(days=dias)
    proximas = []

    for deuda in leer_deudas_personal(incluir_fijos=True):
        if not deuda["fecha"]:
            continue
        fecha_pago = date.fromisoformat(deuda["fecha"])
        if hoy <= fecha_pago <= limite:
            deuda["tabla"] = "personal"
            proximas.append(deuda)

    for deuda in leer_deudas_papas(incluir_fijos=True):
        if not deuda["fecha"]:
            continue
        fecha_pago = date.fromisoformat(deuda["fecha"])
        if hoy <= fecha_pago <= limite:
            deuda["tabla"] = "familiar"
            proximas.append(deuda)

    return sorted(proximas, key=lambda d: d["fecha"])

# ──────────────────────────────────────────
# Lectura: Créditos (tarjetas)
# ──────────────────────────────────────────

def _texto(props, campo):
    t = props.get(campo, {}).get("rich_text", [])
    return t[0]["plain_text"] if t else ""

def leer_creditos():
    pages = _query(DB_CREDITOS)
    tarjetas = []
    for page in pages:
        p = page["properties"]
        tarjetas.append({
            "id":               page["id"],
            "tarjeta":          _titulo(p, "Tarjeta"),
            "personal":         _rollup_numero(p, "Personal"),
            "otros":            _rollup_numero(p, "Otros"),
            "total_mes":        _formula_numero(p, "Total mes"),
            "interes_em":       _numero(p, "Interes E.M"),
            "cupo":             _numero(p, "Cupo"),
            "cupo_disponible":  _formula_numero(p, "Cupo disponible "),
            "total_deudas":     _formula_numero(p, "Total deudas"),
            "total_deudas_mes": _formula_numero(p, "Total deudas mes"),
            "total_pagado":     _formula_numero(p, "Total pagado"),
            "monto_personal":   _rollup_numero(p, "Monto total personal"),
            "monto_otros":      _rollup_numero(p, "Monto total otros"),
            "fecha_corte":      _texto(p, "Fecha de corte"),
            "fecha_pago":       _texto(p, "Fecha de pago"),
            "tipo":             _select(p, "Tipo"),
        })
    return tarjetas

# ──────────────────────────────────────────
# Lectura: Presupuesto mensual
# ──────────────────────────────────────────

def leer_presupuesto():
    pages = _query(DB_PRESUPUESTO)
    categorias = []
    for page in pages:
        p = page["properties"]
        categorias.append({
            "id":              page["id"],
            "nombre":          _titulo(p, "Name"),
            "porcentaje":      _numero(p, "porcentaje"),
            "valor_destinado": _formula_numero(p, "Valor destinado"),
            "presupuesto":     _formula_numero(p, "presupuesto"),
            "salario":         _formula_numero(p, "Salario"),
            "alerta":          _formula_string(p, "Alerta"),
            "gastos_fijos":    _rollup_numero(p, "valor gastos fijos"),
            "total_tarjetas":  _rollup_numero(p, "Total tarjetas"),
        })
    return categorias

# ──────────────────────────────────────────
# Lectura: Gatos por categoría
# ──────────────────────────────────────────

def leer_gastos_por_categoria(mes: int = None, anio: int = None) -> dict:
    """
    Retorna los gastos esporádicos agrupados por categoría.
    Si no se especifica mes/año usa el mes actual.
    """
    from collections import defaultdict
    hoy = date.today()
    mes  = mes  or hoy.month
    anio = anio or hoy.year

    # Primer y último día del mes
    primer_dia = date(anio, mes, 1).isoformat()
    if mes == 12:
        ultimo_dia = date(anio + 1, 1, 1).isoformat()
    else:
        ultimo_dia = date(anio, mes + 1, 1).isoformat()

    pages = _query(
        DB_GASTOS,
        filter_obj={
            "and": [
                {"property": "Fecha", "date": {"on_or_after": primer_dia}},
                {"property": "Fecha", "date": {"before": ultimo_dia}},
                {"property": "Tipo", "select": {"equals": "Gasto"}}
            ]
        },
        sorts=[{"property": "Fecha", "direction": "ascending"}]
    )

    por_categoria = defaultdict(list)
    total = 0

    for page in pages:
        p = page["properties"]
        nombre    = _titulo(p, "Nombre")
        monto     = _numero(p, "Monto")
        categoria = _select(p, "Categoría") or "Sin categoría"
        fecha     = _fecha(p, "Fecha")

        por_categoria[categoria].append({
            "nombre": nombre,
            "monto":  monto,
            "fecha":  fecha
        })
        total += monto

    # Calcular subtotal por categoría
    resumen = {}
    for cat, gastos in por_categoria.items():
        subtotal = sum(g["monto"] for g in gastos)
        resumen[cat] = {
            "total":    subtotal,
            "cantidad": len(gastos),
            "gastos":   gastos,
            "porcentaje": round(subtotal / total * 100, 1) if total > 0 else 0
        }

    return {
        "mes":    mes,
        "anio":   anio,
        "total":  total,
        "categorias": resumen
    }


# ──────────────────────────────────────────
# Escritura: Gastos esporádicos (efectivo)
# ──────────────────────────────────────────

def registrar_gasto_efectivo(nombre: str, monto: float, categoria: str,
                              fecha: str = None, notas: str = "", tipo: str = "Gasto"):
    notion.pages.create(
        parent={"database_id": DB_GASTOS},
        properties={
            "Nombre":                {"title":     [{"text": {"content": nombre}}]},
            "Monto":                 {"number":    monto},
            "Tipo":                  {"select":    {"name": tipo}},
            "Categoría":             {"select":    {"name": categoria}},
            "Fecha":                 {"date":      {"start": fecha or date.today().isoformat()}},
            "Notas":                 {"rich_text": [{"text": {"content": notas}}]},
            "💲 Presupuesto mensual": {"relation":  [{"id": "3d33aefcf317452488139cbbdd5a32df"}]},
            "Distribuido":           {"checkbox":  tipo != "Ahorro"},  # False si es ahorro, True si es gasto
        }
    )
    return {"ok": True}
# ──────────────────────────────────────────
# Escritura: Compra con tarjeta → Deudas Personal
# ──────────────────────────────────────────

def _calcular_fecha_pago(fecha_corte_str: str, fecha_pago_str: str) -> str:
    """
    Calcula la fecha de pago correcta según la fecha de corte.
    - Si hoy <= fecha de corte → paga el mes siguiente en día de pago
    - Si hoy > fecha de corte → paga dos meses después en día de pago
    - "Fin de mes" = último día del mes como corte
    """
    import calendar
    hoy = date.today()

    # Determinar día de pago
    if not fecha_pago_str or not fecha_pago_str.strip().isdigit():
        return hoy.isoformat()
    dia_pago = int(fecha_pago_str.strip())

    # Determinar día de corte
    if fecha_corte_str.strip().lower() in ("fin de mes", "fin"):
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        dia_corte  = ultimo_dia
    elif fecha_corte_str.strip().isdigit():
        dia_corte = int(fecha_corte_str.strip())
    else:
        dia_corte = hoy.day  # si no se entiende, asumir que ya pasó el corte

    # ¿Ya pasamos el corte este mes?
    try:
        fecha_corte = hoy.replace(day=dia_corte)
    except ValueError:
        fecha_corte = hoy  # día inválido — asumir que pasó

    if hoy <= fecha_corte:
        # Antes o en el corte → paga el mes siguiente
        meses_adelante = 1
    else:
        # Después del corte → paga dos meses después
        meses_adelante = 2

    # Calcular mes de pago
    mes_pago  = hoy.month + meses_adelante
    anio_pago = hoy.year
    if mes_pago > 12:
        mes_pago  -= 12
        anio_pago += 1

    # Ajustar si el día de pago no existe en ese mes
    ultimo_dia_mes = calendar.monthrange(anio_pago, mes_pago)[1]
    dia_pago_final = min(dia_pago, ultimo_dia_mes)

    return date(anio_pago, mes_pago, dia_pago_final).isoformat()


def registrar_compra_tarjeta(gasto: str, monto: float, cuotas: int,
                              interes: str, credito_id: str, fecha: str = None):
    if not fecha:
        tarjetas = leer_creditos()
        tarjeta  = next((t for t in tarjetas if t["id"] == credito_id), None)
        if tarjeta and tarjeta.get("fecha_pago"):
            fecha = _calcular_fecha_pago(
                tarjeta.get("fecha_corte", ""),
                tarjeta["fecha_pago"]
            )
        else:
            fecha = date.today().isoformat()

    # IDs de las 4 categorías del presupuesto
    PRESUPUESTO_IDS = [
        "3d33aefcf317452488139cbbdd5a32df",  # Fijos
        "b9d4b96947de48c5b7e80ce3581c2735",  # Deudas
        "e9eaf617d8d9450bbd43862adc478d28",  # Ahorros
        "1318fc0b0df780aab59dd59ec592c046",  # Emergencias
    ]

    notion.pages.create(
        parent={"database_id": DB_DEUDAS_PERSONAL},
        properties={
            "Gasto":                {"title":    [{"text": {"content": gasto}}]},
            "Monto":                {"number":   monto},
            "Cuotas":               {"number":   cuotas},
            "# pagos":              {"number":   cuotas},
            "Interes":              {"select":   {"name": interes.capitalize()}},
            "Fecha":                {"date":     {"start": fecha}},
            "Créditos":             {"relation": [{"id": credito_id}]},
            "💲 Presupuesto mensual": {"relation": [{"id": pid} for pid in PRESUPUESTO_IDS]},
        }
    )
    return {"ok": True}

# ──────────────────────────────────────────
# Lectura: Metas de ahorro
# ──────────────────────────────────────────

def leer_metas():
    """Lee todas las metas de ahorro."""
    pages = _query(DB_METAS)
    metas = []
    for page in pages:
        p = page["properties"]
        metas.append({
            "id":                  page["id"],
            "meta":                _titulo(p, "Meta"),
            "valor_meta":          _numero(p, "Valor meta"),
            "porcentaje_base":     _numero(p, "Porcentaje base"),
            "estado":              _select(p, "Estado"),
            "tipo":                _select(p, "Tipo"),
            "ahorrado":            _numero(p, "Ahorrado"),
            "retirado":            _numero(p, "Retirado"),
            "disponible":          _formula_numero(p, "Disponible"),
            "porcentaje_alcanzado":_formula_numero(p, "Porcentaje alcanzado"),
        })
    return metas

def leer_metas_activas():
    """Lee solo las metas con Estado = Activa."""
    pages = _query(
        DB_METAS,
        filter_obj={"property": "Estado", "select": {"equals": "Activa"}}
    )
    metas = []
    for page in pages:
        p = page["properties"]
        metas.append({
            "id":              page["id"],
            "meta":            _titulo(p, "Meta"),
            "valor_meta":      _numero(p, "Valor meta"),
            "porcentaje_base": _numero(p, "Porcentaje base"),
            "tipo":            _select(p, "Tipo"),
            "ahorrado":        _numero(p, "Ahorrado"),
            "retirado":        _numero(p, "Retirado"),
            "disponible":      _formula_numero(p, "Disponible"),
            "porcentaje_alcanzado": _formula_numero(p, "Porcentaje alcanzado"),
        })
    return metas

def leer_config_ahorros():
    """Lee la fila Config de la tabla Config Ahorros."""
    pages = _query(DB_CONFIG)
    if not pages:
        return None
    p = pages[0]["properties"]
    return {
        "id":                pages[0]["id"],
        "total_ahorrado":    _rollup_numero(p, "Total ahorrado"),
        "porcentaje_activos":_numero(p, "Porcentaje activos"),
    }

# ──────────────────────────────────────────
# Escritura: Metas de ahorro
# ──────────────────────────────────────────

def actualizar_meta(page_id: str, ahorrado: float = None, retirado: float = None,
                    estado: str = None, porcentaje_base: float = None):
    """Actualiza campos de una meta existente."""
    props = {}
    if ahorrado is not None:
        props["Ahorrado"] = {"number": ahorrado}
    if retirado is not None:
        props["Retirado"] = {"number": retirado}
    if estado is not None:
        props["Estado"] = {"select": {"name": estado}}
    if porcentaje_base is not None:
        props["Porcentaje base"] = {"number": porcentaje_base}

    notion.pages.update(page_id=page_id, properties=props)
    return {"ok": True}

def crear_meta(nombre: str, valor_meta: float, porcentaje_base: float,
               tipo: str, estado: str = "Activa"):
    """Crea una nueva meta de ahorro."""
    notion.pages.create(
        parent={"database_id": DB_METAS},
        properties={
            "Meta":            {"title":  [{"text": {"content": nombre}}]},
            "Valor meta":      {"number": valor_meta},
            "Porcentaje base": {"number": porcentaje_base},
            "Tipo":            {"select": {"name": tipo}},
            "Estado":          {"select": {"name": estado}},
            "Ahorrado":        {"number": 0},
            "Retirado":        {"number": 0},
        }
    )
    return {"ok": True}

def actualizar_porcentaje_activos(page_id: str, porcentaje: float):
    """Actualiza el campo Porcentaje activos en Config Ahorros."""
    notion.pages.update(
        page_id=page_id,
        properties={"Porcentaje activos": {"number": porcentaje}}
    )
    return {"ok": True}

# ──────────────────────────────────────────
# Lógica: Distribuir ahorro entre metas
# ──────────────────────────────────────────

def calcular_distribucion(monto: float) -> list:
    """
    Calcula cuánto corresponde a cada meta activa.
    Los porcentajes se normalizan para que sumen 100
    aunque alguna meta esté pausada.
    """
    metas = leer_metas_activas()
    if not metas:
        return []

    total_porcentaje = sum(m["porcentaje_base"] for m in metas)
    if total_porcentaje == 0:
        return []

    distribucion = []
    for m in metas:
        porcentaje_real = m["porcentaje_base"] / total_porcentaje
        monto_meta      = round(monto * porcentaje_real)
        distribucion.append({
            "id":              m["id"],
            "meta":            m["meta"],
            "porcentaje_base": m["porcentaje_base"],
            "porcentaje_real": round(porcentaje_real * 100, 1),
            "monto":           monto_meta,
            "ahorrado_actual": m["ahorrado"],
            "ahorrado_nuevo":  m["ahorrado"] + monto_meta,
        })

    return distribucion

def aplicar_distribucion(distribucion: list, page_ids: list = None) -> bool:
    """Aplica la distribución y opcionalmente marca los ahorros como distribuidos."""
    for item in distribucion:
        actualizar_meta(
            page_id  = item["id"],
            ahorrado = item["ahorrado_nuevo"]
        )
    if page_ids:
        marcar_ahorros_distribuidos(page_ids)
    return True

def leer_ahorros_mes_actual() -> tuple[float, list]:
    """
    Retorna el total de ahorros no distribuidos del mes actual
    y la lista de page IDs para marcarlos después.
    """
    hoy        = date.today()
    primer_dia = date(hoy.year, hoy.month, 1).isoformat()
    if hoy.month == 12:
        ultimo_dia = date(hoy.year + 1, 1, 1).isoformat()
    else:
        ultimo_dia = date(hoy.year, hoy.month + 1, 1).isoformat()

    pages = _query(
        DB_GASTOS,
        filter_obj={
            "and": [
                {"property": "Fecha",       "date":     {"on_or_after": primer_dia}},
                {"property": "Fecha",       "date":     {"before":      ultimo_dia}},
                {"property": "Tipo",        "select":   {"equals":      "Ahorro"}},
                {"property": "Distribuido", "checkbox": {"equals":      False}}
            ]
        }
    )

    total    = 0
    page_ids = []
    for page in pages:
        p = page["properties"]
        total += _formula_numero(p, "Total ahorros")
        page_ids.append(page["id"])

    return total, page_ids

def marcar_ahorros_distribuidos(page_ids: list):
    """Marca los registros de ahorro como distribuidos."""
    for page_id in page_ids:
        notion.pages.update(
            page_id    = page_id,
            properties = {"Distribuido": {"checkbox": True}}
        )