import asyncio, json, os, sqlite3
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

HIST_DIR = "historia"
os.makedirs(HIST_DIR, exist_ok=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

aktywni = {}

def zapisz(kontakt, linia):
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
        data = await ws.receive_json()
        if data.get("type") != "login":
            await ws.close(); return
        nazwa = data["name"].strip().replace("|", "_")[:20]

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
                zapisz(do, f"[{nazwa}] {tekst}")
                zapisz(nazwa, f"[Ja] {tekst}")
                if do in aktywni:
                    try:
                        await aktywni[do].send_json({
                            "type": "msg", "from": nazwa, "text": tekst
                        })
                    except: pass
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
    for u, sock in list(aktywni.items()):
        lista = [k for k in aktywni if k != u]
        try:
            await sock.send_json({"type": "contacts", "contacts": lista})
        except:
            pass

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Komunikator</title>
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100vh; display: flex; background: #121212; color: #e0e0e0; }
  #login { position: fixed; inset: 0; background: #1e1e1e; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 15px; z-index: 10; }
  #login h2 { color: #fff; font-weight: 300; margin-bottom: 10px; }
  #login input, #login button { padding: 14px; width: 260px; font-size: 16px; border-radius: 8px; border: 1px solid #333; background: #2a2a2a; color: #fff; outline: none; }
  #login input:focus { border-color: #00a884; }
  #login button { background: #00a884; color: #fff; border: none; cursor: pointer; font-weight: bold; transition: 0.2s; }
  #login button:hover { background: #008f6f; }
  
  #sidebar { width: 35%; max-width: 250px; background: #1e1e1e; border-right: 1px solid #333; overflow-y: auto; display: flex; flex-direction: column; }
  #sidebar h3 { padding: 15px; background: #2a2a2a; color: #00a884; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
  #contacts { list-style: none; }
  #contacts li { padding: 15px; border-bottom: 1px solid #2a2a2a; cursor: pointer; font-size: 15px; transition: 0.2s; }
  #contacts li:hover { background: #2a2a2a; }
  #contacts li.active { background: #333; border-left: 4px solid #00a884; font-weight: bold; }
  
  #chat { flex: 1; display: flex; flex-direction: column; background: #121212; }
  #header { padding: 15px; background: #1e1e1e; border-bottom: 1px solid #333; color: #fff; font-weight: 600; font-size: 16px; }
  #messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 10px; }
  .msg { max-width: 75%; padding: 10px 14px; border-radius: 12px; font-size: 15px; line-height: 1.4; white-space: pre-wrap; word-wrap: break-word; box-shadow: 0 1px 2px rgba(0,0,0,0.3); }
  .msg.sent { background: #005c4b; color: #fff; align-self: flex-end; border-bottom-right-radius: 2px; }
  .msg.received { background: #2a2a2a; color: #e0e0e0; align-self: flex-start; border-bottom-left-radius: 2px; }
  
  #input-area { display: flex; padding: 15px; background: #1e1e1e; border-top: 1px solid #333; gap: 10px; }
  #input-area input { flex: 1; padding: 12px 16px; border: 1px solid #333; border-radius: 20px; font-size: 15px; outline: none; background: #2a2a2a; color: #fff; }
  #input-area input:focus { border-color: #00a884; }
  #input-area button { padding: 12px 24px; background: #00a884; color: #fff; border: none; border-radius: 20px; cursor: pointer; font-weight: bold; transition: 0.2s; }
  #input-area button:hover { background: #008f6f; }
  #input-area button:disabled, #input-area input:disabled { opacity: 0.4; cursor: not-allowed; }
  #status { font-size: 12px; color: #888; padding: 5px 15px; background: #1e1e1e; }
</style>
</head>
<body>
<div id="login">
  <h2>Komunikator</h2>
  <input id="in-name" placeholder="Twoja nazwa" autocomplete="username">
  <button onclick="zaloguj()">Połącz</button>
  <div id="login-err" style="color:#d32f2f;font-size:14px;"></div>
</div>
<div id="sidebar">
  <h3>Kontakty</h3>
  <ul id="contacts"></ul>
</div>
<div id="chat">
  <div id="header">Wybierz kontakt</div>
  <div id="messages"></div>
  <div id="status">Nie połączono</div>
  <div id="input-area">
    <input id="msg-input" placeholder="Wiadomość..." disabled>
    <button id="send-btn" onclick="wyslij()" disabled>Wyślij</button>
  </div>
</div>
<script>
const HOST = "komunikator-j1q4.onrender.com";
const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + HOST + "/ws";
let ws, myName = "", current = null, reconnectTimer = null;

function zaloguj() {
  const n = document.getElementById("in-name").value.trim();
  if (!n) { document.getElementById("login-err").textContent = "Podaj nazwę"; return; }
  myName = n;
  polacz();
}

function polacz() {
  document.getElementById("status").textContent = "Łączenie...";
  ws = new WebSocket(WS_URL);
  ws.onopen = () => { ws.send(JSON.stringify({ type: "login", name: myName })); };
  ws.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.type === "ok") {
      document.getElementById("login").style.display = "none";
      document.getElementById("status").textContent = "Zalogowano jako " + myName;
    } else if (d.type === "contacts") {
      rysujKontakty(d.contacts);
    } else if (d.type === "msg") {
      if (current === d.from) dodajWiadomosc(d.from, d.text, "received");
      else document.getElementById("status").textContent = "Nowa wiadomość od " + d.from;
    } else if (d.type === "sent") {
      if (current === d.to) dodajWiadomosc("Ja", d.text, "sent");
    } else if (d.type === "historia") {
      if (current !== d.with) return;
      const box = document.getElementById("messages");
      box.innerHTML = "";
      d.lines.forEach(l => {
        const jestMoja = l.startsWith("[Ja]");
        const tekst = l.replace(/^\[[^\]]+\]\s/, "");
        dodajWiadomosc(jestMoja ? "Ja" : d.with, tekst, jestMoja ? "sent" : "received");
      });
    }
  };
  ws.onclose = () => {
    document.getElementById("status").textContent = "Rozłączono – łączę ponownie...";
    if (!reconnectTimer) reconnectTimer = setTimeout(() => { reconnectTimer = null; polacz(); }, 3000);
  };
}

function rysujKontakty(lista) {
  const ul = document.getElementById("contacts");
  ul.innerHTML = "";
  lista.forEach(k => {
    const li = document.createElement("li");
    li.textContent = k;
    if (k === current) li.classList.add("active");
    li.onclick = () => wybierz(k);
    ul.appendChild(li);
  });
}

function wybierz(kontakt) {
  current = kontakt;
  document.getElementById("header").textContent = kontakt;
  document.getElementById("msg-input").disabled = false;
  document.getElementById("send-btn").disabled = false;
  document.getElementById("messages").innerHTML = "";
  document.querySelectorAll("#contacts li").forEach(li => li.classList.toggle("active", li.textContent === kontakt));
  ws.send(JSON.stringify({ type: "historia", with: kontakt }));
}

function dodajWiadomosc(kto, tekst, typ) {
  const box = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "msg " + typ;
  div.textContent = tekst;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function wyslij() {
  const inp = document.getElementById("msg-input");
  const t = inp.value.trim();
  if (!t || !current || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "msg", to: current, text: t }));
  inp.value = "";
}

document.getElementById("msg-input").addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); wyslij(); }
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8765)))
