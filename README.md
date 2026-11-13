# CheckClass

Sistema de asistencia a clases por reconocimiento facial, con módulo local, comunicación en tiempo real por WebSocket y despliegue en la nube.

Proyecto de la asignatura de Arquitectura de Software, Ingeniería de Sistemas.

## Descripción

Un módulo local instalado en el salón captura video con la cámara, detecta y reconoce los rostros de los estudiantes y envía cada detección en tiempo real por WebSocket a un backend desplegado en la nube. El backend guarda los eventos crudos en MongoDB, registra la asistencia oficial en PostgreSQL y actualiza en vivo un panel web que muestra quién está presente.

## Cumplimiento de los requisitos

| Requisito | Cómo se cumple |
|---|---|
| Desplegado en la nube | Backend, bases de datos y panel web en servicios en la nube |
| Módulo local | Programa en Python con OpenCV que corre en el computador del salón |
| Socket | WebSocket entre el módulo local, el backend y el panel web |
| Cámara o micrófono | Cámara para capturar y reconocer rostros |
| Mínimo dos bases de datos | PostgreSQL (relacional) y MongoDB (documentos) |
| Balanceo de carga | Nginx repartiendo conexiones entre varias instancias del backend |
| Dominio | Dominio registrado con DigitalPlat FreeDomain |
| Todo en GitHub | Código, configuración y documentación en este repositorio |

## Arquitectura

1. La cámara del salón alimenta el módulo local.
2. El módulo local detecta y reconoce rostros.
3. Cada detección se envía por WebSocket al backend.
4. Nginx reparte las conexiones entre las instancias del backend.
5. El backend guarda el evento crudo en MongoDB.
6. El backend registra la asistencia oficial en PostgreSQL.
7. El panel web muestra la asistencia en vivo.

## Tecnologías

- **Lenguaje:** Python
- **Módulo local:** OpenCV y face_recognition
- **Backend:** FastAPI
- **Bases de datos:** PostgreSQL (Neon) y MongoDB (Atlas)
- **Balanceador:** Nginx
- **Contenedores:** Docker y Docker Compose
- **Hosting:** Render
- **Panel web:** HTML y JavaScript
- **DNS:** DigitalPlat FreeDomain

## URLs del proyecto

| Servicio | URL |
|---|---|
| Panel web | https://www.checkclass.qd.je |
| API y documentación | https://api.checkclass.qd.je/docs |
| Asistencias de hoy | https://api.checkclass.qd.je/asistencias/hoy |

## Cómo usar

El backend, las bases de datos y el panel web ya están desplegados en la nube. Solo es necesario correr el módulo local en el computador del salón para activar el reconocimiento facial.

**1. Instalar dependencias** (solo la primera vez):

```powershell
python -m pip install -r modulo-local\requirements.txt
```

**2. Crear el archivo `.env`** en la raíz del proyecto con el siguiente contenido:

```
BACKEND_WS_HOST=checkclass-backend.onrender.com
BACKEND_WS_SECURE=true
ID_CURSO=1
ID_DISPOSITIVO=salon-101
```

**3. Agregar fotos de referencia** en la carpeta `fotos/` con el formato `ID_nombre.jpg`, donde `ID` es el identificador del estudiante en la base de datos (por ejemplo: `1_alejandro.jpg`).

**4. Ejecutar el módulo local:**

```powershell
python modulo-local\main.py
```

Se abre una ventana con la cámara. Cuando se detecta un rostro registrado, la asistencia aparece automáticamente en el panel web. Para cerrar el módulo, presiona `Q` en la ventana de la cámara.

## Modelo de datos

**PostgreSQL (datos oficiales)**

- `estudiantes`: id, nombre, código único y codificación facial opcional (`JSONB`).
- `cursos`: id, nombre y docente.
- `matriculas`: relación entre estudiantes y cursos, única por pareja.
- `asistencias`: estudiante, curso, fecha, hora y estado; con una sola asistencia por estudiante, curso y fecha.

El esquema completo está en `backend/schema.sql`. El backend lo aplica automáticamente al iniciar.

## Validación y errores del backend

El WebSocket `/ws` valida que cada detección incluya IDs positivos, una confianza entre `0` y `1` y un ID de dispositivo no vacío. Si el JSON no cumple el formato, responde con `deteccion_invalida`; si el estudiante o su matrícula no existen, responde con `referencia_invalida`. Los fallos de MongoDB y PostgreSQL se registran en los logs y se informan como `mongodb_no_disponible` o `postgres_no_disponible`.

## Sincronización de paneles entre instancias

Cada instancia escucha un change stream de MongoDB en `notificaciones_panel`. Cuando se registra una asistencia, el backend crea allí un aviso idempotente por estudiante, curso y fecha; todos los backends reciben ese cambio y lo envían a sus propios paneles conectados. La restricción única de MongoDB evita duplicar el aviso si dos instancias procesan la misma detección al mismo tiempo.

Los change streams requieren un replica set o un clúster sharded. MongoDB Atlas en su plan gratuito incluye tres nodos replicados, lo que los hace compatibles sin costo adicional.
