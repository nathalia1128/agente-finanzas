import httpx, os
from dotenv import load_dotenv
load_dotenv()

r = httpx.post(
    f"https://api.notion.com/v1/databases/{os.getenv('DB_GASTOS')}/query",
    headers={
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    },
    json={"page_size": 1}
)
props = r.json()["results"][0]["properties"]
for nombre, valor in props.items():
    print(f"  '{nombre}' → {valor.get('type')}")