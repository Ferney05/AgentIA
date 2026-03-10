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
    db_url = os.environ.get("DATABASE_URL")
    print(f"DEBUG: [DB] Iniciando creación de tablas. PG={bool(db_url)}")
    
    conn = _get_connection()
    if db_url:
        conn.autocommit = True
    cursor = conn.cursor()

    # 1. Crear tabla usuarios
    cursor.execute("""
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
            agente_activo INTEGER DEFAULT 0,
            contexto_negocio TEXT,
            filtro_fecha_especifica INTEGER DEFAULT 0,
            fecha_filtro TEXT
        )
    """)
    
    # Migración: Agregar columnas de filtro por fecha si no existen
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN filtro_fecha_especifica INTEGER DEFAULT 0")
    except Exception:
        pass  # Ya existe o error ignorado
    
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN fecha_filtro TEXT")
    except Exception:
        pass  # Ya existe o error ignorado

    print("DEBUG: [DB] Tabla usuarios verificada/creada.")

    # 2. Crear tabla reglas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reglas (
            id SERIAL PRIMARY KEY,
            clave TEXT NOT NULL,
            instruccion TEXT NOT NULL,
            usuario_id INTEGER,
            prioridad INTEGER DEFAULT 3,
            tipo TEXT DEFAULT 'negocio',
            etiquetas TEXT DEFAULT '',
            es_principal INTEGER DEFAULT 0,
            auto_enviar INTEGER DEFAULT 0
        )
    """)
    
    # Migración: Agregar columna auto_enviar a reglas si no existe
    try:
        cursor.execute("ALTER TABLE reglas ADD COLUMN auto_enviar INTEGER DEFAULT 0")
    except Exception:
        pass

    print("DEBUG: [DB] Tabla reglas verificada/creada.")

    # 3. Crear tabla logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            fecha TEXT NOT NULL,
            remitente TEXT,
            asunto TEXT,
            resumen TEXT,
            accion TEXT,
            idioma TEXT,
            categoria TEXT DEFAULT 'GENERAL',
            usuario_id INTEGER
        )
    """)
    print("DEBUG: [DB] Tabla logs verificada/creada.")

    # 4. Crear tabla respuestas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respuestas (
            id SERIAL PRIMARY KEY,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            usuario_id INTEGER
        )
    """)
    print("DEBUG: [DB] Tabla respuestas verificada/creada.")

    # 5. Crear tabla remitentes_conocidos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remitentes_conocidos (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            nombre TEXT,
            primera_vez TEXT NOT NULL,
            ultima_vez TEXT,
            total_correos INTEGER DEFAULT 1,
            estado TEXT DEFAULT 'nuevo',
            usuario_id INTEGER,
            UNIQUE(email, usuario_id)
        )
    """)
    print("DEBUG: [DB] Tabla remitentes_conocidos verificada/creada.")

    # 6. Crear tabla remitentes_bloqueados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remitentes_bloqueados (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            nombre TEXT,
            tipo TEXT DEFAULT 'bloqueado',
            razon TEXT,
            fecha_bloqueo TEXT NOT NULL,
            usuario_id INTEGER,
            UNIQUE(email, usuario_id)
        )
    """)
    print("DEBUG: [DB] Tabla remitentes_bloqueados verificada/creada.")

    # 7. Crear tabla suscripciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suscripciones (
            id SERIAL PRIMARY KEY,
            remitente_email TEXT NOT NULL,
            remitente_nombre TEXT,
            link_cancelacion TEXT,
            total_correos INTEGER DEFAULT 1,
            ultimo_correo TEXT,
            estado TEXT DEFAULT 'activa',
            usuario_id INTEGER,
            UNIQUE(remitente_email, usuario_id)
        )
    """)
    print("DEBUG: [DB] Tabla suscripciones verificada/creada.")

    # 8. Crear tabla reglas_organizacion
    # Solo crear si no existe para evitar borrar datos al reiniciar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reglas_organizacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            condicion_campo TEXT,
            condicion_valor TEXT,
            accion TEXT NOT NULL,
            activa INTEGER DEFAULT 1,
            usuario_id INTEGER
        )
    """)
    print("DEBUG: [DB] Tabla reglas_organizacion verificada/creada.")

    # 9. Crear tabla logs_limpieza
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_limpieza (
            id SERIAL PRIMARY KEY,
            categoria_id INTEGER,
            usuario_id INTEGER NOT NULL,
            correos_procesados INTEGER DEFAULT 0,
            fecha_ejecucion TEXT NOT NULL
        )
    """)
    print("DEBUG: [DB] Tabla logs_limpieza verificada/creada.")

    # 10. Crear tabla categorias_limpieza
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias_limpieza (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            remitentes TEXT,
            fecha_creacion TEXT NOT NULL,
            activa INTEGER DEFAULT 1
        )
    """)
    print("DEBUG: [DB] Tabla categorias_limpieza verificada/creada.")

    conn.close()
    print("DEBUG: [DB] Proceso de inicialización finalizado.")

def insertar_regla(
    clave: str,
    instruccion: str,
    usuario_id: int | None = None,
    prioridad: int = 3,
    tipo: str = "negocio",
    etiquetas: str = "",
    es_principal: int = 0,
    auto_enviar: int = 0,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"INSERT INTO reglas (clave, instruccion, usuario_id, prioridad, tipo, etiquetas, es_principal, auto_enviar) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})",
        (clave, instruccion, usuario_id, prioridad, tipo, etiquetas, es_principal, auto_enviar),
    )
    conn.commit()
    conn.close()


def obtener_firma_usuario(usuario_id: int) -> str | None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT instruccion FROM reglas WHERE usuario_id = {p} AND tipo = 'firma' LIMIT 1",
        (usuario_id,),
    )
    fila = cursor.fetchone()
    conn.close()
    return fila[0] if fila else None

def existe_prioridad(usuario_id: int, prioridad: int, exclude_id: int | None = None) -> bool:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    if exclude_id is not None:
        cursor.execute(
            f"SELECT 1 FROM reglas WHERE usuario_id = {p} AND prioridad = {p} AND id != {p} LIMIT 1",
            (usuario_id, prioridad, exclude_id),
        )
    else:
        cursor.execute(
            f"SELECT 1 FROM reglas WHERE usuario_id = {p} AND prioridad = {p} LIMIT 1",
            (usuario_id, prioridad),
        )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def obtener_siguiente_prioridad(usuario_id: int) -> int:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT MAX(prioridad) FROM reglas WHERE usuario_id = {p}",
        (usuario_id,),
    )
    fila = cursor.fetchone()
    conn.close()
    if fila and fila[0] is not None:
        return int(fila[0]) + 1
    return 1

def obtener_reglas(usuario_id: int | None = None, nombre_bd: str = "kyber.db") -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    if usuario_id is None:
        cursor.execute("SELECT id, clave, instruccion, COALESCE(prioridad, 3), COALESCE(tipo, 'negocio'), COALESCE(etiquetas, ''), COALESCE(es_principal, 0), COALESCE(auto_enviar, 0) FROM reglas ORDER BY COALESCE(prioridad, 3) DESC, id DESC")
    else:
        cursor.execute(
            f"SELECT id, clave, instruccion, COALESCE(prioridad, 3), COALESCE(tipo, 'negocio'), COALESCE(etiquetas, ''), COALESCE(es_principal, 0), COALESCE(auto_enviar, 0) FROM reglas WHERE usuario_id = {p} OR usuario_id IS NULL ORDER BY COALESCE(prioridad, 3) DESC, id DESC",
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
        f"SELECT id, clave, instruccion, COALESCE(prioridad, 3), COALESCE(tipo, 'negocio'), COALESCE(etiquetas, ''), COALESCE(es_principal, 0), COALESCE(auto_enviar, 0) FROM reglas WHERE id = {p}",
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
    auto_enviar: int = 0,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"UPDATE reglas SET clave = {p}, instruccion = {p}, prioridad = {p}, tipo = {p}, etiquetas = {p}, es_principal = {p}, auto_enviar = {p} WHERE id = {p}",
        (clave, instruccion, prioridad, tipo, etiquetas, es_principal, auto_enviar, regla_id),
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
    print(f"DEBUG: [DB] Creando usuario: {email}")
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
        print(f"DEBUG: [DB] Insertando usuario en SQLite")
        cursor.execute(
            f"INSERT INTO usuarios (email, password_hash, creado_en) VALUES ({p}, {p}, {p})",
            (email, password_hash, creado_en),
        )
        user_id = cursor.lastrowid
        print(f"DEBUG: [DB] lastrowid: {user_id}")
        
    conn.commit()
    print(f"DEBUG: [DB] Usuario creado con ID: {user_id}")
    conn.close()
    return user_id


def obtener_usuario_por_email(
    email: str, nombre_bd: str = "kyber.db"
) -> Tuple[Any, ...] | None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    cursor.execute(
        f"SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo, contexto_negocio, filtro_fecha_especifica, fecha_filtro FROM usuarios WHERE email = {p}",
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
        f"SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo, contexto_negocio, filtro_fecha_especifica, fecha_filtro FROM usuarios WHERE id = {p}",
        (usuario_id,),
    )
    fila = cursor.fetchone()
    conn.close()
    return fila


def obtener_usuarios_agente_activo(nombre_bd: str = "kyber.db") -> List[Tuple[Any, ...]]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, password_hash, creado_en, gemini_api_key, gmail_user, gmail_password, scan_batch, scan_max, agente_activo, contexto_negocio, filtro_fecha_especifica, fecha_filtro FROM usuarios WHERE agente_activo = 1"
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
    contexto_negocio: str | None = None,
    filtro_fecha_especifica: int | None = None,
    fecha_filtro: str | None = None,
    nombre_bd: str = "kyber.db",
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    updates = []
    params = []
    
    if scan_batch is not None:
        updates.append(f"scan_batch = {p}")
        params.append(scan_batch)
    if scan_max is not None:
        updates.append(f"scan_max = {p}")
        params.append(scan_max)
    if agente_activo is not None:
        updates.append(f"agente_activo = {p}")
        params.append(agente_activo)
    if contexto_negocio is not None:
        updates.append(f"contexto_negocio = {p}")
        params.append(contexto_negocio)
    if filtro_fecha_especifica is not None:
        updates.append(f"filtro_fecha_especifica = {p}")
        params.append(filtro_fecha_especifica)
    if fecha_filtro is not None:
        updates.append(f"fecha_filtro = {p}")
        params.append(fecha_filtro)
        
    if not updates:
        print("DEBUG: [DB] No hay actualizaciones")
        conn.close()
        return
        
    query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = {p}"
    params.append(usuario_id)
    
    print(f"DEBUG: [DB] Query: {query}")
    print(f"DEBUG: [DB] Params: {tuple(params)}")
    
    cursor.execute(query, tuple(params))
    conn.commit()
    print("DEBUG: [DB] Configuración actualizada exitosamente")
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

def obtener_categorias_unicas(usuario_id: int | None = None) -> List[str]:
    """Obtiene todas las categorías únicas que existen en los logs."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    if usuario_id is None:
        cursor.execute(
            """
            SELECT DISTINCT COALESCE(categoria, 'GENERAL') AS cat
            FROM logs
            WHERE categoria IS NOT NULL AND categoria != ''
            ORDER BY cat ASC
            """
        )
    else:
        cursor.execute(
            f"""
            SELECT DISTINCT COALESCE(categoria, 'GENERAL') AS cat
            FROM logs
            WHERE (usuario_id = {p} OR usuario_id IS NULL)
              AND categoria IS NOT NULL AND categoria != ''
            ORDER BY cat ASC
            """,
            (usuario_id,),
        )
    filas = cursor.fetchall()
    conn.close()
    return [fila[0] for fila in filas]


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


# ============================================
# FUNCIONES PARA REMITENTES CONOCIDOS
# ============================================

def registrar_remitente(email: str, nombre: str, usuario_id: int) -> None:
    """Registra o actualiza un remitente conocido."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    ahora = datetime.utcnow().isoformat()
    
    # Intentar actualizar si existe
    cursor.execute(
        f"""
        UPDATE remitentes_conocidos 
        SET ultima_vez = {p}, total_correos = total_correos + 1, nombre = {p}
        WHERE email = {p} AND usuario_id = {p}
        """,
        (ahora, nombre, email, usuario_id)
    )
    
    # Si no existe, insertar
    if cursor.rowcount == 0:
        cursor.execute(
            f"""
            INSERT INTO remitentes_conocidos (email, nombre, primera_vez, ultima_vez, usuario_id)
            VALUES ({p}, {p}, {p}, {p}, {p})
            """,
            (email, nombre, ahora, ahora, usuario_id)
        )
    
    conn.commit()
    conn.close()


def es_remitente_nuevo(email: str, usuario_id: int) -> bool:
    """Verifica si un remitente es nuevo (primera vez que escribe)."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"SELECT estado FROM remitentes_conocidos WHERE email = {p} AND usuario_id = {p}",
        (email, usuario_id)
    )
    fila = cursor.fetchone()
    conn.close()
    
    if not fila:
        return True  # No existe, es nuevo
    
    return fila[0] == 'nuevo'


def obtener_remitentes_nuevos(usuario_id: int) -> List[Tuple[Any, ...]]:
    """Obtiene todos los remitentes nuevos pendientes de revisar."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"""
        SELECT id, email, nombre, primera_vez, total_correos
        FROM remitentes_conocidos
        WHERE usuario_id = {p} AND estado = 'nuevo'
        ORDER BY primera_vez DESC
        """,
        (usuario_id,)
    )
    filas = cursor.fetchall()
    conn.close()
    return filas
def obtener_todos_remitentes(usuario_id: int, limite: int = 100) -> List[Tuple[Any, ...]]:
    """Obtiene TODOS los remitentes conocidos con su estado."""
    conn = _get_connection()
    cursor = conn.cursor()
    p1, p2, p3 = _get_placeholder(), _get_placeholder(), _get_placeholder()

    cursor.execute(
        f"""
        SELECT
            rc.id,
            rc.email,
            rc.nombre,
            rc.primera_vez,
            rc.ultima_vez,
            rc.total_correos,
            rc.estado,
            CASE
                WHEN rb.id IS NOT NULL THEN rb.tipo
                ELSE NULL
            END as bloqueado_tipo,
            SUBSTR(rc.email, INSTR(rc.email, '@') + 1) as dominio
        FROM remitentes_conocidos rc
        LEFT JOIN remitentes_bloqueados rb ON rc.email = rb.email AND rb.usuario_id = {p2}
        WHERE rc.usuario_id = {p1}
        ORDER BY rc.ultima_vez DESC
        LIMIT {p3}
        """,
        (usuario_id, usuario_id, limite)
    )
    filas = cursor.fetchall()
    conn.close()
    return filas



def aprobar_remitente(remitente_id: int) -> None:
    """Marca un remitente como aprobado."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"UPDATE remitentes_conocidos SET estado = 'aprobado' WHERE id = {p}",
        (remitente_id,)
    )
    conn.commit()
    conn.close()


def bloquear_remitente_desde_nuevos(remitente_id: int, usuario_id: int, razon: str = "Bloqueado desde nuevos") -> None:
    """Bloquea un remitente desde la lista de nuevos."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    # Obtener email del remitente
    cursor.execute(
        f"SELECT email, nombre FROM remitentes_conocidos WHERE id = {p}",
        (remitente_id,)
    )
    fila = cursor.fetchone()
    
    if fila:
        email, nombre = fila
        ahora = datetime.utcnow().isoformat()
        
        # Agregar a bloqueados
        cursor.execute(
            f"""
            INSERT INTO remitentes_bloqueados (email, nombre, tipo, razon, fecha_bloqueo, usuario_id)
            VALUES ({p}, {p}, 'bloqueado', {p}, {p}, {p})
            ON CONFLICT (email, usuario_id) DO NOTHING
            """,
            (email, nombre, razon, ahora, usuario_id)
        )
        
        # Actualizar estado en conocidos
        cursor.execute(
            f"UPDATE remitentes_conocidos SET estado = 'bloqueado' WHERE id = {p}",
            (remitente_id,)
        )
    
    conn.commit()
    conn.close()


# ============================================
# FUNCIONES PARA REMITENTES BLOQUEADOS
# ============================================

def agregar_remitente_bloqueado(email: str, nombre: str, tipo: str, razon: str, usuario_id: int) -> None:
    """Agrega un remitente a la lista de bloqueados o silenciados."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    ahora = datetime.utcnow().isoformat()
    
    cursor.execute(
        f"""
        INSERT INTO remitentes_bloqueados (email, nombre, tipo, razon, fecha_bloqueo, usuario_id)
        VALUES ({p}, {p}, {p}, {p}, {p}, {p})
        ON CONFLICT (email, usuario_id) DO UPDATE SET tipo = {p}, razon = {p}
        """,
        (email, nombre, tipo, razon, ahora, usuario_id, tipo, razon)
    )
    conn.commit()
    conn.close()


def obtener_remitentes_bloqueados(usuario_id: int) -> List[Tuple[Any, ...]]:
    """Obtiene todos los remitentes bloqueados."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"""
        SELECT id, email, nombre, tipo, razon, fecha_bloqueo
        FROM remitentes_bloqueados
        WHERE usuario_id = {p}
        ORDER BY fecha_bloqueo DESC
        """,
        (usuario_id,)
    )
    filas = cursor.fetchall()
    conn.close()
    return filas


def esta_bloqueado(email: str, usuario_id: int) -> bool:
    """Verifica si un remitente está bloqueado."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"SELECT tipo FROM remitentes_bloqueados WHERE email = {p} AND usuario_id = {p}",
        (email, usuario_id)
    )
    fila = cursor.fetchone()
    conn.close()
    
    return fila is not None and fila[0] == 'bloqueado'


def esta_silenciado(email: str, usuario_id: int) -> bool:
    """Verifica si un remitente está silenciado."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"SELECT tipo FROM remitentes_bloqueados WHERE email = {p} AND usuario_id = {p}",
        (email, usuario_id)
    )
    fila = cursor.fetchone()
    conn.close()
    
    return fila is not None and fila[0] == 'silenciado'


def desbloquear_remitente(remitente_id: int) -> None:
    """Elimina un remitente de la lista de bloqueados."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"DELETE FROM remitentes_bloqueados WHERE id = {p}",
        (remitente_id,)
    )
    conn.commit()
    conn.close()


def desbloquear_remitente_por_email(email: str, usuario_id: int) -> None:
    """Elimina un remitente de la lista de bloqueados por su email."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"DELETE FROM remitentes_bloqueados WHERE email = {p} AND usuario_id = {p}",
        (email, usuario_id)
    )
    conn.commit()
    conn.close()


# ============================================
# FUNCIONES PARA SUSCRIPCIONES
# ============================================

def registrar_suscripcion(email: str, nombre: str, link: str, usuario_id: int) -> None:
    """Registra o actualiza una suscripción detectada."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    ahora = datetime.utcnow().isoformat()
    
    cursor.execute(
        f"""
        INSERT INTO suscripciones (remitente_email, remitente_nombre, link_cancelacion, ultimo_correo, usuario_id)
        VALUES ({p}, {p}, {p}, {p}, {p})
        ON CONFLICT (remitente_email, usuario_id) DO UPDATE 
        SET total_correos = suscripciones.total_correos + 1, 
            ultimo_correo = {p},
            link_cancelacion = {p}
        """,
        (email, nombre, link, ahora, usuario_id, ahora, link)
    )
    conn.commit()
    conn.close()


def obtener_suscripciones(usuario_id: int) -> List[Tuple[Any, ...]]:
    """Obtiene todas las suscripciones activas y canceladas."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"""
        SELECT 
            id, 
            remitente_email, 
            remitente_nombre, 
            link_cancelacion, 
            total_correos, 
            ultimo_correo, 
            estado,
            SUBSTR(remitente_email, INSTR(remitente_email, '@') + 1) as dominio
        FROM suscripciones
        WHERE usuario_id = {p}
        ORDER BY total_correos DESC, ultimo_correo DESC
        """,
        (usuario_id,)
    )
    filas = cursor.fetchall()
    conn.close()
    return filas


def marcar_suscripcion_cancelada(suscripcion_id: int) -> None:
    """Marca una suscripción como cancelada."""
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"UPDATE suscripciones SET estado = 'cancelada' WHERE id = {p}",
        (suscripcion_id,)
    )
    conn.commit()
    conn.close()


# ============================================
# FUNCIONES PARA REGLAS DE ORGANIZACIÓN
# ============================================

def crear_regla_organizacion(nombre: str, tipo: str, condicion_campo: str, condicion_valor: str, accion: str, usuario_id: int) -> None:
    """Crea una nueva regla de organización automática."""
    print(f"DEBUG: [DB] Creando regla: {nombre} para usuario_id={usuario_id}")
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"""
        INSERT INTO reglas_organizacion (nombre, tipo, condicion_campo, condicion_valor, accion, activa, usuario_id)
        VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """,
        (nombre, tipo, condicion_campo, condicion_valor, accion, 1, usuario_id)
    )
    conn.commit()
    print(f"DEBUG: [DB] Regla creada exitosamente")
    
    # Verificar que se insertó correctamente
    cursor.execute(f"SELECT COUNT(*) FROM reglas_organizacion WHERE usuario_id = {p}", (usuario_id,))
    count = cursor.fetchone()[0]
    print(f"DEBUG: [DB] Verificación: Total de reglas después de insertar: {count}")
    
    conn.close()


def obtener_reglas_organizacion(usuario_id: int) -> List[Tuple[Any, ...]]:
    """Obtiene todas las reglas de organización activas."""
    print(f"DEBUG: [DB] Obteniendo reglas para usuario_id={usuario_id}")
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    # Primero verificar si hay datos en la tabla
    cursor.execute(f"SELECT COUNT(*) FROM reglas_organizacion WHERE usuario_id = {p}", (usuario_id,))
    count = cursor.fetchone()[0]
    print(f"DEBUG: [DB] Total de reglas en BD: {count}")
    
    if count == 0:
        print("DEBUG: [DB] No hay reglas, retornando lista vacía")
        conn.close()
        return []
    
    cursor.execute(
        f"""
        SELECT id, nombre, tipo, condicion_campo, condicion_valor, accion, activa
        FROM reglas_organizacion
        WHERE usuario_id = {p}
        ORDER BY id DESC
        """,
        (usuario_id,)
    )
    filas = cursor.fetchall()
    print(f"DEBUG: [DB] Se encontraron {len(filas)} reglas")
    for i, fila in enumerate(filas):
        print(f"DEBUG: [DB] Regla {i}: {fila}")
    conn.close()
    return filas


def toggle_regla_organizacion(regla_id: int) -> None:
    """Activa o desactiva una regla de organización."""
    print(f"DEBUG: [DB] Toggle regla {regla_id}")
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"UPDATE reglas_organizacion SET activa = 1 - activa WHERE id = {p}",
        (regla_id,)
    )
    conn.commit()
    print(f"DEBUG: [DB] Regla {regla_id} toggleada")
    conn.close()


def eliminar_regla_organizacion(regla_id: int) -> None:
    """Elimina una regla de organización."""
    print(f"DEBUG: [DB] Eliminando regla {regla_id}")
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(f"DELETE FROM reglas_organizacion WHERE id = {p}", (regla_id,))
    conn.commit()
    print(f"DEBUG: [DB] Regla {regla_id} eliminada")
    conn.close()
