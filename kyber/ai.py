import os
import re
from typing import Dict, List, Any

import google.generativeai as genai

from .db import obtener_reglas, obtener_respuestas


def _configurar_modelo(api_key: str | None = None) -> genai.GenerativeModel:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-2.5-flash")


def _reglas_como_texto() -> str:
    reglas = obtener_reglas()
    items: List[tuple[int, str, str, str]] = []
    for _, clave, instruccion, prioridad, tipo, etiquetas, es_principal, auto_enviar in reglas:
        tipo_norm = (tipo or "negocio").lower()
        # Solo incluir reglas de tipo 'negocio' aquí
        if tipo_norm != "negocio":
            continue
        try:
            prio_val = int(prioridad)
        except Exception:
            prio_val = 3
        
        linea = f"[PRIORIDAD {prio_val}] {clave}: {instruccion}"
        if auto_enviar:
            linea += " (AUTO-ENVÍO ACTIVO: Si aplica esta regla, marca auto_enviar=true)"
            
        items.append((prio_val, str(clave), linea))
    # Orden: prioridad ASC (1, 2, 3...)
    items.sort(key=lambda x: (x[0], x[1]))
    partes = [linea for _, _, linea in items]
    texto = "\n".join(partes)
    return texto if texto else "Sin reglas de negocio específicas."


def _tareas_politicas_como_texto() -> tuple[str, str]:
    reglas = obtener_reglas()
    tareas_items: List[tuple[int, str]] = []
    politicas_items: List[tuple[int, str]] = []
    
    for _, clave, instruccion, prioridad, tipo, etiquetas, _ in reglas:
        tipo_norm = (tipo or "").lower()
        try:
            prio_val = int(prioridad)
        except Exception:
            prio_val = 3
            
        linea = f"[PRIORIDAD {prio_val}] {clave}: {instruccion}"
        
        if tipo_norm == "tarea":
            tareas_items.append((prio_val, linea))
        elif tipo_norm == "politica":
            politicas_items.append((prio_val, linea))
            
    # Ordenar por prioridad ASC (1, 2, 3...)
    tareas_items.sort(key=lambda x: x[0])
    politicas_items.sort(key=lambda x: x[0])
    
    tareas_str = "\n".join([x[1] for x in tareas_items])
    politicas_str = "\n".join([x[1] for x in politicas_items])
    
    return (
        tareas_str if tareas_str else "Sin tareas adicionales.",
        politicas_str if politicas_str else "Sin políticas adicionales."
    )


def _plantillas_como_texto() -> str:
    plantillas = obtener_respuestas()
    partes: List[str] = []
    for pid, titulo, contenido in plantillas:
        partes.append(f"ID {pid} | TITULO: {titulo}\nTEXTO_COMPLETO:\n{contenido}\n---")
    if not partes:
        return "No hay plantillas configuradas; si no encuentras coincidencia clara, redacta un borrador normal."
    return "\n".join(partes)


def traducir_texto(texto: str, direccion: str, api_key: str | None = None) -> str:
    modelo = _configurar_modelo(api_key)
    dir_norm = (direccion or "").lower()
    if dir_norm == "es_en":
        instruccion = "Traduce el siguiente texto de español a inglés. Responde solo con la traducción, sin explicaciones ni comentarios adicionales."
    else:
        instruccion = "Traduce el siguiente texto de inglés a español. Responde solo con la traducción, sin explicaciones ni comentarios adicionales."
    prompt = f"{instruccion}\n\n{texto}"
    respuesta = modelo.generate_content(prompt)
    return respuesta.text or ""


def _parse_json(texto: str) -> Dict[str, str]:
    import json

    try:
        return json.loads(texto)
    except Exception:
        pass
    try:
        m = re.search(r"\{[\s\S]*\}", texto)
        if m:
            candidato = m.group(0)
            return json.loads(candidato)
    except Exception:
        pass
    try:
        limpio = texto.strip().replace("“", '"').replace("”", '"').replace("'", '"')
        return json.loads(limpio)
    except Exception:
        return {
            "accion": "NADA",
            "idioma": "desconocido",
            "borrador": "",
            "resumen_es": "No se pudo interpretar la respuesta de la IA.",
            "plantilla_id": 0,
            "categoria": "GENERAL",
        }


def procesar_correo_con_ia(
    remitente: str,
    asunto: str,
    cuerpo: str,
    imagen_mime: str | None = None,
    imagen_datos: bytes | None = None,
    historial_texto: str | None = None,
    api_key: str | None = None,
    contexto_negocio: str | None = None,
) -> Dict[str, str]:
    """Procesa un correo electrónico utilizando IA para clasificarlo y generar borradores."""
    modelo = _configurar_modelo(api_key)
    reglas_negocio_texto = _reglas_como_texto()
    plantillas_texto = _plantillas_como_texto()
    tareas_texto, politicas_texto = _tareas_politicas_como_texto()

    # Definir el contexto del negocio (Rol del Agente)
    rol_agente = contexto_negocio if contexto_negocio and contexto_negocio.strip() else "Eres un asistente virtual experto en gestión de correos."

    cuerpo = re.sub(r'<[^>]+>', '', cuerpo)
    cuerpo = re.sub(r'https?://\S+', '', cuerpo)
    cuerpo = re.sub(r'\s+', ' ', cuerpo).strip()
    cuerpo = cuerpo[:3000] # Limitar a 3000 caracteres para tener más contexto

    # Prompt GENÉRICO y ORDENADO
    prompt = f"""
    ROL Y CONTEXTO DEL NEGOCIO:
    {rol_agente}

    OBJETIVO PRINCIPAL:
    Clasificar el correo y, si es necesario, redactar un borrador de respuesta. Debes actuar siguiendo estrictamente el orden de prioridad de las reglas definidas abajo.

    --- SECCIÓN 1: REGLAS DE NEGOCIO (Ejecutar en orden de prioridad ascendente: 1, 2, 3...) ---
    Estas reglas definen QUÉ hacer con el correo.
    {reglas_negocio_texto}

    --- SECCIÓN 2: POLÍTICAS (Ejecutar en orden de prioridad ascendente: 1, 2, 3...) ---
    Estas son normas obligatorias que limitan o guían tu comportamiento.
    {politicas_texto}

    --- SECCIÓN 3: TAREAS (Ejecutar en orden de prioridad ascendente: 1, 2, 3...) ---
    Acciones específicas que debes realizar durante el análisis.
    {tareas_texto}

    --- SECCIÓN 4: PLANTILLAS DISPONIBLES ---
    {plantillas_texto}

    --- CORREO RECIBIDO ---
    - Remitente: {remitente}
    - Asunto: {asunto}
    - Cuerpo:
    {cuerpo}

    HISTORIAL:
    {historial_texto if historial_texto else "Sin historial disponible"}

    INSTRUCCIONES DE PROCESAMIENTO:
    1. ANALIZA si el correo es "ANUNCIO" (Spam, Marketing, Newsletter).
       - SI ES ANUNCIO: Debes responder con "accion": "NADA". ¡IGNÓRALO COMPLETAMENTE!
    
    2. SI NO ES ANUNCIO, busca una REGLA DE NEGOCIO o POLÍTICA que aplique.
       - Sigue el orden de prioridad ascendente (1, 2, 3...).
    
    3. SELECCIÓN DE ACCIÓN:
       - Si una regla dice "No responder" o "Ignorar" -> "accion": "NADA".
       - Si requiere respuesta -> "accion": "BORRADOR".
         * Intenta usar una PLANTILLA disponible.
         * Si usas plantilla, rellena los huecos (placeholders) con la info del correo o déjalos indicados (ej: [PRECIO]).
         * Si no hay plantilla, redacta una respuesta profesional siguiendo el ROL DEL AGENTE.

    4. FORMATO JSON DE SALIDA:
    {{
    "accion": "BORRADOR" | "NADA",
    "idioma": "es" | "en" | "otro",
    "borrador": "texto del borrador o vacío",
    "resumen_es": "breve justificación de la acción tomada",
    "plantilla_id": 0 | ID de plantilla,
    "categoria": "GENERAL" | "ANUNCIO" | "COTIZACIONES",
    "auto_enviar": true | false (Solo si la regla aplicada tiene AUTO-ENVÍO ACTIVO)
    }}
    """
    
    if imagen_mime and imagen_datos:
        respuesta = modelo.generate_content(
            [
                prompt,
                {
                    "mime_type": imagen_mime,
                    "data": imagen_datos,
                },
            ]
        )
    else:
        respuesta = modelo.generate_content(prompt)
    texto = respuesta.text or ""
    datos = _parse_json(texto)

    accion = str(datos.get("accion", "NADA")).upper()
    if accion not in {"BORRADOR", "NADA"}:
        accion = "NADA"

    try:
        plantilla_id_val = int(datos.get("plantilla_id", 0))
    except Exception:
        plantilla_id_val = 0
    if plantilla_id_val < 0:
        plantilla_id_val = 0

    categoria_val = str(datos.get("categoria", "") or "").upper()
    if categoria_val not in {"COTIZACIONES", "ANUNCIO", "GENERAL"}:
        categoria_val = ""

    borrador_texto = str(datos.get("borrador", ""))
    auto_enviar_val = bool(datos.get("auto_enviar", False))

    resultado: Dict[str, Any] = {
        "accion": accion,
        "idioma": str(datos.get("idioma", "desconocido")),
        "borrador": borrador_texto,
        "resumen_es": str(datos.get("resumen_es", "")),
        "plantilla_id": plantilla_id_val,
        "categoria": categoria_val,
        "auto_enviar": auto_enviar_val,
    }
    return resultado


def sugerir_clave_prioridad(instruccion: str, api_key: str | None = None) -> Dict[str, str]:
    modelo = _configurar_modelo(api_key)
    guia = """
Eres un asistente que clasifica y titula reglas de educación para un agente de correo.
Objetivo:
- Genera una CLAVE concisa y capitalizada (1–3 palabras, sin guiones ni guiones bajos) que represente la instrucción.
- Asigna una PRIORIDAD del 1 al 5:
  5: política crítica (bloquear borrador, no responder, cotizaciones/presupuesto, cumplimiento estricto)
  4: decisión operativa relevante (filtrar no accionables, spam suave, uso obligado de plantilla)
  3: comportamiento estándar o general (normas por defecto)
  2: ajustes de tono/estilo/idioma/cortesía
  1: sugerencia menor o cosmética
Devuelve SOLO JSON con:
{"clave": "Texto Capitalizado", "prioridad": 1}
"""
    prompt = f"{guia}\n\nINSTRUCCION:\n{instruccion}\n\nJSON:"
    respuesta = modelo.generate_content(prompt)
    texto = respuesta.text or ""
    datos = _parse_json(texto)
    clave = str(datos.get("clave", "")).strip()
    try:
        prioridad_val = int(datos.get("prioridad", 3))
    except Exception:
        prioridad_val = 3
    if prioridad_val < 1 or prioridad_val > 5:
        prioridad_val = 3
    if not clave:
        palabras = (instruccion or "").strip().split()
        w1 = palabras[0].capitalize() if palabras else "General"
        w2 = palabras[1].lower() if len(palabras) > 1 else ""
        clave = f"{w1} {w2}".strip() if w2 else w1
    _FER_DEV_SHEI_200226 = "F-E-R-D-E-V-S-H-E-I-20-02-26"
    return {"clave": clave, "prioridad": str(prioridad_val)}


def sugerir_etiquetas(instruccion: str, api_key: str | None = None) -> Dict[str, str]:
    modelo = _configurar_modelo(api_key)
    guia = """
Genera etiquetas cortas y en minúsculas, separadas por comas, basadas en la instrucción.
Reglas:
- 1 a 5 etiquetas máximo.
- Evita duplicados y palabras vacías.
- Usa términos comunes del dominio: cotizaciones, serial, modelo, pieza, idioma, ingles, español, anuncio, spam, plantillas, borrador, seguimiento, general.
Devuelve SOLO JSON:
{"etiquetas": "tag1, tag2"}
"""
    prompt = f"{guia}\n\nINSTRUCCION:\n{instruccion}\n\nJSON:"
    respuesta = modelo.generate_content(prompt)
    texto = respuesta.text or ""
    datos = _parse_json(texto)
    etiquetas_raw = str(datos.get("etiquetas", "")).strip()
    if not etiquetas_raw:
        base = (instruccion or "").lower()
        sugeridas = []
        if any(k in base for k in ["cotiz", "presup", "precio"]):
            sugeridas.append("cotizaciones")
        if "serial" in base or "serie" in base:
            sugeridas.append("serial")
        if "modelo" in base:
            sugeridas.append("modelo")
        if "pieza" in base or "part number" in base or "repuesto" in base:
            sugeridas.append("pieza")
        if "inglés" in base or "english" in base:
            sugeridas.append("ingles")
        if "español" in base or "spanish" in base:
            sugeridas.append("español")
        if any(k in base for k in ["promoc", "descuento", "newsletter", "campaña"]):
            sugeridas.append("anuncio")
        if "plantilla" in base:
            sugeridas.append("plantillas")
        etiquetas_raw = ", ".join(dict.fromkeys(sugeridas))  # elimina duplicados conservando orden
    return {"etiquetas": etiquetas_raw}
