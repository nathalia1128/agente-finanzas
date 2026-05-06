from notion_db import registrar_compra_tarjeta, leer_creditos

tarjetas = leer_creditos()
rappi    = next((t for t in tarjetas if t["tarjeta"].strip() == "Rappi"), None)

print("Registrando con relación de presupuesto...")
resultado = registrar_compra_tarjeta(
    gasto      = "TEST presupuesto v2",
    monto      = 50000,
    cuotas     = 1,
    interes    = "no",
    credito_id = rappi["id"]
)
print(resultado)