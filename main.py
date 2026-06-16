from bs4 import BeautifulSoup
import fastapi
import re
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import requests
import isEven

#test

limiter = Limiter(key_func=get_remote_address)
app = fastapi.FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

URL = "https://map.stoneworks.gg/abex/tiles/minecraft_overworld/markers.json"

def parse_money(text):
    return float(text.replace("$", "").replace(",", "").strip())

def extract_land_info(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    patterns = {
        "level": r"Level:\s*(.+)",
        "balance": r"Balance:\s*\$?([\d,]+\.\d+)",
        "chunks": r"Chunks:\s*(\d+)",
        "created_at": r"Created at:\s*(.+)",
        "nation": r"This land belongs to nation\s+(.+?):",
        "capital": r"Capital:\s*(.+)",
        "founded_at": r"Founded at:\s*(.+)",
    }

    info = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, text)
        if m:
            info[key] = m.group(1).strip()

    if "balance" in info:
        info["balance"] = parse_money(info["balance"])

    return info

def get_land_info(name):
    r = requests.get(URL, timeout=20)
    r.raise_for_status()
    data = r.json()

    lands_layer = next(
        (
            layer for layer in data
            if layer.get("id") == "lands_world" or layer.get("name") == "Lands"
        ),
        None
    )

    if not lands_layer:
        return None

    for index, marker in enumerate(lands_layer.get("markers", [])):
        html = marker.get("popup") or marker.get("tooltip") or ""

        if name.lower() in html.lower():
            info = extract_land_info(html)
            info["name"] = name
            info["marker_index"] = index
            return info

    return None

@app.get("/land_info")
@limiter.limit("5/second")
async def land_info(request: fastapi.Request, name: str):
    info = get_land_info(name)
    return info or {"error": "Not found"}