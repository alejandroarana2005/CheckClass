import asyncio
import json
import os
import time
from pathlib import Path

import cv2
import face_recognition
from dotenv import load_dotenv
import websockets

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

URL = os.getenv("BACKEND_WS")
if not URL:
    host = os.getenv("BACKEND_WS_HOST", "localhost:8000")
    seguro = os.getenv("BACKEND_WS_SECURE", "false").lower() == "true"
    protocolo = "wss" if seguro else "ws"
    URL = f"{protocolo}://{host}/ws"
ID_CURSO = int(os.getenv("ID_CURSO", "1"))
ID_DISPOSITIVO = os.getenv("ID_DISPOSITIVO", "salon-101")
CARPETA_FOTOS = "fotos"
ESPERA_SEGUNDOS = 10
VIDEO_FPS = 10
UMBRAL = 0.5  # menor distancia = más parecido


def cargar_rostros():
    codificaciones, ids = [], []
    for archivo in os.listdir(CARPETA_FOTOS):
        if not archivo.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        id_estudiante = int(archivo.split("_")[0])
        imagen = face_recognition.load_image_file(
            os.path.join(CARPETA_FOTOS, archivo)
        )
        encontrados = face_recognition.face_encodings(imagen)
        if encontrados:
            codificaciones.append(encontrados[0])
            ids.append(id_estudiante)
    return codificaciones, ids


async def main():
    conocidos, ids = cargar_rostros()
    print(f"Rostros cargados: {len(ids)}")

    camara = cv2.VideoCapture(0)
    if not camara.isOpened():
        raise RuntimeError("No se pudo abrir la cámara predeterminada.")

    ultimo_envio = {}
    ultimo_frame = 0.0

    try:
        async with websockets.connect(URL) as ws:
            while True:
                ok, frame = camara.read()
                if not ok:
                    break

                # Reducir la imagen acelera el reconocimiento
                pequeno = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb = cv2.cvtColor(pequeno, cv2.COLOR_BGR2RGB)

                ubicaciones = face_recognition.face_locations(rgb)
                codificaciones = face_recognition.face_encodings(rgb, ubicaciones)

                for codificacion in codificaciones:
                    if not conocidos:
                        break
                    distancias = face_recognition.face_distance(
                        conocidos, codificacion
                    )
                    mejor = int(distancias.argmin())

                    if distancias[mejor] < UMBRAL:
                        id_estudiante = ids[mejor]
                        ahora = time.time()
                        if ahora - ultimo_envio.get(id_estudiante, 0) > ESPERA_SEGUNDOS:
                            await ws.send(json.dumps({
                                "id_estudiante": id_estudiante,
                                "id_curso": ID_CURSO,
                                "confianza": round(1 - float(distancias[mejor]), 2),
                                "id_dispositivo": ID_DISPOSITIVO,
                            }))
                            ultimo_envio[id_estudiante] = ahora
                            print(f"Detectado estudiante {id_estudiante}")

                ahora_monotonic = time.monotonic()
                if ahora_monotonic - ultimo_frame >= 1 / VIDEO_FPS:
                    codificado, imagen = cv2.imencode(
                        ".jpg",
                        pequeno,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 70],
                    )
                    if not codificado:
                        raise RuntimeError("No se pudo codificar el fotograma.")
                    await ws.send(imagen.tobytes())
                    ultimo_frame = ahora_monotonic

                cv2.imshow("CheckClass", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                await asyncio.sleep(0)
    finally:
        camara.release()
        cv2.destroyAllWindows()


asyncio.run(main())