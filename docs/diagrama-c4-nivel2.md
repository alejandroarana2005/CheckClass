# Diagrama C4 — Nivel 2: Contenedores

```mermaid
C4Container
    title CheckClass — Diagrama de Contenedores

    Person(docente, "Docente", "Consulta y monitorea la asistencia en tiempo real desde cualquier navegador")
    Person(salon, "Computador del salón", "Ejecuta el módulo local con acceso a la cámara")

    System_Boundary(checkclass, "CheckClass") {

        Container(modulo, "Módulo Local", "Python · OpenCV · face_recognition", "Captura video de la cámara, detecta y reconoce rostros, envía detecciones y frames al backend por WebSocket")

        Container(nginx, "Nginx", "Nginx 1.27 · Render", "Balanceador de carga; distribuye el tráfico HTTP y WebSocket entre las instancias del backend")

        Container(backend1, "Backend — Instancia 1", "FastAPI · Python · Render", "Valida detecciones, registra asistencias, sirve la API REST y el WebSocket del panel")

        Container(backend2, "Backend — Instancia 2", "FastAPI · Python · Render", "Instancia idéntica a la anterior para alta disponibilidad")

        Container(panel, "Panel Web", "HTML · JavaScript · Render Static", "Muestra en tiempo real quién está presente, permite registrar estudiantes y consultar asistencia por fecha")
    }

    System_Ext(postgres, "PostgreSQL", "Neon — plan gratuito", "Almacena estudiantes, cursos, matrículas y asistencias de forma relacional")

    System_Ext(mongo, "MongoDB", "Atlas — plan gratuito (3 nodos)", "Almacena eventos crudos de detección, fotos de referencia y notificaciones entre instancias del backend")

    Rel(salon,    modulo,   "Ejecuta el programa")
    Rel(docente,  panel,    "Abre en el navegador", "HTTPS")

    Rel(modulo,   nginx,    "Envía detecciones y frames de video", "WebSocket · wss://")
    Rel(panel,    nginx,    "Carga la asistencia y recibe eventos en vivo", "HTTPS + WebSocket · wss://")

    Rel(nginx,    backend1, "Enruta tráfico", "HTTP · proxy_pass")
    Rel(nginx,    backend2, "Enruta tráfico", "HTTP · proxy_pass")

    Rel(backend1, postgres, "Lee y escribe estudiantes, matrículas y asistencias", "asyncpg · TLS")
    Rel(backend2, postgres, "Lee y escribe estudiantes, matrículas y asistencias", "asyncpg · TLS")

    Rel(backend1, mongo,    "Guarda eventos, fotos y notificaciones", "Motor · TLS")
    Rel(backend2, mongo,    "Guarda eventos, fotos y notificaciones", "Motor · TLS")

    BiRel(backend1, backend2, "Sincroniza notificaciones al panel", "MongoDB Change Streams")
```

## Descripción de los contenedores

| Contenedor | Tecnología | Responsabilidad |
|---|---|---|
| Módulo Local | Python, OpenCV, face_recognition | Detecta y reconoce rostros; envía eventos al backend |
| Nginx | Nginx 1.27 | Balancea carga entre las dos instancias del backend |
| Backend (×2) | FastAPI, asyncpg, Motor | API REST + WebSocket; persiste asistencias; sincroniza paneles |
| Panel Web | HTML, JavaScript | Interfaz en tiempo real para el docente |
| PostgreSQL | Neon | Datos relacionales estructurados |
| MongoDB | Atlas | Eventos crudos, fotos y coordinación entre instancias |
