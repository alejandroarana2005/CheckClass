import asyncio
import logging
import os
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pymongo.errors import DuplicateKeyError, PyMongoError

import asyncpg

app = FastAPI()
logger = logging.getLogger(__name__)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if not cors_origins or "*" in cors_origins:
    raise RuntimeError(
        "CORS_ORIGINS debe enumerar orígenes permitidos y no puede contener '*'."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


POSTGRES_URL = os.getenv("POSTGRES_URL")
MONGO_URL = os.getenv("MONGO_URL")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "")
MONGO_HOST = os.getenv("MONGO_HOST", "")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_REPLICA_SET = os.getenv("MONGO_REPLICA_SET")

if not POSTGRES_URL and not all(
    (POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
):
    raise RuntimeError(
        "Configura POSTGRES_URL o las variables POSTGRES_HOST, POSTGRES_USER, "
        "POSTGRES_PASSWORD y POSTGRES_DB."
    )
if not MONGO_URL and not MONGO_HOST:
    raise RuntimeError("Configura MONGO_URL o MONGO_HOST.")

if MONGO_URL:
    mongo = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
elif MONGO_REPLICA_SET:
    mongo = AsyncIOMotorClient(
        host=MONGO_HOST,
        port=MONGO_PORT,
        replicaSet=MONGO_REPLICA_SET,
        serverSelectionTimeoutMS=5000,
    )
else:
    mongo = AsyncIOMotorClient(
        host=MONGO_HOST,
        port=MONGO_PORT,
        serverSelectionTimeoutMS=5000,
    )
base_datos = mongo["asistencia"]
eventos = base_datos["eventos_deteccion"]
notificaciones = base_datos["notificaciones_panel"]
fotos_col = base_datos["fotos_estudiantes"]


class Deteccion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_estudiante: int = Field(gt=0)
    id_curso: int = Field(gt=0)
    confianza: float = Field(ge=0, le=1)
    id_dispositivo: str = Field(min_length=1, max_length=100)


pool: asyncpg.Pool | None = None
paneles: set[WebSocket] = set()
tarea_notificaciones: asyncio.Task[None] | None = None


async def enviar_error(ws: WebSocket, codigo: str, mensaje: str) -> None:
    await ws.send_json({"error": {"codigo": codigo, "mensaje": mensaje}})


async def aceptar_websocket(ws: WebSocket) -> bool:
    origen = ws.headers.get("origin")
    if origen and origen not in cors_origins:
        logger.warning("Conexión WebSocket rechazada para el origen %s.", origen)
        await ws.close(code=1008)
        return False
    await ws.accept()
    return True


async def avisar_paneles(datos: dict[str, Any] | bytes) -> None:
    for panel_ws in list(paneles):
        try:
            if isinstance(datos, bytes):
                await panel_ws.send_bytes(datos)
            else:
                await panel_ws.send_json(datos)
        except (WebSocketDisconnect, RuntimeError) as error:
            paneles.discard(panel_ws)
            logger.warning("Se quitó un panel desconectado: %s", error)


async def escuchar_notificaciones() -> None:
    espera = 1
    while True:
        try:
            async with notificaciones.watch(
                [{"$match": {"operationType": "insert"}}]
            ) as cambios:
                logger.info("Escuchando notificaciones compartidas de MongoDB.")
                espera = 1
                async for cambio in cambios:
                    documento = cambio["fullDocument"]
                    await avisar_paneles({
                        "id_estudiante": documento["id_estudiante"],
                        "nombre": documento["nombre"],
                        "hora": documento["hora"],
                    })
        except asyncio.CancelledError:
            raise
        except PyMongoError:
            logger.exception(
                "Se perdió el change stream de MongoDB; se reintentará en %d s.",
                espera,
            )
            await asyncio.sleep(espera)
            espera = min(espera * 2, 30)


@app.on_event("startup")
async def iniciar():
    global pool, tarea_notificaciones
    try:
        esquema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    except OSError:
        logger.exception("No se pudo leer el esquema de PostgreSQL.")
        raise

    for intento in range(1, 4):
        try:
            if POSTGRES_URL:
                pool = await asyncpg.create_pool(POSTGRES_URL, timeout=5)
            else:
                pool = await asyncpg.create_pool(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    database=POSTGRES_DB,
                    timeout=5,
                )
            async with pool.acquire() as con:
                await con.execute(esquema)
            await mongo.admin.command("ping")
            await notificaciones.create_index(
                [("id_estudiante", 1), ("id_curso", 1), ("fecha", 1)],
                unique=True,
                name="notificacion_estudiante_curso_fecha_unica",
            )
            tarea_notificaciones = asyncio.create_task(escuchar_notificaciones())
            logger.info("Conexión con PostgreSQL y MongoDB lista.")
            return
        except (asyncpg.PostgresError, PyMongoError, OSError, asyncio.TimeoutError):
            if pool is not None:
                await pool.close()
                pool = None
            logger.exception(
                "No se pudo conectar o inicializar las bases de datos (intento %d/3).",
                intento,
            )
            if intento == 3:
                raise
            await asyncio.sleep(intento)


@app.on_event("shutdown")
async def cerrar_conexiones():
    if tarea_notificaciones is not None:
        tarea_notificaciones.cancel()
        try:
            await tarea_notificaciones
        except asyncio.CancelledError:
            pass
    if pool is not None:
        await pool.close()
    mongo.close()


@app.websocket("/ws")
async def recibir_detecciones(ws: WebSocket):
    if not await aceptar_websocket(ws):
        return
    try:
        while True:
            mensaje = await ws.receive()
            if mensaje["type"] == "websocket.disconnect":
                break
            if mensaje.get("bytes") is not None:
                await avisar_paneles(mensaje["bytes"])
                continue
            if mensaje.get("text") is None:
                continue

            try:
                deteccion = Deteccion.model_validate_json(mensaje["text"])
            except ValidationError as error:
                detalles = [
                    {
                        "campo": ".".join(str(parte) for parte in detalle["loc"]),
                        "mensaje": detalle["msg"],
                    }
                    for detalle in error.errors()
                ]
                logger.warning("Detección inválida: %s", detalles)
                await ws.send_json({
                    "error": {
                        "codigo": "deteccion_invalida",
                        "mensaje": "El JSON no cumple el formato esperado.",
                        "detalles": detalles,
                    }
                })
                continue

            ahora = datetime.now(timezone.utc)

            try:
                await eventos.insert_one({
                    **deteccion.model_dump(),
                    "timestamp": ahora,
                })
            except (PyMongoError, OSError, asyncio.TimeoutError):
                logger.exception("No se pudo guardar el evento crudo en MongoDB.")
                await enviar_error(
                    ws,
                    "mongodb_no_disponible",
                    "No se pudo guardar la detección; inténtalo de nuevo.",
                )
                continue

            if pool is None:
                logger.error("La detección llegó sin un pool de PostgreSQL disponible.")
                await enviar_error(
                    ws,
                    "postgres_no_disponible",
                    "La asistencia oficial no está disponible temporalmente.",
                )
                continue

            try:
                async with pool.acquire() as con:
                    nombre = await con.fetchval(
                        "SELECT nombre FROM estudiantes WHERE id=$1",
                        deteccion.id_estudiante,
                    )
                    asistencia_id = await con.fetchval(
                        """INSERT INTO asistencias
                           (id_estudiante, id_curso, fecha, fecha_hora, estado)
                           VALUES ($1,$2,$3,$4,'presente')
                           ON CONFLICT (id_estudiante, id_curso, fecha) DO NOTHING
                           RETURNING id""",
                        deteccion.id_estudiante, deteccion.id_curso,
                        date.today(), ahora,
                    )
            except asyncpg.ForeignKeyViolationError:
                logger.warning(
                    "Detección rechazada por matrícula o referencia inexistente: "
                    "estudiante=%d curso=%d",
                    deteccion.id_estudiante,
                    deteccion.id_curso,
                )
                await enviar_error(
                    ws,
                    "referencia_invalida",
                    "El estudiante no existe o no está matriculado en el curso.",
                )
                continue
            except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
                logger.exception("No se pudo registrar la asistencia en PostgreSQL.")
                await enviar_error(
                    ws,
                    "postgres_no_disponible",
                    "La asistencia oficial no está disponible temporalmente.",
                )
                continue

            try:
                await notificaciones.update_one(
                    {
                        "id_estudiante": deteccion.id_estudiante,
                        "id_curso": deteccion.id_curso,
                        "fecha": date.today().isoformat(),
                    },
                    {
                        "$setOnInsert": {
                            "id_estudiante": deteccion.id_estudiante,
                            "id_curso": deteccion.id_curso,
                            "fecha": date.today().isoformat(),
                            "nombre": nombre,
                            "hora": ahora.isoformat(),
                        }
                    },
                    upsert=True,
                )
            except DuplicateKeyError:
                logger.debug(
                    "Otra instancia publicó la notificación de asistencia primero."
                )
            except (PyMongoError, OSError, asyncio.TimeoutError):
                logger.exception(
                    "La asistencia se registró, pero no se pudo publicar el aviso."
                )
                await enviar_error(
                    ws,
                    "notificacion_pendiente",
                    "La asistencia se registró; el aviso a los paneles se reintentará "
                    "con la siguiente detección.",
                )
                continue

            if asistencia_id is not None:
                logger.info(
                    "Asistencia registrada: estudiante=%d curso=%d",
                    deteccion.id_estudiante,
                    deteccion.id_curso,
                )
    except WebSocketDisconnect:
        logger.debug("El módulo local cerró su WebSocket.")


@app.websocket("/panel")
async def panel(ws: WebSocket):
    if not await aceptar_websocket(ws):
        return
    paneles.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        logger.debug("Se desconectó un panel.")
    finally:
        paneles.discard(ws)


@app.get("/estudiantes")
async def listar_estudiantes():
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    try:
        async with pool.acquire() as con:
            filas = await con.fetch(
                "SELECT id, nombre, codigo FROM estudiantes ORDER BY nombre"
            )
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as error:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.") from error
    return [dict(f) for f in filas]


@app.post("/estudiantes", status_code=201)
async def crear_estudiante(nombre: str = Form(...), foto: UploadFile = File(...)):
    if pool is None:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")
    contenido = await foto.read()
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                id_est = await con.fetchval(
                    "INSERT INTO estudiantes (nombre, codigo) "
                    "VALUES ($1, gen_random_uuid()::text) RETURNING id",
                    nombre,
                )
                await con.execute(
                    "UPDATE estudiantes SET codigo = $1 WHERE id = $2",
                    f"EST-{id_est:03d}", id_est,
                )
                await con.execute(
                    "INSERT INTO matriculas (id_estudiante, id_curso) "
                    "SELECT $1, id FROM cursos LIMIT 1 ON CONFLICT DO NOTHING",
                    id_est,
                )
    except asyncpg.PostgresError as error:
        logger.exception("Error al crear el estudiante.")
        raise HTTPException(status_code=500, detail="Error al guardar el estudiante.") from error
    try:
        await fotos_col.update_one(
            {"id_estudiante": id_est},
            {"$set": {"id_estudiante": id_est, "foto": contenido}},
            upsert=True,
        )
    except PyMongoError:
        logger.exception("No se pudo guardar la foto del estudiante en MongoDB.")
    return {"id": id_est, "nombre": nombre, "codigo": f"EST-{id_est:03d}"}


@app.get("/estudiantes/{id_estudiante}/foto")
async def obtener_foto(id_estudiante: int):
    try:
        doc = await fotos_col.find_one({"id_estudiante": id_estudiante})
    except PyMongoError as error:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.") from error
    if not doc or "foto" not in doc:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    return Response(content=bytes(doc["foto"]), media_type="image/jpeg")


@app.get("/asistencias/hoy")
async def asistencias_hoy():
    if pool is None:
        logger.error("La consulta de asistencias llegó sin PostgreSQL disponible.")
        raise HTTPException(
            status_code=503,
            detail="Las asistencias no están disponibles temporalmente.",
        )

    try:
        async with pool.acquire() as con:
            filas = await con.fetch(
                """SELECT a.*, e.nombre
                   FROM asistencias AS a
                   LEFT JOIN estudiantes AS e ON e.id=a.id_estudiante
                   WHERE a.fecha=$1""",
                date.today(),
            )
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as error:
        logger.exception("No se pudo consultar la asistencia de hoy.")
        raise HTTPException(
            status_code=503,
            detail="Las asistencias no están disponibles temporalmente.",
        ) from error
    return [dict(f) for f in filas]