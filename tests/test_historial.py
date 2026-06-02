# test_historial.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

# Simular historial corrupto — tool_result sin tool_use correspondiente
historial_corrupto = [
    {"role": "user", "content": "Hola"},
    {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_fake123", "name": "consultar_presupuesto", "input": {}}
    ]},
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_DIFERENTE", "content": "{}"}
    ]}
]

from agent import procesar_mensaje

print("Prueba 1 — historial corrupto debería dar error:")
try:
    respuesta, _ = procesar_mensaje("Hola", historial_corrupto)
    print(f"Respuesta: {respuesta}")
except Exception as e:
    error = str(e)
    print(f"Error detectado: {error[:80]}")
    
    if "tool_use_id" in error or "tool_result" in error:
        print("\nDetectado correctamente — limpiando historial y reintentando...")
        try:
            respuesta, historial_nuevo = procesar_mensaje("Hola", [])
            print(f"Reintento exitoso: {respuesta[:80]}")
        except Exception as e2:
            print(f"Error en reintento: {e2}")
    else:
        print("Error diferente — no es de historial corrupto")

print("\nPrueba 2 — historial limpio funciona normal:")
try:
    respuesta, _ = procesar_mensaje("Hola", [])
    print(f"OK: {respuesta[:80]}")
except Exception as e:
    print(f"Error: {e}")