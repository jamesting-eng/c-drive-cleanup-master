import os, sys, json

# Bulk-safe roots: deletable wholesale (these are caches/temp/logs, not live data)
SAFE_ROOTS = [
    r"C:\Windows\Temp",
    r"C:\Windows\Panther",
    r"C:\Windows\Logs",
    r"C:\Windows\SoftwareDistribution\Download",
    r"C:\Windows\System32\CodeCache",
    r"C:\ProgramData\Microsoft\Windows\WER",
    r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue",
]

# Per-user safe subdirs (relative to each C:\Users\<name>)
USER_SUBDIRS = [
    r"AppData\Local\Temp",
    r"AppData\Local\Microsoft\Edge\User Data\Default\Cache",
    r"AppData\Local\Microsoft\Edge\User Data\Default\Code Cache",
    r"AppData\Local\pip\Cache",
]


def dir_size(path):
    tot = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    tot += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return tot


def main():
    out = {"categories": {}, "programdata_junk": {"bytes": 0, "count": 0, "sample": []}}
    total = 0

    # 1) Bulk-safe roots
    for root in SAFE_ROOTS:
        if os.path.isdir(root):
            s = dir_size(root)
            if s > 0:
                out["categories"][root] = s
                total += s

    # 2) Per-user temp / edge cache / pip cache
    users = os.path.join(os.environ.get("SystemDrive", "C:"), "Users")
    if os.path.isdir(users):
        for u in os.listdir(users):
            base = os.path.join(users, u)
            if not os.path.isdir(base):
                continue
            for sub in USER_SUBDIRS:
                p = os.path.join(base, sub)
                if os.path.isdir(p):
                    s = dir_size(p)
                    if s > 0:
                        out["categories"][p] = s
                        total += s

    # 3) ProgramData junk: .dmp/.tmp/.log excluding QQPCMgr protected path
    pd = r"C:\ProgramData"
    junk_ext = (".dmp", ".tmp")
    cap = 0
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
                    except OSError:
                        continue
                    if s <= 0:
                        continue
                    out["programdata_junk"]["bytes"] += s
                    out["programdata_junk"]["count"] += 1
                    total += s
                    if cap < 50:
                        out["programdata_junk"]["sample"].append(fp)
                        cap += 1

    out["total_bytes"] = total
    out["total_gb"] = round(total / 1024 / 1024 / 1024, 2)
    out["note"] = ("Above is filesystem junk only. For WinSxS run "
                   "Dism.exe /Online /Cleanup-Image /AnalyzeComponentStore; "
                   "for VSS run vssadmin list shadowstorage. "
                   "QQPCMgr *.db is kernel-protected and excluded.")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
