from notion_db import registrar_gasto_efectivo

print("Registrando ingreso de prueba...")
registrar_gasto_efectivo(
    nombre    = "TEST ingreso prueba",
    monto     = 100000,
    categoria = "Otros",
    tipo      = "Ingreso"
)
print("Listo — verifica en Notion")