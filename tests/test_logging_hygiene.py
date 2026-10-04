"""Guards against print()-logging and PII in worker logs creeping back in."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_tasks_use_logging_not_print():
    assert "print(" not in (ROOT / "workers/tasks.py").read_text()


def test_bots_only_print_interactive_debug_hints():
    prints = [
        line.strip()
        for line in (ROOT / "workers/playwright_bot.py").read_text().splitlines()
        if "print(" in line
    ]
    assert all("[debug]" in p for p in prints), prints


def test_ocr_values_and_qr_contents_not_logged_above_debug():
    src = (ROOT / "workers/tasks.py").read_text()
    for m in re.finditer(r"logger\.(info|warning|error)\((.*)", src):
        assert "amount" not in m.group(2) and "qr_raw" not in m.group(2), m.group(0)
