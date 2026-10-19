import asyncio, json, os, sqlite3
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse  # <-- DODANA LINIJKA
import uvicorn

HIST_DIR = "historia"
os.makedirs(HIST_DIR, exist_ok=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Aktywni użytkownicy: {nazwa: websocket}
aktywni = {}

def zapisz(kontakt, linia):
    """Dopisuje linię do pliku tekstowego kontaktu."""
    sciezka = os.path.join(HIST_DIR, f"{kontakt}.txt")
    with open(sciezka, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {linia}\n")

def wczytaj(kontakt):
    sciezka = os.path.join(HIST_DIR, f"{kontakt}.txt")
    if not os.path.exists(sciezka):
        return []
    with open(sciezka, "r", encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f]

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    nazwa = None
    try:
        # Pierwsza wiadomość: {"type":"login","name":"Jan"}
        data = await ws.receive_json()
        if data.get("type") != "login":
            await ws.close(); return
        nazwa = data["name"].strip().replace("|", "_")[:20]

        # Jeśli już zalogowany – zamknij stare połączenie
        if nazwa in aktywni:
            try: await aktywni[nazwa].close()
            except: pass
        aktywni[nazwa] = ws

        await ws.send_json({"type": "ok", "name": nazwa})
        await rozeslij_liste()

        while True:
            data = await ws.receive_json()

            if data["type"] == "msg":
                do = data["to"]
                tekst = data["text"].strip()
                if not tekst: continue
                # Zapisz historię u obu stron
                zapisz(do, f"[{nazwa}] {tekst}")
                zapisz(nazwa, f"[Ja] {tekst}")
                # Wyślij do odbiorcy jeśli online
                if do in aktywni:
                    try:
                        await aktywni[do].send_json({
                            "type": "msg", "from": nazwa, "text": tekst
                        })
                    except: pass
                # Potwierdzenie dla nadawcy
                await ws.send_json({"type": "sent", "to": do, "text": tekst})

            elif data["type"] == "historia":
                kontakt = data["with"]
                await ws.send_json({
                    "type": "historia",
                    "with": kontakt,
                    "lines": wczytaj(kontakt)
                })

    except WebSocketDisconnect:
        pass
    finally:
        if nazwa and aktywni.get(nazwa) is ws:
            del aktywni[nazwa]
            await rozeslij_liste()

async def rozeslij_liste():
    """Wysyła każdemu aktualną listę kontaktów (bez siebie)."""
    for u, sock in list(aktywni.items()):
        lista = [k for k in aktywni if k != u]
        try:
            await sock.send_json({"type": "contacts", "contacts": lista})
        except:
            pass

# --- DODANE, ABY STRONA DZIAŁAŁA Z SERWERA ---
@app.get("/")
async def index():
    return FileResponse("index.html")
# ---------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8765)))
