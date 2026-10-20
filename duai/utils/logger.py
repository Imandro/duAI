"""Logger estructurado para duAI - Rotación, logging asíncrono, niveles."""

import json
import os
import time
import logging
import logging.handlers
import threading
import queue
import atexit
from pathlib import Path
from .paths import expand


_portable_mode = False
_logger = None
_logger_lock = threading.Lock()

# Async logging
_log_queue = queue.Queue(maxsize=10000)
_log_worker = None
_log_worker_stop = threading.Event()


def set_portable_mode(enabled: bool):
    global _portable_mode, _logger
    _portable_mode = bool(enabled)
    _logger = None  # Forzar reinicialización en próximo log


def is_portable_mode() -> bool:
    return _portable_mode


def base_dir():
    if _portable_mode:
        if getattr(__import__("sys"), "frozen", False):
            import sys
            base = os.path.dirname(sys.executable)
        else:
            import sys
            base = os.path.dirname(os.path.abspath(sys.argv[0] or __file__))
        path = os.path.join(base, "duAI_data")
    else:
        path = expand("%LOCALAPPDATA%/duAI")
    os.makedirs(path, exist_ok=True)
    return path


def logs_dir():
    path = os.path.join(base_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def _get_logger() -> logging.Logger:
    """Obtiene o crea el logger configurado con rotación."""
    global _logger
    with _logger_lock:
        if _logger is not None:
            return _logger

        logger = logging.getLogger("duai")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Limpiar handlers existentes
        logger.handlers.clear()

        log_file = os.path.join(logs_dir(), "duai.log")

        # Rotating file handler: 5MB max, mantener 10 archivos
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)

        # JSON formatter
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
                    "level": record.levelname,
                    "event": getattr(record, "event", record.getMessage()),
                }
                # Añadir campos extra del record
                for key, value in record.__dict__.items():
                    if key not in ("name", "msg", "args", "created", "filename", "funcName",
                                   "levelname", "levelno", "lineno", "module", "msecs",
                                   "message", "name", "pathname", "process",
                                   "processName", "relativeCreated", "thread", "threadName",
                                   "exc_info", "exc_text", "stack_info", "event"):
                        log_entry[key] = value
                return json.dumps(log_entry, ensure_ascii=False)

        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

        _logger = logger
        return _logger


def _log_worker_loop():
    """Thread background que procesa cola de logs."""
    logger = _get_logger()
    while not _log_worker_stop.is_set():
        try:
            record = _log_queue.get(timeout=0.1)
            if record is None:  # Señal de shutdown
                break
            logger.handle(record)
        except queue.Empty:
            continue
        except Exception:
            pass  # Evitar crashear el worker


def _start_log_worker():
    global _log_worker
    if _log_worker is None or not _log_worker.is_alive():
        _log_worker_stop.clear()
        _log_worker = threading.Thread(target=_log_worker_loop, daemon=True)
        _log_worker.start()


def log(event: str, level: int = logging.INFO, **data):
    """Registra un evento con datos estructurados."""
    _start_log_worker()
    logger = _get_logger()
    record = logger.makeRecord(
        "duai", level, __file__, 0, event, (), None, extra=data
    )
    try:
        _log_queue.put_nowait(record)
    except queue.Full:
        # Fallback: log directo síncrono si cola llena
        logger.handle(record)


def log_debug(event: str, **data):
    log(event, logging.DEBUG, **data)


def log_info(event: str, **data):
    log(event, logging.INFO, **data)


def log_warning(event: str, **data):
    log(event, logging.WARNING, **data)


def log_error(event: str, **data):
    log(event, logging.ERROR, **data)


def shutdown_logging():
    """Vacía cola y detiene worker (llamar al salir de la app)."""
    _log_worker_stop.set()
    _log_queue.put(None)  # Señal al worker para salir
    if _log_worker and _log_worker.is_alive():
        _log_worker.join(timeout=2.0)


def open_logs_folder():
    os.startfile(logs_dir())


def get_log_files() -> list[str]:
    """Obtiene todos los archivos de log (actual + rotados)."""
    log_dir = Path(logs_dir())
    return sorted([str(f) for f in log_dir.glob("duai.log*")])


def cleanup_old_logs(max_age_days: int = 30):
    """Elimina archivos de log más antiguos que max_age_days."""
    import time
    log_dir = Path(logs_dir())
    now = time.time()
    for log_file in log_dir.glob("duai.log*"):
        if log_file.stat().st_mtime < now - (max_age_days * 86400):
            try:
                log_file.unlink()
                log("log_cleanup", file=str(log_file))
            except OSError:
                pass


# Registrar shutdown al salir
atexit.register(shutdown_logging)