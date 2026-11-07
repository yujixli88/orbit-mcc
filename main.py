"""API + WebSocket. Запуск: uvicorn main:app --reload"""
import asyncio, pathlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from simulator import Satellite

sat, clients = Satellite(), set()

async def loop():
    while True:
        sat.step()
        data = sat.snapshot()
        for ws in list(clients):
            try: await ws.send_json(data)
            except Exception: clients.discard(ws)
        await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(loop()); yield; task.cancel()

app = FastAPI(title="MCC Satellite", lifespan=lifespan)

class Cmd(BaseModel):
    cmd: str
    arg: str | None = None

@app.get("/api/state")
def state(): return sat.snapshot()

@app.get("/api/track")
def track(): return sat.track()

@app.post("/api/command")
def command(c: Cmd): return sat.command(c.cmd, c.arg)

@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)

app.mount("/", StaticFiles(directory=pathlib.Path(file).parent, html=True))
