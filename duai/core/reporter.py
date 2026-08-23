import csv

from ..utils.paths import fmt_bytes


def diff_reports(before, after):
    lines = []
    before_map = {e.target.id: e for e in before.entries}
    after_map = {e.target.id: e for e in after.entries}
    changed = 0
    for target_id, entry_before in before_map.items():
        entry_after = after_map.get(target_id)
        if entry_after is None:
            continue
        delta_items = len(entry_before.items) - len(entry_after.items)
        delta_bytes = entry_before.total_bytes - entry_after.total_bytes
        if entry_before.status == "found" and entry_after.status != "found":
            lines.append(f"LIMPIO  · {entry_before.target.name}")
            changed += 1
        elif delta_items != 0 or delta_bytes != 0:
            sign_items = f"{delta_items:+d}" if delta_items else "-"
            lines.append(
                f"REDUCIDO · {entry_before.target.name} · {sign_items} elementos · "
                f"{fmt_bytes(abs(delta_bytes))}"
            )
            changed += 1
    total_delta = before.total_bytes - after.total_bytes
    lines.append("")
    lines.append(f"OBJETIVOS MEJORADOS: {changed}")
    lines.append(f"ESPACIO LIBERADO NETO: {fmt_bytes(total_delta)}")
    return lines


def save_report_txt(report, out_path, title="duAI - Reporte de escaneo"):
    lines = [title, "=" * len(title), f"Fecha: {report.scanned_at}", ""]
    for entry in report.entries:
        size = fmt_bytes(entry.total_bytes) if entry.items else "-"
        lines.append(
            f"[{entry.status_label}] {entry.target.category} | {entry.target.name} | "
            f"{len(entry.items)} elementos | {size}"
        )
        if entry.detail:
            lines.append(f"    {entry.detail}")
        for item in entry.items[:15]:
            lines.append(f"    {item.path}")
        if len(entry.items) > 15:
            lines.append(f"    ... y {len(entry.items) - 15} rutas mas")
    lines.append("")
    lines.append(
        f"TOTAL: {len(report.found_entries)} objetivos con rastros, "
        f"{fmt_bytes(report.total_bytes)}"
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return out_path


def save_report_csv(report, out_path):
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["categoria", "objetivo", "estado", "elementos", "bytes", "detalle"])
        for entry in report.entries:
            writer.writerow([
                entry.target.category,
                entry.target.name,
                entry.status_label,
                len(entry.items),
                entry.total_bytes,
                entry.detail,
            ])
    return out_path
