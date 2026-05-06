from notion_db import leer_presupuesto, leer_creditos, leer_deudas_personal, deudas_proximas

print("--- Presupuesto ---")
for c in leer_presupuesto():
    print(f"  {c['nombre']}: destinado ${c['valor_destinado']:,.0f} | disponible ${c['presupuesto']:,.0f}")

print("\n--- Tarjetas ---")
for t in leer_creditos():
    print(f"  {t['tarjeta']}: cupo ${t['cupo']:,.0f} | disponible ${t['cupo_disponible']:,.0f} | total mes ${t['total_mes']:,.0f}")

print("\n--- Deudas con cuotas (sin fijos) ---")
for d in leer_deudas_personal(incluir_fijos=False):
    print(f"  {d['gasto']}: cuota ${d['monto_final']:,.0f} | quedan {d['pagos_restantes']} pagos")

print("\n--- Próximos 7 días ---")
for d in deudas_proximas(7):
    fijo = " (fijo)" if d.get("es_fijo") else ""
    print(f"  {d['gasto']}{fijo}: vence {d['fecha']}")