import os
import imaplib
import email
import time
import re
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


def obtener_ids_no_leidos(max_total: int | None = None, usuario: str | None = None, clave_app: str | None = None, desde_fecha: str | None = None) -> List[str]:
    conexion = _abrir_conexion(usuario, clave_app)
    conexion.select("INBOX")
    
    # Construir el comando de búsqueda
    search_criteria = "UNSEEN"
    if desde_fecha:
        # desde_fecha debe venir en formato "DD-Mon-YYYY" (ej: "27-Feb-2026")
        search_criteria = f'(UNSEEN SINCE "{desde_fecha}")'
    
    estado, datos = conexion.search(None, search_criteria)
    ids = datos[0].split()
    conexion.logout()
    ids_decod = [i.decode() for i in ids]
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
) -> None:
    user = usuario or os.environ.get("KYBER_GMAIL_USER")
    pwd = clave_app or os.environ.get("KYBER_GMAIL_APP_PASSWORD")
    if not user or not pwd:
        return
        
    mensaje = MIMEText(cuerpo, _charset="utf-8")
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
