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

## Modelo de datos

**PostgreSQL (datos oficiales)**

- `estudiantes`: id, nombre, código, codificación facial
- `cursos`: id, nombre, docente
- `matriculas`: id, id_estudiante, id_curso
- `asistencias`: id, id_estudiante, id_curso, fecha_hora,
