import os
import imaplib
import email
import time
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.utils import parseaddr
from email.header import decode_header
from typing import Any, Dict, List, Tuple


def _abrir_conexion(usuario: str | None = None, clave_app: str | None = None) -> imaplib.IMAP4_SSL:
    user = usuario or os.environ.get("KYBER_GMAIL_USER")
    pwd = clave_app or os.environ.get("KYBER_GMAIL_APP_PASSWORD")
    if not user or not pwd:
        raise RuntimeError("Credenciales de Gmail no configuradas")
    conexion = imaplib.IMAP4_SSL("imap.gmail.com")
    conexion.login(user, pwd)
    return conexion


def obtener_ids_no_leidos(max_total: int | None = None, usuario: str | None = None, clave_app: str | None = None, desde_fecha: str | None = None, usuario_id: int | None = None) -> List[str]:
    from datetime import datetime, timedelta
    import email.utils
    
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    
    # Detectar día de la semana y configuración de filtro
    hoy = datetime.now()
    dia_semana = hoy.weekday()  # 0=lunes, 1=martes, ..., 6=domingo
    dias_nombres = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
    
    # Verificar configuración de filtro por fecha específica
    filtro_fecha_especifica = 0
    fecha_filtro = None
    
    if usuario_id:
        try:
            from .db import obtener_usuario_por_id
            usuario_data = obtener_usuario_por_id(usuario_id)
            if usuario_data and len(usuario_data) > 11:
                filtro_fecha_especifica = usuario_data[11] if usuario_data[11] is not None else 0
                fecha_filtro = usuario_data[12] if len(usuario_data) > 12 and usuario_data[12] else None
        except Exception as e:
            print(f"⚠️  Error obteniendo configuración de filtro: {e}")
    
    print(f"\n{'='*60}")
    print(f"🔍 ESCANEO INICIADO - Hoy es {dias_nombres[dia_semana]} {hoy.strftime('%d/%m/%Y %H:%M')}")
    if filtro_fecha_especifica == 1 and fecha_filtro:
        print(f"📅 FILTRADO POR FECHA ESPECÍFICA: {fecha_filtro}")
    print(f"{'='*60}")
    
    # Buscar correos no leídos
    estado, datos = conexion.search(None, 'UNSEEN')
    ids = datos[0].split()
    ids_decod = [i.decode() for i in ids]
    
    print(f"📬 Total de correos NO LEÍDOS en bandeja: {len(ids_decod)}")
    
    if ids_decod:
        ids_filtrados = []
        
        # Definir rango de fechas
        if filtro_fecha_especifica == 1 and fecha_filtro:
            # Filtrar por fecha específica
            try:
                fecha_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d')
                fecha_inicio = fecha_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                fecha_fin = fecha_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
                print(f"📅 Filtrando correos de la fecha específica: {fecha_filtro}")
            except Exception as e:
                print(f"⚠️  Error parseando fecha específica, usando fecha actual: {e}")
                fecha_inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
                fecha_fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif desde_fecha:
            # Usar la fecha proporcionada (lógica original para lunes)
            try:
                # Parsear la fecha en formato IMAP "DD-Mon-YYYY"
                fecha_dt = datetime.strptime(desde_fecha, '%d-%b-%Y')
                fecha_inicio = fecha_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                fecha_fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
                print(f"📅 Filtrando correos desde fecha proporcionada: {desde_fecha}")
            except Exception as e:
                print(f"⚠️  Error parseando fecha proporcionada, usando fecha actual: {e}")
                fecha_inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
                fecha_fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Lógica normal según día de la semana
            if dia_semana == 0:  # LUNES
                # Leer correos del sábado (hace 2 días), domingo (hace 1 día) y lunes (hoy)
                fecha_sabado = (hoy - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
                fecha_inicio = fecha_sabado
                fecha_fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
                print(f"📅 Filtrando correos desde SÁBADO {fecha_inicio.strftime('%d/%m/%Y')} hasta LUNES {fecha_fin.strftime('%d/%m/%Y')}")
            else:  # MARTES a DOMINGO
                # Leer solo correos de HOY
                fecha_inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
                fecha_fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
                print(f"📅 Filtrando correos solo de HOY {dias_nombres[dia_semana]} {fecha_inicio.strftime('%d/%m/%Y')}")
        
        # Filtrar correos por fecha
        for correo_id in ids_decod:
            try:
                estado_fetch, datos_fetch = conexion.fetch(correo_id.encode(), '(BODY.PEEK[HEADER.FIELDS (DATE)])')
                if estado_fetch == 'OK':
                    header_data = datos_fetch[0][1]
                    msg = email.message_from_bytes(header_data)
                    fecha_str = msg.get('Date', '')
                    
                    if fecha_str:
                        fecha_tuple = email.utils.parsedate_tz(fecha_str)
                        if fecha_tuple:
                            fecha_correo = datetime.fromtimestamp(email.utils.mktime_tz(fecha_tuple))
                            
                            # Verificar si el correo está en el rango de fechas
                            if fecha_inicio <= fecha_correo <= fecha_fin:
                                ids_filtrados.append(correo_id)
                            else:
                                print(f"🔍 Correo ID {correo_id}: {fecha_correo.strftime('%d/%m/%Y %H:%M')} - Fuera del rango")
                    else:
                        print(f"⚠️  Correo ID {correo_id} no tiene fecha, incluyendo por seguridad")
                        ids_filtrados.append(correo_id)
            except Exception as e:
                print(f"⚠️  Error procesando correo ID {correo_id}: {e}")
                ids_filtrados.append(correo_id)
        
        ids_decod = ids_filtrados
        print(f"✅ Correos que cumplen el filtro de fecha: {len(ids_decod)}")
    
    conexion.logout()
    
    if max_total is not None:
        ids_decod = ids_decod[-max_total:]
    
    return ids_decod


def obtener_correos_por_ids(ids: List[str], usuario: str | None = None, clave_app: str | None = None) -> List[Dict[str, Any]]:
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    resultados: List[Dict[str, str]] = []
    for correo_id in ids:
        estado, datos_correo = conexion.fetch(correo_id.encode(), "(BODY.PEEK[] X-GM-THRID)")
        if estado != "OK":
            continue
        raw = datos_correo[0]
        raw_bytes = raw[1] if isinstance(raw, tuple) else raw
        mensaje = email.message_from_bytes(raw_bytes)
        thread_id = ""
        try:
            raw_str = raw[0].decode() if isinstance(raw, tuple) else b"".decode()
        except Exception:
            raw_str = ""
        try:
            if not raw_str and isinstance(datos_correo[0], bytes):
                raw_str = datos_correo[0].decode(errors="ignore")
        except Exception:
            pass
        try:
            mthr = re.search(r"X-GM-THRID\s+(\d+)", raw_str or "")
            if mthr:
                thread_id = mthr.group(1)
        except Exception:
            thread_id = ""
        remitente_raw = mensaje.get("From", "")
        asunto_raw = mensaje.get("Subject", "")
        message_id = mensaje.get("Message-ID", "")

        def _dec(h: str) -> str:
            try:
                parts = decode_header(h)
                out = ""
                for text, enc in parts:
                    if isinstance(text, bytes):
                        out += text.decode(enc or "utf-8", errors="replace")
                    else:
                        out += text
                return out
            except Exception:
                return h

        remitente = _dec(remitente_raw)
        asunto = _dec(asunto_raw)
        from_email = parseaddr(remitente_raw)[1]

        cuerpo = ""
        imagen_mime: str | None = None
        imagen_datos: bytes | None = None
        if mensaje.is_multipart():
            for parte in mensaje.walk():
                tipo = parte.get_content_type()
                disposicion = str(parte.get("Content-Disposition"))
                if tipo == "text/plain" and "attachment" not in disposicion:
                    cuerpo = parte.get_payload(decode=True).decode(
                        parte.get_content_charset() or "utf-8",
                        errors="replace",
                    )
                    break
            if not cuerpo:
                for parte in mensaje.walk():
                    tipo = parte.get_content_type()
                    disposicion = str(parte.get("Content-Disposition"))
                    if tipo == "text/html" and "attachment" not in disposicion:
                        html = parte.get_payload(decode=True).decode(
                            parte.get_content_charset() or "utf-8",
                            errors="replace",
                        )
                        cuerpo = re.sub(r"<[^>]+>", " ", html)
                        cuerpo = re.sub(r"\s+", " ", cuerpo).strip()
                        break
            if imagen_mime is None:
                for parte in mensaje.walk():
                    tipo = parte.get_content_type()
                    if tipo.startswith("image/"):
                        datos = parte.get_payload(decode=True)
                        if isinstance(datos, bytes):
                            imagen_mime = tipo
                            imagen_datos = datos
                            break
        else:
            cuerpo = mensaje.get_payload(decode=True).decode(
                mensaje.get_content_charset() or "utf-8",
                errors="replace",
            )

        resultados.append(
            {
                "id": correo_id,
                "remitente": remitente,
                "asunto": asunto,
                "cuerpo": cuerpo,
                "message_id": message_id,
                "from_email": from_email or remitente,
                "imagen_mime": imagen_mime,
                "imagen_datos": imagen_datos,
                "thread_id": thread_id,
            }
        )

    conexion.logout()
    return resultados

def obtener_historial_por_thread(thread_id: str, limite: int = 5, usuario: str | None = None, clave_app: str | None = None) -> List[Dict[str, Any]]:
    if not thread_id:
        return []
    conexion = _abrir_conexion(usuario, clave_app)
    try:
        conexion.select("[Gmail]/All Mail")
    except Exception:
        conexion.select("INBOX")
    estado, datos = conexion.search(None, f"X-GM-THRID {thread_id}")
    if estado != "OK":
        conexion.logout()
        return []
    ids = datos[0].split()
    ids_decod = [i.decode() for i in ids][-limite:]
    historial: List[Dict[str, Any]] = []
    for mid in ids_decod:
        est2, dat2 = conexion.fetch(mid.encode(), "(BODY.PEEK[])")
        if est2 != "OK":
            continue
        msg = email.message_from_bytes(dat2[0][1])
        remitente_raw = msg.get("From", "")
        asunto_raw = msg.get("Subject", "")
        fecha_raw = msg.get("Date", "")
        def _dec(h: str) -> str:
            try:
                parts = decode_header(h)
                out = ""
                for text, enc in parts:
                    if isinstance(text, bytes):
                        out += text.decode(enc or "utf-8", errors="replace")
                    else:
                        out += text
                return out
            except Exception:
                return h
        remitente = _dec(remitente_raw)
        asunto = _dec(asunto_raw)
        cuerpo = ""
        if msg.is_multipart():
            for parte in msg.walk():
                tipo = parte.get_content_type()
                disp = str(parte.get("Content-Disposition"))
                if tipo == "text/plain" and "attachment" not in disp:
                    try:
                        cuerpo = parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", errors="replace")
                    except Exception:
                        cuerpo = ""
                    break
        else:
            try:
                cuerpo = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                cuerpo = ""
        cuerpo = re.sub(r"\s+", " ", cuerpo or "").strip()
        historial.append({"from": remitente, "subject": asunto, "date": fecha_raw, "body": cuerpo})
    conexion.logout()
    return historial


def marcar_como_leido(ids: List[str], usuario: str | None = None, clave_app: str | None = None) -> None:
    if not ids:
        return
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    for correo_id in ids:
        try:
            conexion.store(correo_id, "+FLAGS", "\\Seen")
        except Exception:
            pass
    conexion.logout()

def marcar_como_no_leido(ids: List[str], usuario: str | None = None, clave_app: str | None = None) -> None:
    if not ids:
        return
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    for correo_id in ids:
        try:
            conexion.store(correo_id, "-FLAGS", "\\Seen")
        except Exception:
            pass
    conexion.logout()
def archivar_ids(ids: List[str], usuario: str | None = None, clave_app: str | None = None) -> None:
    if not ids:
        return
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    for correo_id in ids:
        ok = False
        try:
            conexion.store(correo_id, "+X-GM-LABELS", "Archivados")
        except Exception:
            pass
        try:
            conexion.store(correo_id, "-X-GM-LABELS", "\\Inbox")
            ok = True
        except Exception:
            pass
        if not ok:
            try:
                conexion.store(correo_id, "-X-GM-LABELS", "Inbox")
                ok = True
            except Exception:
                pass
        if not ok:
            try:
                conexion.copy(correo_id, "[Gmail]/All Mail")
                conexion.store(correo_id, "+FLAGS", "\\Deleted")
            except Exception:
                pass
    try:
        conexion.expunge()
    except Exception:
        pass
    conexion.logout()

def crear_borrador(
    responder_a: str,
    asunto: str,
    cuerpo: str,
    in_reply_to: str | None = None,
    references: str | None = None,
    usuario: str | None = None,
    clave_app: str | None = None,
    firma_personalizada: str | None = None,
) -> None:
    user = usuario or os.environ.get("KYBER_GMAIL_USER")
    pwd = clave_app or os.environ.get("KYBER_GMAIL_APP_PASSWORD")
    if not user or not pwd:
        return
        
    firma = firma_personalizada 
    
    # or (
    #     "\n\nFerney Barbosa\n"
    #     "Desarrollador de software\n"
    #     "Coordinación de gestión de tecnologías y las comunicaciones\n"
    #     "Sabanarlarga, Atlántico"
    # )
    
    if firma and firma.strip() not in cuerpo:
        firma_html = firma.replace("\n", "<br>")
        cuerpo = f"{cuerpo}<br>{firma_html}"

    # Convertir saltos de línea del cuerpo a HTML
    cuerpo_html = cuerpo.replace("\n", "<br>")

    mensaje = MIMEText(cuerpo_html, "html", _charset="utf-8")
    mensaje["From"] = user
    mensaje["To"] = responder_a
    mensaje["Subject"] = asunto
    if in_reply_to:
        mensaje["In-Reply-To"] = in_reply_to
    if references:
        mensaje["References"] = references

    conexion = _abrir_conexion(user, pwd)

    timestamp = imaplib.Time2Internaldate(time.time())
    conexion.append(
        "[Gmail]/Drafts",
        "",
        timestamp,
        mensaje.as_bytes(),
    )

    conexion.logout()


def enviar_correo(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    in_reply_to: str | None = None,
    references: str | None = None,
    usuario: str | None = None,
    clave_app: str | None = None,
    firma_personalizada: str | None = None,
) -> bool:
    """Envía un correo electrónico inmediatamente usando SMTP."""
    user = usuario or os.environ.get("KYBER_GMAIL_USER")
    pwd = clave_app or os.environ.get("KYBER_GMAIL_APP_PASSWORD")
    if not user or not pwd:
        return False
        
    firma = firma_personalizada 
    if firma and firma.strip() not in cuerpo:
        firma_html = firma.replace("\n", "<br>")
        cuerpo = f"{cuerpo}<br><br>{firma_html}"

    cuerpo_html = cuerpo.replace("\n", "<br>")

    mensaje = MIMEText(cuerpo_html, "html", _charset="utf-8")
    mensaje["From"] = user
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    if in_reply_to:
        mensaje["In-Reply-To"] = in_reply_to
    if references:
        mensaje["References"] = references

    try:
        import smtplib
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, pwd)
            server.send_message(mensaje)
        return True
    except Exception as e:
        print(f"ERROR AL ENVIAR CORREO: {e}")
        return False

def existe_borrador_para_message_id(message_id: str, usuario: str | None = None, clave_app: str | None = None) -> bool:
    if not message_id:
        return False
    conexion = _abrir_conexion(usuario, clave_app)
    try:
        try:
            conexion.select("[Gmail]/Drafts")
        except Exception:
            try:
                conexion.select("Drafts")
            except Exception:
                return False
        estado, datos = conexion.search(None, "ALL")
        if estado != "OK":
            return False
        ids = datos[0].split()
        for bid in ids:
            est2, dat2 = conexion.fetch(bid, "(BODY.PEEK[HEADER])")
            if est2 != "OK":
                continue
            raw = dat2[0][1]
            try:
                msg = email.message_from_bytes(raw)
            except Exception:
                continue
            in_reply = msg.get("In-Reply-To", "") or ""
            refs = msg.get("References", "") or ""
            if message_id in in_reply or message_id in refs:
                return True
        return False
    finally:
        _FER_DEV_SHEI_200226 = "F-E-R-D-E-V-S-H-E-I-20-02-26"
        try:
            conexion.logout()
        except Exception:
            pass
def existe_borrador_para_thread_id(thread_id: str, usuario: str | None = None, clave_app: str | None = None) -> bool:
    if not thread_id:
        return False
    conexion = _abrir_conexion(usuario, clave_app)
    try:
        try:
            conexion.select("[Gmail]/Drafts")
        except Exception:
            try:
                conexion.select("Drafts")
            except Exception:
                return False
        estado, datos = conexion.search(None, "ALL")
        if estado != "OK":
            return False
        ids = datos[0].split()
        for bid in ids:
            est2, dat2 = conexion.fetch(bid, "(BODY.PEEK[] X-GM-THRID)")
            if est2 != "OK":
                continue
            raw = dat2[0]
            raw_str = ""
            try:
                raw_str = raw[0].decode() if isinstance(raw, tuple) else b"".decode()
            except Exception:
                raw_str = ""
            try:
                if not raw_str and isinstance(dat2[0], bytes):
                    raw_str = dat2[0].decode(errors="ignore")
            except Exception:
                pass
            try:
                mthr = re.search(r"X-GM-THRID\s+(\d+)", raw_str or "")
                if mthr and mthr.group(1) == thread_id:
                    return True
            except Exception:
                pass
        return False
    finally:
        try:
            conexion.logout()
        except Exception:
            pass


def detectar_link_unsubscribe(mensaje: email.message.Message) -> str | None:
    """Detecta el link de cancelación de suscripción en un correo."""
    # Buscar en header List-Unsubscribe
    list_unsub = mensaje.get("List-Unsubscribe", "")
    if list_unsub:
        # Extraer URL del header
        match = re.search(r'<(https?://[^>]+)>', list_unsub)
        if match:
            return match.group(1)
    
    # Buscar en el cuerpo del correo
    cuerpo = ""
    if mensaje.is_multipart():
        for parte in mensaje.walk():
            tipo = parte.get_content_type()
            if tipo == "text/html":
                try:
                    html = parte.get_payload(decode=True).decode(
                        parte.get_content_charset() or "utf-8",
                        errors="replace"
                    )
                    cuerpo = html
                    break
                except Exception:
                    pass
    else:
        try:
            cuerpo = mensaje.get_payload(decode=True).decode(
                mensaje.get_content_charset() or "utf-8",
                errors="replace"
            )
        except Exception:
            pass
    
    if cuerpo:
        # Buscar links con palabras clave
        patrones = [
            r'href=["\']([^"\']*(?:unsubscribe|opt-out|remove|cancelar|baja)[^"\']*)["\']',
            r'(https?://[^\s<>"]+(?:unsubscribe|opt-out|remove|cancelar|baja)[^\s<>"]*)',
        ]
        for patron in patrones:
            match = re.search(patron, cuerpo, re.IGNORECASE)
            if match:
                return match.group(1)
    
    return None


def eliminar_correos_por_ids(ids: List[str], usuario: str | None = None, clave_app: str | None = None) -> int:
    """Elimina permanentemente correos por sus IDs."""
    if not ids:
        return 0
    
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    eliminados = 0
    
    for correo_id in ids:
        try:
            # Marcar como eliminado
            conexion.store(correo_id, "+FLAGS", "\\Deleted")
            eliminados += 1
        except Exception:
            pass
    
    # Expunge para eliminar permanentemente
    try:
        conexion.expunge()
    except Exception:
        pass
    
    conexion.logout()
    return eliminados


def obtener_correos_antiguos(dias: int = 90, max_total: int = 100, usuario: str | None = None, clave_app: str | None = None) -> List[str]:
    """Obtiene IDs de correos más antiguos que X días."""
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    
    # Calcular fecha límite
    fecha_limite = datetime.utcnow() - timedelta(days=dias)
    fecha_str = fecha_limite.strftime("%d-%b-%Y")
    
    # Buscar correos antes de esa fecha
    estado, datos = conexion.search(None, f'BEFORE {fecha_str}')
    ids = datos[0].split()
    conexion.logout()
    
    ids_decod = [i.decode() for i in ids]
    if max_total is not None:
        ids_decod = ids_decod[:max_total]
    
    return ids_decod
