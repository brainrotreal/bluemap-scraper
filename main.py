from bs4 import BeautifulSoup
import fastapi
import re
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import requests

limiter = Limiter(key_func=get_remote_address)
app = fastapi.FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

URL = "https://map.stoneworks.gg/abex/maps/abexilas/live/markers.json"

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
    data = requests.get(URL, timeout=20).json()

    lands = data["me.angeschossen.lands"]["markers"]

    for marker_id, marker in lands.items():
        detail = marker.get("detail", "")
        label = marker.get("label", "")

        if name.lower() in label.lower() or name.lower() in detail.lower():
            info = extract_land_info(detail)
            info["name"] = label
            info["marker_id"] = marker_id
            return info

    return None

@app.get("/land_info")
@limiter.limit("5/second")
async def land_info(request: fastapi.Request, name: str):
    info = get_land_info(name)
    return info or {"error": "Not found"}