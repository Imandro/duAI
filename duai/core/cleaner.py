import os
import shutil
import sqlite3
import tempfile
import time

from . import registry_clean, system_clean
from .scanner import STATUS_FOUND, STATUS_READY, ScanReport
from ..utils.paths import delete_filesystem, fmt_bytes


class CleanOptions:
    MODE_RECYCLE = "recycle"
    MODE_PERMANENT = "permanent"
    MODE_QUARANTINE = "quarantine"

    def __init__(self, selected=None, permanent=False, preview=False, mode=None):
        self.selected = selected or set()
        self.preview = preview
        if mode in (self.MODE_RECYCLE, self.MODE_PERMANENT, self.MODE_QUARANTINE):
            self.mode = mode
        else:
            self.mode = self.MODE_PERMANENT if permanent else self.MODE_RECYCLE

    @property
    def permanent(self):
        return self.mode == self.MODE_PERMANENT


class CleanResult:
    def __init__(self):
        self.lines = []
        self.freed_bytes = 0
        self.removed_items = 0
        self.errors = 0
        self.preview = False

    def add(self, line):
        self.lines.append(line)

    def summary(self):
        mode = "VISTA PREVIA" if self.preview else "COMPLETADA"
        head = f"LIMPIEZA {mode} - {self.removed_items} elementos, {fmt_bytes(self.freed_bytes)} liberados"
        if self.errors:
            head += f", {self.errors} errores"
        return head


def run_clean(report: ScanReport, options: CleanOptions) -> CleanResult:
    result = CleanResult()
    result.preview = options.preview

    for entry in report.entries:
        target_id = entry.target.id
        if entry.target.kind_action == "registry":
            if target_id not in options.selected:
                continue
            _clean_registry_entry(entry, result, options)
            continue
        if entry.status not in (STATUS_FOUND, STATUS_READY):
            continue
        if target_id not in options.selected:
            continue

        kind_action = entry.target.kind_action
        if kind_action == "dns":
            if options.preview:
                result.add("[PREVIEW] Vaciaria la cache DNS")
            else:
                ok = system_clean.flush_dns()
                result.add("Cache DNS vaciada" if ok else "No se pudo vaciar la cache DNS")
                result.errors += 0 if ok else 1
        elif kind_action == "clipboard":
            if options.preview:
                result.add("[PREVIEW] Borraria el portapapeles y su historial")
            else:
                system_clean.clear_clipboard()
                result.add("Portapapeles borrado")
        elif kind_action == "timeline":
            if options.preview:
                result.add(f"[PREVIEW] Borraria la cronologia de actividades ({entry.total_bytes} bytes)")
                result.freed_bytes += entry.total_bytes
            else:
                ok = system_clean.clean_timeline()
                result.add("Cronologia de actividades borrada" if ok else "Cronologia bloqueada por el sistema")
                result.errors += 0 if ok else 1
                result.freed_bytes += entry.total_bytes
        elif kind_action == "location":
            if options.preview:
                result.add(f"[PREVIEW] Borraria {len(entry.items)} archivos de historial de ubicacion")
            else:
                removed = system_clean.clean_location_history()
                result.add(f"{removed} archivos de ubicacion eliminados")
                result.removed_items += removed
        elif entry.target.kind == "browser_history":
            domains = entry.target.meta.get("domains", [])
            if not domains:
                continue
            total_rows = 0
            dbs = [item.path for item in entry.items]
            for db_path in dbs:
                if options.preview:
                    result.add(f"[PREVIEW] {label_of(entry)}: depuraria historial IA en {os.path.basename(db_path)}")
                    continue
                rows = clean_browser_history(db_path, domains)
                if rows < 0:
                    result.add(f"{label_of(entry)}: base bloqueada o ilegible ({os.path.basename(db_path)})")
                    result.errors += 1
                else:
                    total_rows += rows
            if not options.preview:
                result.add(f"{label_of(entry)}: {total_rows} registros de historial IA eliminados")
        else:
            _clean_filesystem_entry(entry, result, options)

    return result


def label_of(entry):
    return entry.target.name


def _clean_filesystem_entry(entry, result, options):
    label = entry.target.name
    items = sorted({item.path for item in entry.items}, key=lambda p: len(p), reverse=True)
    total_bytes = sum(item.size for item in entry.items)
    if not items:
        return
    if options.preview:
        result.add(f"[PREVIEW] {label}: {len(items)} elementos, {fmt_bytes(total_bytes)}")
        for path in items[:8]:
            result.add(f"    {path}")
        if len(items) > 8:
            result.add(f"    ... y {len(items) - 8} mas")
        result.freed_bytes += total_bytes
        result.removed_items += len(items)
        return
    removed = 0
    freed = 0
    sizes = {item.path: item.size for item in entry.items}
    for path in items:
        size = sizes.get(path, 0)
        if options.mode == CleanOptions.MODE_QUARANTINE:
            from .quarantine import quarantine_path

            ok = quarantine_path(path)
        else:
            ok = delete_filesystem(path, permanent=options.permanent)
        if ok:
            removed += 1
            freed += size
        else:
            result.errors += 1
    verbs = {
        CleanOptions.MODE_PERMANENT: "Eliminados",
        CleanOptions.MODE_RECYCLE: "A la papelera",
        CleanOptions.MODE_QUARANTINE: "En cuarentena",
    }
    result.add(f"{label}: {verbs[options.mode]} {removed}/{len(items)} ({fmt_bytes(freed)})")
    result.freed_bytes += freed
    result.removed_items += removed


def _clean_registry_entry(entry, result, options):
    if options.preview:
        counts = registry_clean.collect_registry_traces()
        total = sum(counts.values())
        result.add(f"[PREVIEW] Registro: {total} valores serian eliminados ({entry.detail})")
        return
    removed = registry_clean.clean_registry()
    total = sum(removed.values())
    detail = ", ".join(f"{k}: {v}" for k, v in removed.items() if v)
    result.add(f"Registro: {total} valores eliminados" + (f" ({detail})" if detail else ""))


def clean_browser_history(db_path, domains):
    engine = "firefox" if os.path.basename(db_path).lower() == "places.sqlite" else "chromium"
    tmp_dir = tempfile.mkdtemp(prefix="duai_")
    tmp_db = os.path.join(tmp_dir, os.path.basename(db_path))
    deleted_rows = 0
    try:
        shutil.copy2(db_path, tmp_db)
        conn = sqlite3.connect(tmp_db)
        cur = conn.cursor()
        like_params = [f"%{domain}%" for domain in domains]
        where_url = "(" + " OR ".join(["lower(url) LIKE ?"] * len(like_params)) + ")"

        if engine == "chromium":
            url_ids = [r[0] for r in cur.execute(
                f"SELECT id FROM urls WHERE {where_url}", like_params)]
            chain_ids = [r[0] for r in cur.execute(
                f"SELECT DISTINCT id FROM downloads_url_chains WHERE {where_url}", like_params)]
            if url_ids:
                ph = ",".join("?" * len(url_ids))
                cur.execute(f"DELETE FROM visits WHERE url IN ({ph})", url_ids)
                cur.execute(f"DELETE FROM keyword_search_terms WHERE url_id IN ({ph})", url_ids)
                cur.execute(
                    f"DELETE FROM segment_usage WHERE segment_id IN "
                    f"(SELECT id FROM segments WHERE url_id IN ({ph}))",
                    url_ids,
                )
                cur.execute(f"DELETE FROM segments WHERE url_id IN ({ph})", url_ids)
                cur.execute(f"DELETE FROM urls WHERE id IN ({ph})", url_ids)
                deleted_rows += len(url_ids)
            if chain_ids:
                ph = ",".join("?" * len(chain_ids))
                cur.execute(f"DELETE FROM downloads_url_chains WHERE id IN ({ph})", chain_ids)
                cur.execute(f"DELETE FROM downloads WHERE id IN ({ph})", chain_ids)
        else:
            place_ids = [r[0] for r in cur.execute(
                f"SELECT id FROM moz_places WHERE {where_url}", like_params)]
            if place_ids:
                ph = ",".join("?" * len(place_ids))
                cur.execute(f"DELETE FROM moz_historyvisits WHERE from_visit IN ({ph}) OR place_id IN ({ph})",
                            place_ids + place_ids)
                cur.execute(f"DELETE FROM moz_inputhistory WHERE place_id IN ({ph})", place_ids)
                cur.execute(f"DELETE FROM moz_annos WHERE place_id IN ({ph}) "
                            f"OR item_id IN (SELECT a.item_id FROM moz_annos a JOIN moz_places p ON "
                            f"a.place_id=p.id WHERE p.id IN ({ph}))", place_ids + place_ids)
                bookmarked = [r[0] for r in cur.execute(
                    f"SELECT fk FROM moz_bookmarks WHERE fk IN ({ph})", place_ids)]
                deletable = [pid for pid in place_ids if pid not in bookmarked]
                if deletable:
                    ph2 = ",".join("?" * len(deletable))
                    cur.execute(f"DELETE FROM moz_places WHERE id IN ({ph2})", deletable)
                deleted_rows += len(place_ids)

        conn.commit()
        conn.close()

        for suffix in ("-wal", "-shm"):
            extra = db_path + suffix
            if os.path.exists(extra):
                try:
                    os.remove(extra)
                except OSError:
                    pass
        shutil.move(tmp_db, db_path)
        return deleted_rows
    except sqlite3.Error:
        return -1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
