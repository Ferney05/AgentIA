"""
Módulo de Limpieza Profesional con IA Avanzada
Analiza correos antiguos y sugiere acciones de limpieza
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import re

from .db import _get_connection, _get_placeholder


def analizar_correos_antiguos(usuario_id: int, meses_minimos: int = 10) -> List[Dict[str, Any]]:
    """
    Analiza correos antiguos y sugiere acciones de limpieza usando IA.
    
    Args:
        usuario_id: ID del usuario
        meses_minimos: Mínimo de meses para considerar un correo como antiguo
        
    Returns:
        Lista de sugerencias de limpieza
    """
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    # Fecha límite para correos antiguos
    fecha_limite = datetime.utcnow() - timedelta(days=meses_minimos * 30)
    fecha_limite_str = fecha_limite.strftime('%Y-%m-%d %H:%M:%S')
    
    # Buscar correos antiguos en logs
    cursor.execute(
        f"""
        SELECT 
            DISTINCT remitente,
            COUNT(*) as total_correos,
            MAX(fecha) as ultimo_correo,
            MIN(fecha) as primer_correo,
            COUNT(CASE WHEN accion = 'NADA' THEN 1 END) as correos_sin_accion,
            COUNT(CASE WHEN categoria = 'ANUNCIO' THEN 1 END) as correos_anuncio,
            AVG(LENGTH(asunto)) as promedio_asunto
        FROM logs 
        WHERE usuario_id = {p} 
            AND fecha < {p}
            AND remitente IS NOT NULL 
            AND remitente != ''
        GROUP BY remitente
        HAVING COUNT(*) >= 3
        ORDER BY total_correos DESC, ultimo_correo DESC
        LIMIT 50
        """,
        (usuario_id, fecha_limite_str)
    )
    
    resultados = cursor.fetchall()
    conn.close()
    
    sugerencias = []
    
    for remitente, total_correos, ultimo_correo, primer_correo, sin_accion, anuncios, promedio_asunto in resultados:
        # Análisis con IA para determinar categoría de limpieza
        categoria = _categorizar_remitente_ia(
            remitente, total_correos, sin_accion, anuncios, promedio_asunto, ultimo_correo, primer_correo
        )
        
        sugerencia = {
            'remitente': remitente,
            'total_correos': total_correos,
            'ultimo_correo': ultimo_correo,
            'primer_correo': primer_correo,
            'categoria': categoria['tipo'],
            'razon': categoria['razon'],
            'confianza': categoria['confianza'],
            'accion_sugerida': categoria['accion'],
            'prioridad': categoria['prioridad'],
            'dias_antiguedad': (datetime.utcnow() - datetime.strptime(ultimo_correo[:19], '%Y-%m-%d')).days
        }
        
        sugerencias.append(sugerencia)
    
    return sugerencias


def _categorizar_remitente_ia(
    remitente: str, 
    total_correos: int, 
    sin_accion: int, 
    anuncios: int, 
    promedio_asunto: float,
    ultimo_correo: str,
    primer_correo: str
) -> Dict[str, Any]:
    """
    Algoritmo de IA para categorizar remitentes y sugerir acciones.
    """
    
    # Análisis del dominio
    dominio = remitente.split('@')[-1].lower() if '@' in remitente else ''
    
    # Patrones de spam/marketing
    patrones_spam = [
        r'.*newsletter.*', r'.*marketing.*', r'.*promo.*', r'.*offer.*',
        r'.*deal.*', r'.*discount.*', r'.*sale.*', r'.*shop.*',
        r'.*noreply.*', r'.*unsubscribe.*'
    ]
    
    # Dominios sospechosos
    dominios_sospechosos = [
        'spam', 'scam', 'fake', 'temp', 'throwaway', 'guerrillamail',
        '10minutemail', 'yopmail', 'mailinator'
    ]
    
    # Inicializar categoría
    categoria = {
        'tipo': 'desconocido',
        'razon': 'Sin análisis',
        'confianza': 50,
        'accion': 'revisar',
        'prioridad': 'media'
    }
    
    # Análisis basado en patrones
    es_spam_probable = any(re.search(pattern, remitente.lower()) or re.search(pattern, dominio) for pattern in patrones_spam)
    es_dominio_sospechoso = any(sospechoso in dominio for sospechoso in dominios_sospechosos)
    
    # Lógica de decisión
    if es_dominio_sospechoso or es_spam_probable:
        categoria.update({
            'tipo': 'spam',
            'razon': 'Dominio o patrón sospechoso detectado',
            'confianza': 10,
            'accion': 'eliminar',
            'prioridad': 'alta'
        })
    elif anuncios > total_correos * 0.7:  # Más del 70% son anuncios
        categoria.update({
            'tipo': 'marketing',
            'razon': 'Alta tasa de correos promocionales',
            'confianza': 20,
            'accion': 'bloquear',
            'prioridad': 'alta'
        })
    elif sin_accion > total_correos * 0.8:  # Más del 80% sin acción
        categoria.update({
            'tipo': 'inactivo',
            'razon': 'Alta tasa de correos sin acción del usuario',
            'confianza': 15,
            'accion': 'archivar',
            'prioridad': 'media'
        })
    elif total_correos > 20:  # Muchos correos
        categoria.update({
            'tipo': 'frecuente',
            'razon': 'Alto volumen de correos recibidos',
            'confianza': 60,
            'accion': 'revisar',
            'prioridad': 'media'
        })
    elif 'noreply' in remitente.lower():
        categoria.update({
            'tipo': 'automático',
            'razon': 'Correo automático sin respuesta posible',
            'confianza': 40,
            'accion': 'archivar',
            'prioridad': 'baja'
        })
    else:
        categoria.update({
            'tipo': 'normal',
            'razon': 'Patrón de comunicación normal',
            'confianza': 70,
            'accion': 'mantener',
            'prioridad': 'baja'
        })
    
    # Ajustes basados en la antigüedad
    try:
        ultimo_dt = datetime.strptime(ultimo_correo[:19], '%Y-%m-%d')
        antiguedad_dias = (datetime.utcnow() - ultimo_dt).days
        
        if antiguedad_dias > 365:  # Más de 1 año
            categoria['accion'] = 'eliminar'
            categoria['prioridad'] = 'alta'
            categoria['razon'] += ' (muy antiguo)'
        elif antiguedad_dias > 180:  # Más de 6 meses
            if categoria['prioridad'] == 'media':
                categoria['prioridad'] = 'alta'
                categoria['razon'] += ' (antiguo)'
    except:
        pass
    
    return categoria


def obtener_estadisticas_limpieza(usuario_id: int) -> Dict[str, Any]:
    """
    Obtiene estadísticas detalladas para el dashboard de limpieza.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    # Estadísticas generales
    cursor.execute(
        f"""
        SELECT 
            COUNT(*) as total_correos,
            COUNT(CASE WHEN fecha < datetime('now', '-6 months') THEN 1 END) as correos_6meses,
            COUNT(CASE WHEN fecha < datetime('now', '-1 year') THEN 1 END) as correos_1ano,
            COUNT(CASE WHEN accion = 'NADA' THEN 1 END) as correos_sin_accion,
            COUNT(DISTINCT remitente) as remitentes_unicos
        FROM logs 
        WHERE usuario_id = {p}
        """,
        (usuario_id,)
    )
    
    stats_generales = cursor.fetchone()
    
    # Estadísticas por categoría
    cursor.execute(
        f"""
        SELECT 
            categoria,
            COUNT(*) as total,
            COUNT(CASE WHEN fecha >= datetime('now', '-30 days') THEN 1 END) as recientes
        FROM logs 
        WHERE usuario_id = {p}
            AND categoria IS NOT NULL
        GROUP BY categoria
        ORDER BY total DESC
        """,
        (usuario_id,)
    )
    
    stats_categoria = cursor.fetchall()
    
    # Espacio potencial liberado
    cursor.execute(
        f"""
        SELECT 
            SUM(CASE WHEN LENGTH(asunto) * 1000 + LENGTH(resumen) * 500 THEN 1 ELSE 0 END) as kb_estimados
        FROM logs 
        WHERE usuario_id = {p}
            AND fecha < datetime('now', '-6 months')
        """,
        (usuario_id,)
    )
    
    espacio_stats = cursor.fetchone()
    
    conn.close()
    
    return {
        'generales': stats_generales,
        'categorias': stats_categoria,
        'espacio_liberable': espacio_stats,
        'fecha_analisis': datetime.utcnow().isoformat()
    }


def crear_categoria_limpieza(
    usuario_id: int,
    nombre: str,
    descripcion: str,
    remitentes: List[str]
) -> bool:
    """
    Crea una categoría personalizada de limpieza.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    try:
        # Crear tabla si no existe
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
        
        # Insertar categoría
        remitentes_json = str(remitentes)
        ahora = datetime.utcnow().isoformat()
        
        cursor.execute(
            f"""
            INSERT INTO categorias_limpieza 
            (usuario_id, nombre, descripcion, remitentes, fecha_creacion)
            VALUES ({p}, {p}, {p}, {p}, {p})
            """,
            (usuario_id, nombre, descripcion, remitentes_json, ahora)
        )
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error creando categoría de limpieza: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def obtener_categorias_limpieza(usuario_id: int) -> List[Tuple[Any, ...]]:
    """
    Obtiene todas las categorías de limpieza del usuario.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    cursor.execute(
        f"""
        SELECT id, nombre, descripcion, remitentes, fecha_creacion, activa
        FROM categorias_limpieza
        WHERE usuario_id = {p}
        ORDER BY fecha_creacion DESC
        """,
        (usuario_id,)
    )
    
    categorias = cursor.fetchall()
    conn.close()
    return categorias


def ejecutar_limpieza_categoria(
    categoria_id: int,
    usuario_id: int
) -> Dict[str, Any]:
    """
    Ejecuta la limpieza de una categoría específica.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    p = _get_placeholder()
    
    # Obtener información de la categoría
    cursor.execute(
        f"SELECT nombre, remitentes FROM categorias_limpieza WHERE id = {p} AND usuario_id = {p}",
        (categoria_id, usuario_id)
    )
    
    categoria = cursor.fetchone()
    if not categoria:
        return {'error': 'Categoría no encontrada'}
    
    nombre_categoria, remitentes_json = categoria
    remitentes = eval(remitentes_json) if remitentes_json else []
    
    # Contar correos a eliminar/archivar
    correos_eliminados = 0
    correos_archivados = 0
    
    for remitente in remitentes:
        cursor.execute(
            f"""
            UPDATE logs 
            SET accion = 'ELIMINADO_LIMPIEZA', 
                categoria = 'LIMPIEZA_AUTOMATICA'
            WHERE remitente = {p} AND usuario_id = {p}
            """,
            (remitente, usuario_id)
        )
        correos_eliminados += cursor.rowcount
    
    # Actualizar estadísticas
    cursor.execute(
        f"""
        INSERT INTO logs_limpieza 
        (categoria_id, usuario_id, correos_procesados, fecha_ejecucion)
        VALUES ({p}, {p}, {p}, {p})
        """,
        (categoria_id, usuario_id, correos_eliminados, datetime.utcnow().isoformat())
    )
    
    conn.commit()
    conn.close()
    
    return {
        'categoria': nombre_categoria,
        'correos_procesados': correos_eliminados,
        'fecha_ejecucion': datetime.utcnow().isoformat()
    }
