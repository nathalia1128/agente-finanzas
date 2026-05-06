# Arquitectura del Agente Financiero Personal

## ¿Es un agente o un workflow?

**Es un agente.** La diferencia fundamental es dónde vive la lógica de decisión.

En un **workflow** (como Zapier o n8n), el programador define explícitamente cada paso: "si llega un mensaje, extrae el texto, luego busca en la base de datos, luego responde". La lógica es rígida y solo funciona para los casos previstos.

En un **agente**, el modelo de IA recibe el contexto completo, un conjunto de herramientas disponibles y decide por sí mismo qué hacer. Cuando el usuario dice "gasté $25.000 en el bus", Claude razona que debe llamar `registrar_gasto_efectivo()` con categoría `Transporte` y monto `25000`. Nadie programó esa asociación — el agente la infirió del contexto.

El código del proyecto solo define:
- Qué herramientas existen (funciones de Python)
- Qué reglas seguir (system prompt)
- Cómo ejecutar cada herramienta

Claude decide cuándo y cómo usarlas.

---

## Descripción de cada archivo

### `main.py` — Servidor y punto de entrada
Recibe los mensajes de WhatsApp a través de un webhook de Twilio. Detecta si el mensaje es texto o audio. Si es audio y Gemini está activo, transcribe primero. Luego pasa el texto al agente y devuelve la respuesta a Twilio para que la envíe por WhatsApp.

**IA involucrada:** Gemini (opcional) para transcripción de audio.

---

### `agent.py` — El cerebro del agente
Define las herramientas disponibles para Claude (consultar presupuesto, registrar gastos, listar tarjetas, etc.) y el system prompt con las reglas del sistema. Contiene el agentic loop: envía el mensaje a Claude, recibe su respuesta, ejecuta las herramientas que Claude solicite, y repite hasta que Claude termina de razonar.

**IA involucrada:** Claude Sonnet — toda la inteligencia del sistema vive aquí. Claude decide qué herramientas llamar, en qué orden, y cómo responder al usuario.

---

### `notion_db.py` — Conexión con Notion
Lee y escribe en las 5 tablas de Notion. Contiene todos los helpers para extraer propiedades (números, fórmulas, relaciones, selects), la lógica para calcular fechas de pago según la fecha de corte de cada tarjeta, y las funciones de escritura para registrar gastos y compras.

**IA involucrada:** Ninguna directamente. Es una capa de datos pura. Claude la usa como herramienta.

---

### `gmail_monitor.py` — Lectura de facturas del hogar
Se conecta a Gmail con OAuth2, busca correos de remitentes específicos (Enel, ETB, Vanti, Acueducto), extrae el texto del correo o de adjuntos (PDF, ZIP, imagen), e intenta encontrar el monto y fecha de vencimiento con expresiones regulares.

**IA involucrada:** Gemini (opcional) para leer facturas en formato imagen o PDF escaneado que no tienen texto extraíble directamente.

---

### `scheduler.py` — Alertas automáticas diarias
Corre todos los días a las 8am vía GitHub Actions. Revisa deudas próximas a vencer (7 días y 3 días), compara el presupuesto contra los umbrales definidos en Notion, y revisa si llegaron facturas nuevas en las últimas 24 horas. Envía las alertas relevantes por WhatsApp vía Twilio.

**IA involucrada:** Ninguna. Las decisiones de alerta se basan en cálculos y en la columna `Alerta` que Notion ya calcula.

---

### `.github/workflows/scheduler.yml` — Automatización en la nube
Define cuándo y cómo corre el scheduler en los servidores de GitHub. Se ejecuta todos los días a las 8am (hora Colombia) sin necesidad de que el PC esté encendido. Reconstruye los archivos de credenciales de Gmail desde los secretos del repositorio antes de correr.

**IA involucrada:** Ninguna. Es infraestructura pura.

---

## ¿Dónde interviene la IA?

| Proceso | Modelo | Descripción |
|---|---|---|
| Interpretar mensajes del usuario | Claude Sonnet | Lee el mensaje, entiende la intención, decide qué herramienta usar |
| Registrar gastos y compras | Claude Sonnet | Infiere categoría, monto, tarjeta y fecha del lenguaje natural |
| Consultar y resumir datos | Claude Sonnet | Traduce datos crudos de Notion en respuestas conversacionales |
| Transcribir audios | Gemini 2.0 Flash | Convierte mensajes de voz a texto antes de pasarlos a Claude |
| Leer facturas en imagen/PDF | Gemini 2.0 Flash | Extrae monto y fecha de facturas que no tienen texto legible |

---

## Flujo completo de un mensaje

```
Usuario (WhatsApp)
    ↓
Twilio recibe el mensaje y lo envía al webhook
    ↓
main.py detecta si es texto o audio
    ↓  (si es audio)
Gemini transcribe → texto
    ↓
agent.py envía el texto a Claude con el historial y las herramientas disponibles
    ↓
Claude razona y decide qué herramienta(s) llamar
    ↓
agent.py ejecuta las herramientas (consultas o escrituras en Notion)
    ↓
Claude recibe los resultados y formula la respuesta final
    ↓
main.py devuelve la respuesta a Twilio
    ↓
Usuario recibe la respuesta por WhatsApp
```

---

## Flujo de alertas automáticas (8am)

```
GitHub Actions (cron 8am Colombia)
    ↓
scheduler.py revisa deudas próximas a vencer (7 días y 3 días)
    ↓
scheduler.py revisa estado del presupuesto (columna Alerta de Notion)
    ↓
gmail_monitor.py busca facturas nuevas en Gmail
    ↓  (si la factura es imagen/PDF)
Gemini extrae monto y fecha
    ↓
Para cada alerta relevante: Twilio envía mensaje al WhatsApp del usuario
```
