"""Notificaciones de Windows (Toast) para duAI.

Usa QSystemTrayIcon.showMessage() como fallback universal.
Si winotify esta disponible, usa notificaciones nativas de Windows 10/11.
"""

import os
import sys


def _has_winotify():
    try:
        import winotify
        return True
    except ImportError:
        return False


def notify(title, message, icon_path=None, duration=5000):
    """Envia una notificacion al usuario.

    Usa winotify si esta disponible, sino QSystemTrayIcon.
    """
    if _has_winotify():
        try:
            from winotify import Notification, audio
            toast = Notification(
                app_id="duAI",
                title=title,
                msg=message,
                icon=icon_path or "",
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
            return True
        except Exception:
            pass

    # Fallback: QSystemTrayIcon
    try:
        from PySide6.QtWidgets import QSystemTrayIcon
        from PySide6.QtGui import QIcon
        tray = None
        # Buscar tray existente en la app
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.allWidgets():
                if isinstance(widget, QSystemTrayIcon):
                    tray = widget
                    break
        if tray:
            tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration)
            return True
    except Exception:
        pass

    return False


def notify_scan_complete(found, freed_bytes):
    """Notificacion cuando termina un escaneo."""
    if found > 0:
        notify(
            "duAI — Escaneo completo",
            f"Se encontraron {found} rastros de IA. "
            f"Liberables: {freed_bytes // 1024} KB.",
        )
    else:
        notify(
            "duAI — Todo limpio",
            "No se encontraron rastros de IA. Tu privacidad esta protegida.",
        )


def notify_clean_complete(removed, freed_bytes):
    """Notificacion cuando termina una limpieza."""
    notify(
        "duAI — Limpieza completada",
        f"Se eliminaron {removed} items. Liberados: {freed_bytes // (1024*1024)} MB.",
    )


def notify_panic_complete():
    """Notificacion cuando termina el modo panico."""
    notify(
        "duAI — Modo panico",
        "Limpieza total completada. Todos los rastros eliminados.",
    )


def notify_new_achievement(name):
    """Notificacion cuando se desbloquea un logro."""
    notify(
        "duAI — Nuevo logro desbloqueado",
        f"LOGRO: {name}",
    )


def notify_update_available(version):
    """Notificacion cuando hay una actualizacion disponible."""
    notify(
        "duAI — Actualizacion disponible",
        f"Nueva version {version} disponible. Abre duAI para descargarla.",
    )
