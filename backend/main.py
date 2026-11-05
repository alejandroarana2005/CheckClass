import os
from datetime import datetime, date

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorClient
import asyncpg

app = FastAPI()

POSTGRES_URL = os.getenv("POSTGRES_URL")
MONGO_URL = os.getenv("MONGO_URL")

mongo = AsyncIOMotorClient(MONGO_URL)
eventos = mongo["asistencia"]["eventos_deteccion"]

pool = None
paneles = set()


@app.on_event("startup")
async def iniciar():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL)
    async with pool.acquire() as con:
        await con.execute("""
            CREATE TABLE IF NOT EXISTS asistencias (
                id SERIAL PRIMARY KEY,
                id_estudiante INT NOT NULL,
                id_curso INT NOT NULL,
                fecha_hora TIMESTAMP NOT NULL,
                estado TEXT NOT NULL
            )
        """)


@app.websocket("/ws")
async def recibir_detecciones(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            datos = await ws.receive_json()
            ahora = datetime.utcnow()

            # 1. Evento crudo en MongoDB
            await eventos.insert_one({
                "id_estudiante": datos["id_estudiante"],
                "id_curso": datos["id_curso"],
                "timestamp": ahora,
                "confianza": datos["confianza"],
                "id_dispositivo": datos["id_dispositivo"],
            })

            # 2. Asistencia oficial en PostgreSQL (una por día y curso)
            async with pool.acquire() as con:
                existe = await con.fetchval(
                    """SELECT 1 FROM asistencias
                       WHERE id_estudiante=$1 AND id_curso=$2
                       AND fecha_hora::date=$3""",
                    datos["id_estudiante"], datos["id_curso"], date.today(),
                )
                if not existe:
                    await con.execute(
                        """INSERT INTO asistencias
                           (id_estudiante, id_curso, fecha_hora, estado)
                           VALUES ($1,$2,$3,'presente')""",
                        datos["id_estudiante"], datos["id_curso"], ahora,
                    )
                    # 3. Avisar a los paneles conectados
                    for p in list(paneles):
                        await p.send_json({
                            "id_estudiante": datos["id_estudiante"],
                            "hora": ahora.isoformat(),
                        })
    except WebSocketDisconnect:
        pass


@app.websocket("/panel")
async def panel(ws: WebSocket):
    await ws.accept()
    paneles.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        paneles.discard(ws)


@app.get("/asistencias/hoy")
async def asistencias_hoy():
    async with pool.acquire() as con:
        filas = await con.fetch(
            "SELECT * FROM asistencias WHERE fecha_hora::date=$1", date.today()
        )
    return [dict(f) for f in filas]