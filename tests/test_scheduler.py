from dotenv import load_dotenv
load_dotenv()
from notion_db import leer_ahorros_mes_actual, calcular_distribucion, aplicar_distribucion
from scheduler import _cop

print("--- Ahorros mes actual ---")
total = leer_ahorros_mes_actual()
print(f"  Total: {_cop(total)}")

print("\n--- Simulación distribución ---")
dist = calcular_distribucion(total if total > 0 else 290000)
for d in dist:
    print(f"  {d['meta']} ({d['porcentaje_real']}%): +{_cop(d['monto'])} → {_cop(d['ahorrado_nuevo'])}")