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
- **Bases de datos:** PostgreSQL y MongoDB
- **Balanceador:** Nginx
- **Contenedores:** Docker y Docker Compose
- **Panel web:** HTML y JavaScript
- **DNS:** DigitalPlat FreeDomain y Cloudflare

## Ejecutar localmente

Se requiere Docker Desktop con el motor de Docker iniciado. Desde la carpeta raíz, crea el archivo local de variables y cambia el marcador de contraseña:

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` está excluido de Git; no compartas ni subas ese archivo. `.env.example` solo contiene nombres de variables y valores de referencia, no credenciales ni URL de conexión a bases de datos.

Luego inicia los servicios:

```powershell
docker compose up --build -d
docker compose ps
```

Docker Compose inicia PostgreSQL, MongoDB, dos instancias del backend y Nginx. Nginx balancea las solicitudes HTTP y WebSocket y queda disponible en `http://localhost:8000`; la documentación interactiva está en `http://localhost:8000/docs`. El módulo local se ejecuta en el computador anfitrión para acceder a la cámara y a la ventana de OpenCV. Conecta la cámara, agrega las fotos de referencia en `fotos` (por ejemplo, `1_nombre.jpg`, donde `1` es el ID del estudiante) e inicia el módulo local en otra terminal:

```powershell
python -m pip install -r modulo-local\requirements.txt
python modulo-local\main.py
```

Deja el módulo ejecutándose mientras uses el panel. El video se envía en JPEG reducido a un máximo de 10 FPS al backend local. Para detener los servicios sin borrar los datos:

```powershell
docker compose down
```

MongoDB se publica en el puerto local `27018` para evitar conflictos con servicios que ya usen `27017`. Las credenciales locales se leen desde `.env`; el marcador de contraseña debe reemplazarse antes del primer inicio.

Si ya existe un volumen `postgres_data` de una ejecución anterior, cambiar `POSTGRES_PASSWORD` en `.env` no cambia la contraseña guardada dentro de PostgreSQL. Conserva la contraseña de ese volumen o actualízala sin borrar datos: ejecuta `docker compose exec postgres psql -U asistencia -d postgres` y, dentro de `psql`, usa `\password asistencia`.

Para abrir el panel con un origen permitido por CORS, inicia un servidor estático en otra terminal y visita `http://localhost:5500`:

```powershell
python -m http.server 5500 --directory panel-web
```

El panel deriva automáticamente `http`/`ws` o `https`/`wss` del protocolo de la página. Si el backend está en otro host, agrega `?api=HOST_DEL_BACKEND` a la dirección del panel y configura ese origen en `CORS_ORIGINS`.

El módulo local carga `.env` automáticamente. Para usarlo con un backend remoto, define `BACKEND_WS_HOST` y `BACKEND_WS_SECURE=true` en `.env`; para una conexión local se usan `localhost:8000` y `false`.

## Modelo de datos

**PostgreSQL (datos oficiales)**

- `estudiantes`: id, nombre, código único y codificación facial opcional (`JSONB`).
- `cursos`: id, nombre y docente.
- `matriculas`: relación entre estudiantes y cursos, única por pareja.
- `asistencias`: estudiante, curso, fecha, hora y estado; referencias a estudiante, curso y matrícula, con una sola asistencia por estudiante, curso y fecha.

El esquema y los datos de prueba están en `backend/schema.sql`. El backend lo aplica al iniciar; el script se puede ejecutar repetidamente y migra la tabla de asistencias mínima que ya existía. Los rostros de ejemplo no se incluyen: el módulo local sigue cargando fotos desde `fotos/`.

## Validación y errores del backend

El WebSocket `/ws` valida que cada detección incluya IDs positivos, una confianza entre `0` y `1` y un ID de dispositivo no vacío. Si el JSON no cumple el formato, responde con `deteccion_invalida`; si el estudiante o su matrícula no existen, responde con `referencia_invalida`. Los fallos de MongoDB y PostgreSQL se registran en los logs y se informan como `mongodb_no_disponible` o `postgres_no_disponible`. Al iniciar, el backend intenta conectarse a ambas bases hasta tres veces; sus clientes mantienen la reconexión ante caídas transitorias.

El backend solo habilita CORS para los orígenes enumerados en `CORS_ORIGINS` y rechaza el comodín `*`. También verifica el origen en las conexiones WebSocket que lo envían; el módulo local de Python, que no envía encabezado `Origin`, puede conectarse normalmente.

## Sincronización de paneles entre instancias

Cada instancia escucha un change stream de MongoDB en `notificaciones_panel`. Cuando se registra una asistencia, el backend crea allí un aviso idempotente por estudiante, curso y fecha; todos los backends reciben ese cambio y lo envían a sus propios paneles conectados. La restricción única de MongoDB evita duplicar el aviso si dos instancias procesan la misma detección al mismo tiempo.

Los change streams requieren un replica set o un clúster sharded. El Compose local inicia MongoDB como replica set de un nodo para permitir probar el mismo mecanismo. Atlas documenta que sus clústeres gratuitos tienen tres nodos replicados; por tanto, son compatibles con change streams, sin añadir Redis ni otro servicio de pago. La interrupción del stream se registra y se reintenta con espera creciente.

Referencias oficiales: [límites de clústeres gratuitos de Atlas](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/) y [change streams de MongoDB](https://www.mongodb.com/docs/manual/changeStreams/).
