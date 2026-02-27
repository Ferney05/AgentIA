import sqlite3
import os
import psycopg2
from typing import Any, Dict, List, Tuple
from datetime import datetime

def _get_connection():
    """Obtiene una conexión a la base de datos (PostgreSQL o SQLite)."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Usar PostgreSQL en la nube
        return psycopg2.connect(db_url)
    else:
        # Usar SQLite en local
        return sqlite3.connect("kyber.db")

def _get_placeholder():
    """Retorna el placeholder adecuado para el motor de BD activo."""
    return "%s" if os.environ.get("DATABASE_URL") else "?"

def crear_base_de_datos(nombre_bd: str = "kyber.db") -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()

def crear_base_de_datos(nombre_bd: str = "kyber.db") -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()

    is_pg = os.environ.get("DATABASE_URL")

    if is_pg:
        # PostgreSQL specific table creation
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TEXT NOT NULL,
                gemini_api_key TEXT,
                gmail_user TEXT,
                gmail_password TEXT,
                scan_batch INTEGER DEFAULT 10,
                scan_max INTEGER DEFAULT 100,
                agente_activo INTEGER DEFAULT 0
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reglas (
                id SERIAL PRIMARY KEY,
                clave TEXT NOT NULL,
                instruccion TEXT NOT NULL,
                usuario_id INTEGER,
                prioridad INTEGER,
                tipo TEXT,
                etiquetas TEXT,
                es_principal INTEGER
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                remitente TEXT,
                asunto TEXT,
                resumen TEXT,
                accion TEXT,
                idioma TEXT,
                categoria TEXT,
                usuario_id INTEGER
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS respuestas (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                contenido TEXT NOT NULL,
                usuario_id INTEGER
            );
            """
        )
    else:
        # SQLite specific table creation
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TEXT NOT NULL,
                gemini_api_key TEXT,
                gmail_user TEXT,
                gmail_password TEXT,
                scan_batch INTEGER DEFAULT 10,
                scan_max INTEGER DEFAULT 100,
                agente_activo INTEGER DEFAULT 0
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reglas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT NOT NULL,
                instruccion TEXT NOT NULL,
                usuario_id INTEGER,
                prioridad INTEGER,
                tipo TEXT,
                etiquetas TEXT,
                es_principal INTEGER
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                remitente TEXT,
                asunto TEXT,
                resumen TEXT,
                accion TEXT,
                idioma TEXT,
                categoria TEXT,
                usuario_id INTEGER
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS respuestas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                contenido TEXT NOT NULL,
                usuario_id INTEGER
            );
            """
        )

    # Migraciones/Actualizaciones de columnas
    tablas_columnas = {
        "usuarios": [
            ("gemini_api_key", "TEXT"),
            ("gmail_user", "TEXT"),
            ("gmail_password", "TEXT"),
            ("scan_batch", "INTEGER DEFAULT 10"),
            ("scan_max", "INTEGER DEFAULT 100"),
            ("agente_activo", "INTEGER DEFAULT 0")
        ],
        "reglas": [
            ("usuario_id", "INTEGER"),
            ("prioridad", "INTEGER"),
            ("tipo", "TEXT"),
            ("etiquetas", "TEXT"),
            ("es_principal", "INTEGER")
        ],
        "logs": [
            ("categoria", "TEXT"),
            ("usuario_id", "INTEGER")
        ],
        "respuestas": [
            ("usuario_id", "INTEGER")
        ]
    }

    for tabla, columnas in tablas_columnas.items():
        for col_nombre, col_tipo in columnas:
            try:
                cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {col_nombre} {col_tipo}")
            except Exception:
                pass

    conn.commit()
    conn.close()

def insertar_regla(
    clave: str,
    instruccion: str,
    usuario_id: int | None = None,
    prioridad: int = 3,
    tipo: str = "negocio",
    etiquetas: str = "",
    es_principal: int = 0,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"INSERT INTO reglas (clave, instruccion, usuario_id, prioridad, tipo, etiquetas, es_principal) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})",
        (clave, instruccion, usuario_id, prioridad, tipo, etiquetas, es_principal),
    )
    conn.commit()
    conn.close()


def obtener_reglas(usuario_id: int | None = None, nombre_bd: str = "kyber.db") -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    if usuario_id is None:
        cursor.execute("SELECT id, clave, instruccion, COALESCE(prioridad, 3), COALESCE(tipo, 'negocio'), COALESCE(etiquetas, ''), COALESCE(es_principal, 0) FROM reglas ORDER BY COALESCE(prioridad, 3) DESC, id DESC")
    else:
        cursor.execute(
            f"SELECT id, clave, instruccion, COALESCE(prioridad, 3), COALESCE(tipo, 'negocio'), COALESCE(etiquetas, ''), COALESCE(es_principal, 0) FROM reglas WHERE usuario_id = {p} OR usuario_id IS NULL ORDER BY COALESCE(prioridad, 3) DESC, id DESC",
            (usuario_id,),
        )
    filas = cursor.fetchall()
    conn.close()
    return filas


def obtener_regla_por_id(regla_id: int, nombre_bd: str = "kyber.db") -> Tuple[Any, ...] | None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT id, clave, instruccion, COALESCE(prioridad, 3), COALESCE(tipo, 'negocio'), COALESCE(etiquetas, ''), COALESCE(es_principal, 0) FROM reglas WHERE id = {p}",
        (regla_id,),
    )
    fila = cursor.fetchone()
    conn.close()
    return fila


def actualizar_regla(
    regla_id: int,
    clave: str,
    instruccion: str,
    prioridad: int = 3,
    tipo: str = "negocio",
    etiquetas: str = "",
    es_principal: int = 0,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"UPDATE reglas SET clave = {p}, instruccion = {p}, prioridad = {p}, tipo = {p}, etiquetas = {p}, es_principal = {p} WHERE id = {p}",
        (clave, instruccion, prioridad, tipo, etiquetas, es_principal, regla_id),
    )
    conn.commit()
    conn.close()


def eliminar_regla(regla_id: int, nombre_bd: str = "kyber.db") -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(f"DELETE FROM reglas WHERE id = {p}", (regla_id,))
    conn.commit()
    conn.close()

def insertar_respuesta(
    titulo: str, contenido: str, usuario_id: int | None = None, nombre_bd: str = "kyber.db"
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"INSERT INTO respuestas (titulo, contenido, usuario_id) VALUES ({p}, {p}, {p})",
        (titulo, contenido, usuario_id),
    )
    conn.commit()
    conn.close()

def obtener_respuestas(usuario_id: int | None = None, nombre_bd: str = "kyber.db") -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    if usuario_id is None:
        cursor.execute("SELECT id, titulo, contenido FROM respuestas ORDER BY id DESC")
    else:
        cursor.execute(
            f"SELECT id, titulo, contenido FROM respuestas WHERE usuario_id = {p} OR usuario_id IS NULL ORDER BY id DESC",
            (usuario_id,),
        )
    filas = cursor.fetchall()
    conn.close()
    return filas

def obtener_respuesta_por_id(respuesta_id: int, nombre_bd: str = "kyber.db") -> Tuple[Any, ...] | None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT id, titulo, contenido FROM respuestas WHERE id = {p}", (respuesta_id,)
    )
    fila = cursor.fetchone()
    conn.close()
    return fila

def actualizar_respuesta(respuesta_id: int, titulo: str, contenido: str, nombre_bd: str = "kyber.db") -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"UPDATE respuestas SET titulo = {p}, contenido = {p} WHERE id = {p}",
        (titulo, contenido, respuesta_id),
    )
    conn.commit()
    conn.close()

def eliminar_respuesta(respuesta_id: int, nombre_bd: str = "kyber.db") -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(f"DELETE FROM respuestas WHERE id = {p}", (respuesta_id,))
    conn.commit()
    conn.close()

def insertar_log(
    fecha: str,
    remitente: str,
    asunto: str,
    resumen: str,
    accion: str,
    idioma: str,
    categoria: str,
    usuario_id: int | None = None,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"""
        INSERT INTO logs (fecha, remitente, asunto, resumen, accion, idioma, categoria, usuario_id)
        VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """,
        (fecha, remitente, asunto, resumen, accion, idioma, categoria, usuario_id),
    )
    conn.commit()
    conn.close()


def crear_usuario(
    email: str, password_hash: str, creado_en: str
) -> int:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    if os.environ.get("DATABASE_URL"):
        # PostgreSQL: usamos RETURNING para obtener el ID de forma segura
        cursor.execute(
            f"INSERT INTO usuarios (email, password_hash, creado_en) VALUES ({p}, {p}, {p}) RETURNING id",
            (email, password_hash, creado_en),
        )
        user_id = cursor.fetchone()[0]
    else:
        # SQLite
        cursor.execute(
            f"INSERT INTO usuarios (email, password_hash, creado_en) VALUES ({p}, {p}, {p})",
            (email, password_hash, creado_en),
        )
        user_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return user_id


def obtener_usuario_por_email(
    email: str, nombre_bd: str = "kyber.db"
) -> Tuple[Any, ...] | None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo FROM usuarios WHERE email = {p}",
        (email,),
    )
    fila = cursor.fetchone()
    conn.close()
    return fila


def obtener_usuario_por_id(
    usuario_id: int, nombre_bd: str = "kyber.db"
) -> Tuple[Any, ...] | None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo FROM usuarios WHERE id = {p}",
        (usuario_id,),
    )
    fila = cursor.fetchone()
    conn.close()
    return fila


def obtener_usuarios_agente_activo(nombre_bd: str = "kyber.db") -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo FROM usuarios WHERE agente_activo = 1"
    )
    filas = cursor.fetchall()
    conn.close()
    return filas


def actualizar_configuracion_usuario(
    usuario_id: int,
    gemini_api_key: str | None = None,
    gmail_user: str | None = None,
    gmail_password: str | None = None,
    scan_batch: int | None = None,
    scan_max: int | None = None,
    agente_activo: int | None = None,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    updates = []
    params = []
    
    if gemini_api_key is not None:
        updates.append(f"gemini_api_key = {p}")
        params.append(gemini_api_key)
    if gmail_user is not None:
        updates.append(f"gmail_user = {p}")
        params.append(gmail_user)
    if gmail_password is not None:
        updates.append(f"gmail_password = {p}")
        params.append(gmail_password)
    if scan_batch is not None:
        updates.append(f"scan_batch = {p}")
        params.append(scan_batch)
    if scan_max is not None:
        updates.append(f"scan_max = {p}")
        params.append(scan_max)
    if agente_activo is not None:
        updates.append(f"agente_activo = {p}")
        params.append(agente_activo)
        
    if not updates:
        conn.close()
        return
        
    query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = {p}"
    params.append(usuario_id)
    
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()


def obtener_usuarios_agente_activo(nombre_bd: str = "kyber.db") -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo FROM usuarios WHERE agente_activo = 1"
    )
    filas = cursor.fetchall()
    conn.close()
    return filas


def actualizar_configuracion_usuario(
    usuario_id: int,
    gemini_api_key: str | None = None,
    gmail_user: str | None = None,
    gmail_password: str | None = None,
    scan_batch: int | None = None,
    scan_max: int | None = None,
    agente_activo: int | None = None,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    updates = []
    params = []
    
    if gemini_api_key is not None:
        updates.append(f"gemini_api_key = {p}")
        params.append(gemini_api_key)
    if gmail_user is not None:
        updates.append(f"gmail_user = {p}")
        params.append(gmail_user)
    if gmail_password is not None:
        updates.append(f"gmail_password = {p}")
        params.append(gmail_password)
    if scan_batch is not None:
        updates.append(f"scan_batch = {p}")
        params.append(scan_batch)
    if scan_max is not None:
        updates.append(f"scan_max = {p}")
        params.append(scan_max)
    if agente_activo is not None:
        updates.append(f"agente_activo = {p}")
        params.append(agente_activo)
        
    if not updates:
        conn.close()
        return
        
    query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = {p}"
    params.append(usuario_id)
    
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()


def obtener_resumen_logs(usuario_id: int | None = None, nombre_bd: str = "kyber.db") -> Dict[str, int]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()

    hoy = datetime.utcnow().strftime("%Y-%m-%d")
    if usuario_id is None:
        cursor.execute(
            f"SELECT COUNT(*) FROM logs WHERE accion = {p}", ("NADA",)
        )
    else:
        cursor.execute(
            f"SELECT COUNT(*) FROM logs WHERE accion = {p} AND (usuario_id = {p} OR usuario_id IS NULL)",
            ("NADA", usuario_id),
        )
    sin_accion = cursor.fetchone()[0]

    if usuario_id is None:
        cursor.execute(
            f"SELECT COUNT(*) FROM logs WHERE accion = 'BORRADOR' AND fecha LIKE {p}",
            (hoy + "%",),
        )
    else:
        cursor.execute(
            f"SELECT COUNT(*) FROM logs WHERE accion = 'BORRADOR' AND fecha LIKE {p} AND (usuario_id = {p} OR usuario_id IS NULL)",
            (hoy + "%", usuario_id),
        )
    borradores = cursor.fetchone()[0]

    conn.close()
    return {
        "sin_accion": sin_accion,
        "borradores": borradores,
    }


def obtener_ultimos_logs(
    limite: int = 10, usuario_id: int | None = None, nombre_bd: str = "kyber.db"
) -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    if usuario_id is None:
        cursor.execute(
            f"""
            SELECT fecha, remitente, asunto, resumen, accion, idioma, categoria
            FROM logs
            ORDER BY id DESC
            LIMIT {p}
            """,
            (limite,),
        )
    else:
        cursor.execute(
            f"""
            SELECT fecha, remitente, asunto, resumen, accion, idioma, categoria
            FROM logs
            WHERE usuario_id = {p} OR usuario_id IS NULL
            ORDER BY id DESC
            LIMIT {p}
            """,
            (usuario_id, limite),
        )
    filas = cursor.fetchall()
    conn.close()
    return filas


def obtener_logs_filtrados_paginados(
    limite: int = 20,
    offset: int = 0,
    usuario_id: int | None = None,
    categoria: str | None = None,
    accion: str | None = None,
    nombre_bd: str = "kyber.db",
) -> Tuple[List[Tuple[Any, ...]], int]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    where_clauses = []
    params: list[Any] = []

    if usuario_id is not None:
        where_clauses.append(f"(usuario_id = {p} OR usuario_id IS NULL)")
        params.append(usuario_id)

    if categoria:
        where_clauses.append(f"COALESCE(categoria, 'GENERAL') = {p}")
        params.append(categoria)

    if accion:
        where_clauses.append(f"accion = {p}")
        params.append(accion)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    cursor.execute(f"SELECT COUNT(*) FROM logs {where_sql}", tuple(params))
    total = cursor.fetchone()[0]

    params_con_limite = list(params)
    params_con_limite.extend([limite, offset])
    cursor.execute(
        f"""
        SELECT fecha, remitente, asunto, resumen, accion, idioma, categoria
        FROM logs
        {where_sql}
        ORDER BY id DESC
        LIMIT {p} OFFSET {p}
        """,
        tuple(params_con_limite),
    )
    filas = cursor.fetchall()
    conn.close()
    return filas, total


def eliminar_logs(
    usuario_id: int | None = None,
    categoria: str | None = None,
    accion: str | None = None,
    nombre_bd: str = "kyber.db",
) -> int:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    where_clauses = []
    params: list[Any] = []

    if usuario_id is not None:
        where_clauses.append(f"(usuario_id = {p} OR usuario_id IS NULL)")
        params.append(usuario_id)

    if categoria:
        where_clauses.append(f"COALESCE(categoria, 'GENERAL') = {p}")
        params.append(categoria)

    if accion:
        where_clauses.append(f"accion = {p}")
        params.append(accion)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    cursor.execute(f"DELETE FROM logs {where_sql}", tuple(params))
    eliminados = cursor.rowcount
    conn.commit()
    conn.close()
    return eliminados


def obtener_stats_categorias(
    usuario_id: int | None = None
) -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    if usuario_id is None:
        cursor.execute(
            """
            SELECT COALESCE(categoria, 'GENERAL') AS categoria, COUNT(*) AS total
            FROM logs
            GROUP BY COALESCE(categoria, 'GENERAL')
            """
        )
    else:
        cursor.execute(
            f"""
            SELECT COALESCE(categoria, 'GENERAL') AS categoria, COUNT(*) AS total
            FROM logs
            WHERE usuario_id = {p} OR usuario_id IS NULL
            GROUP BY COALESCE(categoria, 'GENERAL')
            """,
            (usuario_id,),
        )
    filas = cursor.fetchall()
    conn.close()
    return filas

def obtener_borradores_por_periodo(
    periodo: str = "diario",
    limite: int = 30,
    usuario_id: int | None = None,
    nombre_bd: str = "kyber.db",
) -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    is_pg = os.environ.get("DATABASE_URL")
    
    if is_pg:
        # PostgreSQL
        if periodo == "semanal":
            group_expr = "to_char(fecha::timestamp, 'YYYY-WW')"
        elif periodo == "mensual":
            group_expr = "to_char(fecha::timestamp, 'YYYY-MM')"
        else:
            group_expr = "to_char(fecha::timestamp, 'YYYY-MM-DD')"
    else:
        # SQLite
        if periodo == "semanal":
            group_expr = "strftime('%Y-%W', replace(fecha, 'T', ' '))"
        elif periodo == "mensual":
            group_expr = "strftime('%Y-%m', replace(fecha, 'T', ' '))"
        else:
            group_expr = "strftime('%Y-%m-%d', replace(fecha, 'T', ' '))"

    if usuario_id is None:
        cursor.execute(
            f"""
            SELECT {group_expr} AS per, COUNT(*) AS total
            FROM logs
            WHERE accion = 'BORRADOR'
            GROUP BY per
            ORDER BY per ASC
            LIMIT {p}
            """,
            (limite,),
        )
    else:
        cursor.execute(
            f"""
            SELECT {group_expr} AS per, COUNT(*) AS total
            FROM logs
            WHERE accion = 'BORRADOR' AND (usuario_id = {p} OR usuario_id IS NULL)
            GROUP BY per
            ORDER BY per ASC
            LIMIT {p}
            """,
            (usuario_id, limite),
        )
    filas = cursor.fetchall()
    conn.close()
    return filas


if __name__ == "__main__":
    _FER_DEV_SHEI_200226 = "F-E-R-D-E-V-S-H-E-I-20-02-26"
    crear_base_de_datos()
