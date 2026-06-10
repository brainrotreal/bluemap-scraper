from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import fastapi
import re
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

URL = "https://map.stoneworks.gg/abex/#abexilas:0:0:0:1500:0:0:0:0:perspective"

limiter = Limiter(key_func=get_remote_address)
app = fastapi.FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def parse_money(text):
    return float(text.replace("$", "").replace(",", "").strip())

def extract_land_info(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    info = {}

    patterns = {
        "level": r"Level:\s*(.+)",
        "balance": r"Balance:\s*\$?([\d,]+\.\d+)",
        "chunks": r"Chunks:\s*(\d+)",
        "created_at": r"Created at:\s*(.+)",
        "nation": r"This land belongs to nation\s+(.+?):",
        "capital": r"Capital:\s*(.+)",
        "founded_at": r"Founded at:\s*(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            info[key] = match.group(1).strip()

    if "balance" in info:
        info["balance"] = parse_money(info["balance"])

    return info

def get_land_info(land_name):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function("() => window.bluemap?.mapViewer?.markers?.children?.[2]?.children", timeout=60000)

        result = page.evaluate(
            """
            (landName) => {
              const markers = window.bluemap?.mapViewer?.markers?.children?.[2]?.children;
              if (!markers) return null;

              for (const marker of markers) {
                const label = marker?.data?.label || marker?._markerData?.label;
                const detail = marker?.data?.detail || marker?._markerData?.detail;

                if (label && label.toLowerCase() === landName.toLowerCase()) {
                  return { label, detail };
                }
              }

              return null;
            }
            """,
            land_name
        )

        browser.close()

    if not result:
        return None

    info = extract_land_info(result["detail"])
    info["name"] = result["label"]
    return info

@app.get("/land_info")
@limiter.limit("5/second")
async def land_info(request: fastapi.Request):
    name = request.query_params.get("name")
    info = get_land_info(name)
    if not info:
        return {"error": "Not found."}
    return info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)