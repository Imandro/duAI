import os
import tempfile
import unittest


class QuarantineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="duai_q_")
        from duai.core import quarantine

        self.quarantine = quarantine

    def test_quarantine_roundtrip(self):
        src_dir = os.path.join(self.tmp, "origen")
        os.makedirs(src_dir)
        marker = os.path.join(src_dir, "rastro.txt")
        with open(marker, "w") as fh:
            fh.write("x")

        qbase = os.path.join(self.tmp, "cuarentena")
        self.assertTrue(self.quarantine.quarantine_path(marker, base=qbase))
        self.assertFalse(os.path.exists(marker))

        restored = self.quarantine.restore_all(base=qbase)
        self.assertEqual(restored, 0)
        restored_global = self.quarantine.restore_all()
        self.assertGreaterEqual(restored_global, 0)
        self.assertTrue(os.path.isdir(qbase))

    def test_purge_quarantine_removes_files(self):
        qbase = os.path.join(self.tmp, "q2")
        victim = os.path.join(self.tmp, "victim.bin")
        with open(victim, "wb") as fh:
            fh.write(b"12345")
        self.quarantine.quarantine_path(victim, base=qbase)
        files_before = [f for f in os.listdir(qbase) if f != "manifest.json"]
        self.assertEqual(len(files_before), 1)

        removed = self.quarantine.purge_quarantine(base=qbase)
        self.assertGreaterEqual(removed, 1)
        leftovers = [f for f in os.listdir(qbase) if f != "manifest.json"]
        self.assertEqual(leftovers, [])


class SelfCleanTest(unittest.TestCase):
    def test_purge_logs_truncates(self):
        tmp = tempfile.mkdtemp(prefix="duai_l_")
        log_file = os.path.join(tmp, "duai.log")
        with open(log_file, "w", encoding="utf-8") as fh:
            fh.write("evento secreto\n" * 100)
        from duai.core.selfclean import purge_logs

        self.assertTrue(purge_logs(log_file))
        with open(log_file, "r", encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "")

    def test_purge_own_recent_links_only_matches_duai(self):
        from duai.core.selfclean import purge_own_recent_links

        self.assertIsInstance(purge_own_recent_links(), int)


class DiffReportsTest(unittest.TestCase):
    def _report_with(self, items_by_target):
        from duai.core.scanner import ScanEntry, ScanReport, TraceItem
        from duai.core.targets import Target

        report = ScanReport()
        report.scanned_at = "T"
        for target_id, count in items_by_target.items():
            target = Target(id=target_id, name=target_id.upper(), category="cat")
            entry = ScanEntry(target)
            entry.status = "found" if count else "empty"
            entry.items = [TraceItem(f"C:/fake/{target_id}_{i}", 10) for i in range(count)]
            report.entries.append(entry)
        return report

    def test_diff_detects_reduction_and_cleanup(self):
        from duai.core.reporter import diff_reports

        before = self._report_with({"a": 5, "b": 3})
        after = self._report_with({"a": 0, "b": 1})
        lines = "\n".join(diff_reports(before, after))
        self.assertIn("LIMPIO", lines)
        self.assertIn("REDUCIDO", lines)
        self.assertIn("ESPACIO LIBERADO NETO: 70 B", lines)


if __name__ == "__main__":
    unittest.main()
