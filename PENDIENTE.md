# Estado pendiente del proyecto

## Resumen

El proyecto ya tiene un modelo relacional completo, validación de detecciones, sincronización entre instancias y un entorno local con Docker Compose, dos backends y Nginx. El trabajo quedó detenido antes de configurar el despliegue en la nube: todavía no se eligieron el proveedor del backend ni el proveedor de PostgreSQL.

## Avances terminados

1. **Modelo de datos:** [backend/schema.sql](./backend/schema.sql) crea las tablas de estudiantes, cursos, matrículas y asistencias, sus relaciones y restricciones. Incluye datos de prueba y una migración compatible con la tabla de asistencias anterior.
2. **Nombres en el panel:** [backend/main.py](./backend/main.py) devuelve nombres reales en el historial y en los avisos WebSocket; [panel-web/index.html](./panel-web/index.html) los muestra.
3. **Validación y errores:** el backend valida las detecciones, registra errores útiles, intenta conectarse a las bases al iniciar y reporta los fallos de PostgreSQL y MongoDB.
4. **Ejecución local:** [compose.yaml](./compose.yaml) inicia PostgreSQL, MongoDB, dos backends y Nginx. [infra/nginx.conf](./infra/nginx.conf) configura el proxy WebSocket. El módulo local se ejecuta en el computador anfitrión para poder usar la cámara.
5. **Sincronización entre backends:** MongoDB funciona como replica set local. Change streams distribuyen las notificaciones de asistencia entre las instancias; los fotogramas de video no se replican entre ellas.
6. **Variables de entorno y CORS:** [.env.example](./.env.example) contiene la plantilla de configuración. El backend exige orígenes permitidos y rechaza `*`. El módulo local y el panel admiten configurar el destino WebSocket y usar `wss://` cuando corresponde.

Las pruebas realizadas cubrieron la inicialización de bases, solicitudes HTTP y WebSocket a través de Nginx, propagación entre backends, recuperación ante interrupciones de las bases y rechazo de orígenes no autorizados. También se verificó que el backend falla al arrancar si `CORS_ORIGINS=*`.

## Pendiente

### Punto 7: despliegue en la nube

Está **pospuesto por decisión del usuario**. No se crearon servicios ni se configuraron dominios. Quedaron sin decidir:

- Proveedor y topología del backend: Render o Railway, y si el balanceador con dos backends debe estar también en la nube o basta con Compose local.
- Proveedor PostgreSQL: Neon o Supabase.
- Dominio del panel y subdominio del backend en Cloudflare.

La comparación preliminar encontró límites relevantes en los planes gratuitos: Render Free permite WebSockets y dominios propios, pero una sola instancia por servicio y 750 horas activas mensuales compartidas; Railway Free tiene créditos de uso limitados y una réplica por servicio. Por eso, antes de desplegar se debe confirmar qué compromiso se acepta entre costo cero, balanceo en la nube y disponibilidad. Revisar nuevamente los planes al retomar, porque pueden cambiar.

El punto incluye configurar Atlas, PostgreSQL, variables privadas, `wss://`, los dominios de DigitalPlat/Cloudflare y validar el despliegue. No cargar fotos ni codificaciones faciales reales sin autorización.

### Punto 8: documentación

- El [README.md](./README.md) ya contiene instrucciones locales y documentación de las decisiones implementadas.
- Falta crear el diagrama de arquitectura Mermaid en `docs/`.
- Falta completar la guía de despliegue cuando se elijan los proveedores.

### Punto 9: automatización opcional

No se han creado GitHub Actions.

## Para retomar

1. Elegir la arquitectura de despliegue y el proveedor PostgreSQL.
2. Configurar los servicios y secretos en los paneles de los proveedores; no subir credenciales al repositorio.
3. Probar HTTP, WebSocket seguro, base de datos, sincronización entre instancias y dominios.
4. Completar el diagrama y la documentación de despliegue.

Para volver a ejecutar Compose, primero crea `.env` a partir de `.env.example`; el `.env` temporal usado durante las pruebas fue eliminado. Si se conserva un volumen PostgreSQL anterior, cambiar `POSTGRES_PASSWORD` en `.env` no cambia por sí solo la contraseña guardada en ese volumen. El [README.md](./README.md) explica cómo manejar ese caso.

No se creó ningún commit ni se hizo push.
