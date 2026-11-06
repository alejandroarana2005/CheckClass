CREATE TABLE IF NOT EXISTS estudiantes (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    codigo TEXT NOT NULL UNIQUE,
    codificacion_facial JSONB
);

CREATE TABLE IF NOT EXISTS cursos (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    docente TEXT NOT NULL,
    CONSTRAINT cursos_nombre_docente_unicos UNIQUE (nombre, docente)
);

CREATE TABLE IF NOT EXISTS matriculas (
    id SERIAL PRIMARY KEY,
    id_estudiante INT NOT NULL REFERENCES estudiantes(id),
    id_curso INT NOT NULL REFERENCES cursos(id),
    CONSTRAINT matriculas_estudiante_curso_unicos UNIQUE (id_estudiante, id_curso)
);

CREATE TABLE IF NOT EXISTS asistencias (
    id SERIAL PRIMARY KEY,
    id_estudiante INT NOT NULL,
    id_curso INT NOT NULL,
    fecha DATE,
    fecha_hora TIMESTAMPTZ NOT NULL,
    estado TEXT NOT NULL
);

ALTER TABLE asistencias ADD COLUMN IF NOT EXISTS fecha DATE;

UPDATE asistencias
SET fecha = fecha_hora::date
WHERE fecha IS NULL;

ALTER TABLE asistencias ALTER COLUMN fecha SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'asistencias'
          AND column_name = 'fecha_hora'
          AND table_schema = current_schema()
          AND data_type = 'timestamp without time zone'
    ) THEN
        ALTER TABLE asistencias
        ALTER COLUMN fecha_hora TYPE TIMESTAMPTZ
        USING fecha_hora AT TIME ZONE 'UTC';
    END IF;
END
$$;

INSERT INTO estudiantes (nombre, codigo)
SELECT datos.nombre, datos.codigo
FROM (VALUES
    ('Juan Perez', 'EST-001'),
    ('Maria Gomez', 'EST-002')
) AS datos(nombre, codigo)
WHERE NOT EXISTS (SELECT 1 FROM asistencias)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO cursos (nombre, docente)
SELECT 'Arquitectura de Software', 'Docente de prueba'
WHERE NOT EXISTS (SELECT 1 FROM asistencias)
ON CONFLICT (nombre, docente) DO NOTHING;

INSERT INTO matriculas (id_estudiante, id_curso)
SELECT e.id, c.id
FROM estudiantes AS e
CROSS JOIN cursos AS c
WHERE e.codigo IN ('EST-001', 'EST-002')
  AND c.nombre = 'Arquitectura de Software'
  AND c.docente = 'Docente de prueba'
ON CONFLICT (id_estudiante, id_curso) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'asistencias_estudiante_fk'
          AND conrelid = 'asistencias'::regclass
    ) THEN
        ALTER TABLE asistencias
        ADD CONSTRAINT asistencias_estudiante_fk
        FOREIGN KEY (id_estudiante) REFERENCES estudiantes(id) NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'asistencias_curso_fk'
          AND conrelid = 'asistencias'::regclass
    ) THEN
        ALTER TABLE asistencias
        ADD CONSTRAINT asistencias_curso_fk
        FOREIGN KEY (id_curso) REFERENCES cursos(id) NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'asistencias_matricula_fk'
          AND conrelid = 'asistencias'::regclass
    ) THEN
        ALTER TABLE asistencias
        ADD CONSTRAINT asistencias_matricula_fk
        FOREIGN KEY (id_estudiante, id_curso)
        REFERENCES matriculas(id_estudiante, id_curso) NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'asistencias_estado_valido'
          AND conrelid = 'asistencias'::regclass
    ) THEN
        ALTER TABLE asistencias
        ADD CONSTRAINT asistencias_estado_valido
        CHECK (estado IN ('presente', 'tarde', 'ausente')) NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'asistencias_estudiante_curso_fecha_unicos'
          AND conrelid = 'asistencias'::regclass
    ) THEN
        ALTER TABLE asistencias
        ADD CONSTRAINT asistencias_estudiante_curso_fecha_unicos
        UNIQUE (id_estudiante, id_curso, fecha);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM asistencias a
        LEFT JOIN estudiantes e ON e.id = a.id_estudiante
        WHERE e.id IS NULL
    ) THEN
        ALTER TABLE asistencias VALIDATE CONSTRAINT asistencias_estudiante_fk;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM asistencias a
        LEFT JOIN cursos c ON c.id = a.id_curso
        WHERE c.id IS NULL
    ) THEN
        ALTER TABLE asistencias VALIDATE CONSTRAINT asistencias_curso_fk;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM asistencias a
        LEFT JOIN matriculas m
            ON m.id_estudiante = a.id_estudiante
           AND m.id_curso = a.id_curso
        WHERE m.id_estudiante IS NULL
    ) THEN
        ALTER TABLE asistencias VALIDATE CONSTRAINT asistencias_matricula_fk;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM asistencias
        WHERE estado NOT IN ('presente', 'tarde', 'ausente')
    ) THEN
        ALTER TABLE asistencias VALIDATE CONSTRAINT asistencias_estado_valido;
    END IF;
END
$$;
