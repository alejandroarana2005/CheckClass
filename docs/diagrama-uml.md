# Diagrama UML — Modelo de datos

## PostgreSQL (datos relacionales)

```mermaid
classDiagram
    direction LR

    class estudiantes {
        +SERIAL id PK
        +TEXT nombre
        +TEXT codigo UK
        +JSONB codificacion_facial
        +TEXT estado
        +TIMESTAMPTZ fecha_registro
    }

    class cursos {
        +SERIAL id PK
        +TEXT nombre
        +TEXT docente
    }

    class matriculas {
        +SERIAL id PK
        +INT id_estudiante FK
        +INT id_curso FK
    }

    class asistencias {
        +SERIAL id PK
        +INT id_estudiante FK
        +INT id_curso FK
        +DATE fecha
        +TIMESTAMPTZ fecha_hora
        +TEXT estado
    }

    estudiantes "1" --> "0..*" matriculas : está matriculado en
    cursos      "1" --> "0..*" matriculas : tiene matriculados
    matriculas  "1" --> "0..*" asistencias : habilita
    estudiantes "1" --> "0..*" asistencias : registra
    cursos      "1" --> "0..*" asistencias : agrupa
```

### Restricciones destacadas

| Tabla | Restricción |
|---|---|
| `estudiantes` | `codigo` único; `estado` ∈ `{AC, IN}` |
| `cursos` | `(nombre, docente)` único |
| `matriculas` | `(id_estudiante, id_curso)` único |
| `asistencias` | `(id_estudiante, id_curso, fecha)` único |

---

## MongoDB (datos de documentos)

```mermaid
classDiagram
    direction LR

    class fotos_estudiantes {
        +ObjectId _id PK
        +INT id_estudiante UK
        +BinData foto
    }

    class eventos_deteccion {
        +ObjectId _id PK
        +INT id_estudiante
        +INT id_curso
        +FLOAT confianza
        +STRING id_dispositivo
        +Date timestamp
    }

    class notificaciones_panel {
        +ObjectId _id PK
        +INT id_estudiante
        +INT id_curso
        +STRING fecha
        +STRING nombre
        +STRING hora
    }
```

> Las colecciones de MongoDB no tienen claves foráneas formales. `id_estudiante` e `id_curso` corresponden a los IDs de PostgreSQL por convención.
