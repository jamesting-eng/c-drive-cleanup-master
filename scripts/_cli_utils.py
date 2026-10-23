"""Shared CLI helpers for c-drive-cleanup-master scripts.

Provides:
  Progress       - stderr heartbeat so long scans never look frozen
  friendly_error - translate OSError/WinError into plain-English hints
  load_locale    - load a UI-string resource file (bilingual report support)

Import as:  from _cli_utils import Progress, friendly_error, load_locale
(script dir is auto-added to sys.path when run via `python -S scripts/xxx.py`)

Pure ASCII. Progress goes to stderr so stdout stays clean JSON.
UI text for reports lives in locale_*.json / wechat_locale_*.json so the
scripts stay ASCII while reports can be localized (SkillHub zh / GitHub en).
"""
import os
import sys
import time
import json


class Progress:
    """Heartbeat reporter. Call .tick() per file; prints to stderr at most
    once every `interval` seconds (or every `every_n` files)."""

    def __init__(self, label, interval=5.0, every_n=20000, stream=None):
        self.label = label
        self.interval = interval
        self.every_n = every_n
        self.stream = stream or sys.stderr
        self.n = 0
        self.bytes = 0
        self.t0 = time.time()
        self._last = time.time()

    def tick(self, size=0):
        self.n += 1
        self.bytes += size
        now = time.time()
        if now - self._last >= self.interval or self.n % self.every_n == 0:
            self._last = now
            self._emit()

    def _emit(self):
        mb = self.bytes / 1048576.0
        el = int(time.time() - self.t0)
        try:
            self.stream.write("[%s] %d files, %.1f MB seen, %ds elapsed...\n"
                              % (self.label, self.n, mb, el))
            self.stream.flush()
        except Exception:
            pass

    def done(self):
        el = int(time.time() - self.t0)
        try:
            self.stream.write("[%s] done: %d files, %.1f MB, %ds\n"
                              % (self.label, self.n, self.bytes / 1048576.0, el))
            self.stream.flush()
        except Exception:
            pass


# WinError / errno -> plain-English hint (what happened + what to do next)
_HINTS = {
    5: ("Access denied. The file is locked by a running program, an "
        "antivirus self-protection driver, or system protection. "
        "Fix: close the related app and retry, or use restart_delete.py "
        "to schedule deletion at next reboot. Do NOT force-delete."),
    32: ("The file is in use by another program. "
         "Fix: close the app holding it (WeChat / WPS / browser etc.) "
         "and retry, or schedule a restart-delete."),
    2: ("File not found. It was probably already removed by another "
        "cleanup pass. Safe to ignore."),
    3: ("Path not found. The directory is gone already. Safe to ignore."),
    124: ("Path too long. Fix: retry with the \\\\?\\ long-path prefix."),
    206: ("Path too long. Fix: retry with the \\\\?\\ long-path prefix."),
    13: ("Permission denied (read). Usually antivirus protection. "
         "Fix: skip this item; do not fight it."),
}


def friendly_error(e):
    """Return a short plain-English hint for an OSError-like exception."""
    code = getattr(e, "winerror", None)
    if code is None:
        code = getattr(e, "errno", None)
    if code is None:
        return str(e)
    h = _HINTS.get(code)
    if h:
        return "WinError %d: %s" % (code, h)
    return str(e)


def error_code(e):
    """Best-effort numeric error code for grouping in reports."""
    code = getattr(e, "winerror", None)
    if code is None:
        code = getattr(e, "errno", None)
    return code


def load_locale(lang, base="locale"):
    """Load a report UI-string resource.

    Resolves `<base>_<lang>.json` next to this module. Falls back to the
    English resource so an untranslated key never crashes a run.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    primary = os.path.join(here, "%s_%s.json" % (base, lang))
    fallback = os.path.join(here, "%s_en.json" % base)
    target = primary if os.path.isfile(primary) else fallback
    try:
        with open(target, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        with open(fallback, encoding="utf-8") as f:
            return json.load(f)
