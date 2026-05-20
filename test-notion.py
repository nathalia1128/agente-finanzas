from notion_db import leer_metas, leer_config_ahorros, calcular_distribucion

print("--- Metas ---")
for m in leer_metas():
    print(f"  {m['meta']} | {m['estado']} | {m['porcentaje_base']}% | ahorrado ${m['ahorrado']:,.0f}")

print("\n--- Config ---")
c = leer_config_ahorros()
print(f"  Total ahorrado: ${c['total_ahorrado']:,.0f}" if c else "  Sin config")

print("\n--- Simulación distribución $290.000 ---")
for d in calcular_distribucion(290000):
    print(f"  {d['meta']}: ${d['monto']:,.0f} ({d['porcentaje_real']}%)")