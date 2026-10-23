import os, sys, json, argparse

from _cli_utils import Progress, friendly_error, error_code, load_locale

# Bulk-safe roots: deletable wholesale (these are caches/temp/logs, not live data)
SAFE_ROOTS = [
    r"C:\Windows\Temp",
    r"C:\Windows\Panther",
    r"C:\Windows\Logs",
    r"C:\Windows\SoftwareDistribution\Download",
    r"C:\Windows\System32\CodeCache",
    r"C:\ProgramData\Microsoft\Windows\WER",
    r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue",
    # Delivery Optimization (DoSvc) download cache: pure re-downloadable chunks.
    # Lives under the NetworkService service profile, so Explorer refuses to
    # delete it ("needs NETWORK SERVICE permission"); script deletes fine.
    r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache",
]

# Per-user safe subdirs (relative to each C:\Users\<name>)
USER_SUBDIRS = [
    r"AppData\Local\Temp",
    r"AppData\Local\Microsoft\Edge\User Data\Default\Cache",
    r"AppData\Local\Microsoft\Edge\User Data\Default\Code Cache",
    r"AppData\Local\pip\Cache",
]

# WPS Cloud Drive client local file cache: huge, safe to delete (cloud copies remain).
# Pattern: %LOCALAPPDATA%\kingsoft\WPS Cloud Files\userdata\<WPS_UID>\filecache\cachedata
WPS_CACHE_GLOBS = [
    r"AppData\Local\kingsoft\WPS Cloud Files\userdata\*\filecache\cachedata",
]


def dir_size(path, errors=None):
    tot = 0
    prog = Progress(os.path.basename(path) or path)
    try:
        for root, _, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    tot += sz
                    prog.tick(sz)
                except OSError as e:
                    if errors is not None:
                        errors.append({"path": fp, "code": error_code(e),
                                       "hint": friendly_error(e)})
    except OSError as e:
        if errors is not None:
            errors.append({"path": path, "code": error_code(e),
                           "hint": friendly_error(e)})
    prog.done()
    return tot


def summarize_errors(errors):
    """Aggregate raw error list into novice-friendly summary."""
    if not errors:
        return {"unreadable_files": 0, "summary": "everything was readable"}
    by_code = {}
    for e in errors:
        by_code.setdefault(e["code"], 0)
        by_code[e["code"]] += 1
    hints = []
    for code, cnt in sorted(by_code.items(), key=lambda kv: -kv[1]):
        sample_hint = next(e["hint"] for e in errors if e["code"] == code)
        hints.append({"count": cnt, "hint": sample_hint})
    return {"unreadable_files": len(errors), "hints": hints}


HTML_TMPL = """<!DOCTYPE html>
<html lang="__LANG__"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
 body{font-family:'Segoe UI',system-ui,sans-serif;margin:0;background:#f5f6fa;color:#22262e}
 .wrap{max-width:900px;margin:24px auto;padding:0 16px}
 h1{font-size:22px;margin:8px 0 2px}
 .sub{color:#5b6472;font-size:13px;margin-bottom:18px}
 .cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}
 .card{flex:1;min-width:180px;background:#fff;border-radius:10px;padding:16px 18px;
       box-shadow:0 1px 4px rgba(20,24,40,.08)}
 .card .v{font-size:26px;font-weight:700;color:#1a56db}
 .card .k{font-size:12px;color:#5b6472;margin-top:2px}
 table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;
       box-shadow:0 1px 4px rgba(20,24,40,.08)}
 th{background:#eef1f7;text-align:left;font-size:13px;padding:9px 14px;color:#3b4252}
 td{padding:9px 14px;font-size:13px;border-top:1px solid #f0f2f6;word-break:break-all}
 td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
 .bar{height:8px;border-radius:4px;background:#e5e9f2;overflow:hidden;margin-top:4px}
 .bar i{display:block;height:100%;background:linear-gradient(90deg,#4c7dff,#7aa5ff)}
 .warn{background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:12px 16px;
       font-size:13px;margin:16px 0}
 .foot{color:#5b6472;font-size:12px;margin:14px 2px;line-height:1.7}
</style></head><body><div class="wrap">
<h1>__TITLE__</h1>
<div class="sub">__SUBTITLE__</div>
<div class="cards">
 <div class="card"><div class="v">__TOTAL_GB__ GB</div><div class="k">__CARD_TOTAL__</div></div>
 <div class="card"><div class="v">__NCAT__</div><div class="k">__CARD_CATS__</div></div>
 <div class="card"><div class="v">__NERR__</div><div class="k">__CARD_ERR__</div></div>
</div>
<table>
 <thead><tr><th>__TH_IDX__</th><th>__TH_PATH__</th><th style="width:120px">__TH_SIZE__</th><th style="width:220px">__TH_SHARE__</th></tr></thead>
 <tbody>
__ROWS__
 </tbody>
</table>
__WARN__
<div class="foot">__FOOT__</div>
</div></body></html>"""


def write_html(out, html_path, lang="zh"):
    L = load_locale(lang, base="locale")
    rows = []
    cats = sorted(out["categories"].items(), key=lambda kv: -kv[1])
    total = max(out["total_bytes"], 1)
    for i, (path, sz) in enumerate(cats, 1):
        pct = sz * 100.0 / total
        rows.append(
            "<tr><td>%d</td><td>%s</td><td class=num>%.2f MB</td>"
            "<td><div>%.1f%%</div><div class=bar><i style=\"width:%.1f%%\"></i></div></td></tr>"
            % (i, path, sz / 1048576.0, pct, pct))
    if out["programdata_junk"]["bytes"] > 0:
        pj = out["programdata_junk"]
        pct = pj["bytes"] * 100.0 / total
        sample = pj["sample"][0] if pj["sample"] else ""
        more = "" if pj["count"] <= 1 else (L["pd_more"] % (pj["count"] - 1))
        rows.append(
            "<tr><td>%d</td><td>%s<br><span style=\"color:#8a93a3\">%s%s</span></td>"
            "<td class=num>%.2f MB</td>"
            "<td><div>%.1f%%</div><div class=bar><i style=\"width:%.1f%%\"></i></div></td></tr>"
            % (len(cats) + 1, L["pd_label"], sample, more,
               pj["bytes"] / 1048576.0, pct, pct))
    if out["warnings"].get("unreadable_files"):
        hint_map = L.get("hint_map", {})
        h = "".join("<li>%s (x%d)</li>"
                    % (hint_map.get(str(w["code"]), w["hint"]), w["count"])
                    for w in out["warnings"].get("hints", []))
        warn_title = L["warn_title"].replace(
            "__N__", str(out["warnings"]["unreadable_files"]))
        warn = ('<div class="warn"><b>%s</b> %s<ul>%s</ul></div>'
                % (warn_title, L["warn_body"], h))
    else:
        warn = ""
    import datetime
    html = (HTML_TMPL
            .replace("__LANG__", L["html_lang"])
            .replace("__TITLE__", L["title"])
            .replace("__SUBTITLE__", L["subtitle"])
            .replace("__CARD_TOTAL__", L["card_total"])
            .replace("__CARD_CATS__", L["card_cats"])
            .replace("__CARD_ERR__", L["card_err"])
            .replace("__TH_IDX__", L["th_idx"])
            .replace("__TH_PATH__", L["th_path"])
            .replace("__TH_SIZE__", L["th_size"])
            .replace("__TH_SHARE__", L["th_share"])
            .replace("__GEN__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            .replace("__TOTAL_GB__", str(out["total_gb"]))
            .replace("__NCAT__", str(len(cats) + (1 if out["programdata_junk"]["bytes"] > 0 else 0)))
            .replace("__NERR__", str(out["warnings"].get("unreadable_files", 0)))
            .replace("__ROWS__", "\n".join(rows))
            .replace("__WARN__", warn)
            .replace("__FOOT__", L["foot"]))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(
        description="Read-only scan of C-drive safe-to-clean junk (no limits, junction-aware)")
    ap.add_argument("--html", metavar="PATH",
                    help="also write a visual HTML report to this path")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh",
                    help="report language: zh (default, SkillHub) or en (GitHub)")
    args = ap.parse_args()

    out = {"categories": {}, "programdata_junk": {"bytes": 0, "count": 0, "sample": []}}
    errors = []
    total = 0

    # 1) Bulk-safe roots
    for root in SAFE_ROOTS:
        if os.path.isdir(root):
            s = dir_size(root, errors)
            if s > 0:
                out["categories"][root] = s
                total += s

    # 2) Per-user temp / edge cache / pip cache
    sysdrive = os.environ.get("SystemDrive", "C:").rstrip("\\")
    users = sysdrive + "\\Users"
    if os.path.isdir(users):
        for u in os.listdir(users):
            base = os.path.join(users, u)
            if not os.path.isdir(base):
                continue
            for sub in USER_SUBDIRS:
                p = os.path.join(base, sub)
                if os.path.isdir(p):
                    s = dir_size(p, errors)
                    if s > 0:
                        out["categories"][p] = s
                        total += s
            # WPS Cloud Drive client local file cache
            for pattern in WPS_CACHE_GLOBS:
                import glob as _glob
                for p in _glob.glob(os.path.join(base, pattern)):
                    if os.path.isdir(p):
                        s = dir_size(p, errors)
                        if s > 0:
                            out["categories"][p] = s
                            total += s

    # 3) ProgramData junk: .dmp/.tmp/.log excluding QQPCMgr protected path
    pd = r"C:\ProgramData"
    junk_ext = (".dmp", ".tmp")
    cap = 0
    prog = Progress("ProgramData")
    if os.path.isdir(pd):
        for root, _, files in os.walk(pd):
            if "QQPCMgr" in root:  # never touch QQ PCMgr protected data
                continue
            for f in files:
                low = f.lower()
                if low.endswith(junk_ext) or (low.endswith(".log")):
                    fp = os.path.join(root, f)
                    try:
                        s = os.path.getsize(fp)
                    except OSError as e:
                        errors.append({"path": fp, "code": error_code(e),
                                       "hint": friendly_error(e)})
                        continue
                    prog.tick(s)
                    if s <= 0:
                        continue
                    out["programdata_junk"]["bytes"] += s
                    out["programdata_junk"]["count"] += 1
                    total += s
                    if cap < 50:
                        out["programdata_junk"]["sample"].append(fp)
                        cap += 1
    prog.done()

    out["warnings"] = summarize_errors(errors)
    out["total_bytes"] = total
    out["total_gb"] = round(total / 1024 / 1024 / 1024, 2)
    out["note"] = ("Above is filesystem junk only. For WinSxS run "
                   "Dism.exe /Online /Cleanup-Image /AnalyzeComponentStore; "
                   "for VSS run vssadmin list shadowstorage. "
                   "QQPCMgr *.db is kernel-protected and excluded.")
    print(json.dumps(out, ensure_ascii=False))

    if args.html:
        write_html(out, args.html, args.lang)
        try:
            sys.stderr.write("HTML report written: %s (lang=%s)\n"
                             % (os.path.abspath(args.html), args.lang))
        except Exception:
            pass


if __name__ == "__main__":
    main()
