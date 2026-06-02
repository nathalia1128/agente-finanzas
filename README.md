# Agente Financiero Personal

Asistente financiero personal basado en IA, accesible por WhatsApp. Usa Claude (Anthropic) como motor de razonamiento para gestionar deudas, presupuesto, gastos y metas de ahorro mediante lenguaje natural.

## Caracteristicas

- **Registro de gastos**: en efectivo o con tarjeta de credito con planes de cuotas
- **Control de presupuesto**: seguimiento por categoria (Comida, Transporte, Salud, etc.)
- **Gestion de deudas**: personales y familiares, con alertas de vencimiento
- **Metas de ahorro**: creacion, distribucion proporcional y retiros
- **Integracion Gmail**: detecta y extrae montos de facturas de servicios publicos
- **Alertas diarias automaticas**: deudas proximas a vencer, presupuesto excedido y distribucion mensual de ahorros

## Tech Stack

| Capa | Tecnologia |
|------|-----------|
| IA principal | Claude Sonnet (Anthropic) |
| IA secundaria | Gemini 2.0 Flash (transcripcion de audio y PDFs) |
| Backend | FastAPI + Uvicorn |
| Base de datos | Notion API |
| Mensajeria | Twilio (WhatsApp) |
| Email | Gmail OAuth2 |
| Automatizacion | GitHub Actions (cron diario) |

## Estructura del proyecto

```
agente-finanzas/
├── main.py              # Servidor FastAPI y webhook de WhatsApp
├── agent.py             # Agente Claude con 14 herramientas y loop agentico
├── notion_db.py         # Operaciones CRUD sobre bases de datos de Notion
├── gmail_monitor.py     # Monitoreo de Gmail y extraccion de facturas
├── scheduler.py         # Alertas diarias automaticas
├── .github/
│   └── workflows/
│       └── scheduler.yml  # Cron job 8am (hora Colombia)
├── requirements.txt
└── Procfile             # Configuracion Heroku
```

## Requisitos previos

- Python 3.11+
- Cuenta de Twilio con numero de WhatsApp
- Integracion de Notion con 6 bases de datos configuradas
- API key de Anthropic
- (Opcional) API key de Gemini para audio y PDFs
- (Opcional) Credenciales OAuth2 de Gmail

## Instalacion

```bash
git clone https://github.com/nathalia1128/agente-finanzas.git
cd agente-finanzas
pip install -r requirements.txt
```

Crea un archivo `.env` con las siguientes variables:

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Notion
NOTION_TOKEN=ntn_...
DB_DEUDAS_PERSONAL=...
DB_DEUDAS_PAPAS=...
DB_CREDITOS=...
DB_PRESUPUESTO=...
DB_GASTOS=...
DB_METAS=...

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
MI_WHATSAPP_NUMBER=whatsapp:+57...

# Opcional
GEMINI_API_KEY=AIzaSy...
```

## Uso

### Servidor local

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

El webhook de WhatsApp queda expuesto en `POST /whatsapp`. Configuralo en Twilio como URL del sandbox o numero comprado.

### Scheduler manual

```bash
python scheduler.py --once   # Ejecutar revision una sola vez
python scheduler.py          # Loop continuo
```

## Herramientas del agente

| Herramienta | Descripcion |
|-------------|-------------|
| `consultar_presupuesto` | Estado del presupuesto por categoria |
| `consultar_deudas` | Deudas personales y familiares |
| `consultar_tarjetas` | Estado de tarjetas de credito |
| `registrar_gasto_efectivo` | Registrar gasto en efectivo o debito |
| `registrar_compra_tarjeta` | Registrar compra a cuotas con tarjeta |
| `listar_tarjetas_disponibles` | Listar tarjetas disponibles |
| `consultar_gastos_por_categoria` | Desglose de gastos del mes |
| `deudas_proximas_a_vencer` | Deudas que vencen en N dias |
| `consultar_beneficios_tarjeta` | Beneficios actuales de una tarjeta |
| `consultar_metas_ahorro` | Progreso de metas de ahorro |
| `distribuir_ahorro` | Distribuir ahorro mensual entre metas |
| `retirar_de_meta` | Retirar dinero de una meta |
| `crear_meta_ahorro` | Crear nueva meta de ahorro |
| `transferir_porcentaje` | Redirigir porcentaje entre metas |

## Bases de datos de Notion

El sistema requiere 6 bases de datos en Notion:

| Base de datos | Campos principales |
|---------------|-------------------|
| Deudas personal | Gasto, Monto, Cuotas, Interes, Credito, Fecha |
| Deudas familia | Gasto, Monto, Cuotas, Dueno, Fecha |
| Creditos | Tarjeta, Saldo, Cupo, Banco |
| Presupuesto | Categoria, Valor destinado, Comprometido, Disponible |
| Gastos | Gasto, Monto, Categoria, Fecha, Tipo, Distribuido |
| Metas ahorro | Meta, Valor meta, Porcentaje base, Ahorrado, Estado, Tipo |

## Automatizacion con GitHub Actions

El archivo `.github/workflows/scheduler.yml` ejecuta `scheduler.py` todos los dias a las 8am (hora Colombia) para:

- Detectar deudas vencidas o proximas a vencer (3 y 7 dias)
- Alertar categorias de presupuesto excedidas
- Revisar facturas nuevas en Gmail
- Distribuir ahorros automaticamente el dia 2 de cada mes

Para configurarlo, agrega los mismos valores del `.env` como secretos del repositorio en GitHub, mas:

```
GMAIL_CREDENTIALS_B64   # credentials.json en base64
GMAIL_TOKEN_B64         # token.json en base64
```

## Endpoints

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/whatsapp` | POST | Webhook de Twilio para mensajes entrantes |
| `/health` | GET | Health check |

## Arquitectura

```
Usuario (WhatsApp)
      |
   Twilio
      |
  FastAPI /whatsapp
      |
  agent.py (Claude Sonnet)
   /         \
notion_db.py  gmail_monitor.py
(Notion API)  (Gmail OAuth2)
```

Claude recibe el mensaje en lenguaje natural, decide que herramienta usar, la ejecuta contra Notion y formula una respuesta conversacional. Para mensajes de voz, Gemini transcribe el audio antes de pasarlo a Claude.

## Despliegue

El proyecto incluye un `Procfile` para despliegue en Heroku:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```
