import subprocess, sys, re, json


def diskfree(drive):
    d = drive.rstrip("\\").rstrip(":") + ":"
    r = subprocess.run(["fsutil", "volume", "diskfree", d], capture_output=True)
    txt = r.stdout.decode("gbk", "ignore") + r.stderr.decode("gbk", "ignore")
    m = re.search(r"\u603b\u53ef\u7528\u5b57\u8282\u6570\s*:\s*([\d,]+)", txt)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def main():
    drive = sys.argv[1] if len(sys.argv) > 1 else "C:"
    readings = []
    for _ in range(3):
        f = diskfree(drive)
        if f is not None:
            readings.append(f)
    if not readings:
        print(json.dumps({"error": "fsutil failed"}))
        return
    avg = sum(readings) // len(readings)
    print(json.dumps({
        "drive": drive,
        "free_bytes": avg,
        "free_gb": round(avg / 1024 / 1024 / 1024, 2),
        "readings_bytes": readings,
        "stable": (max(readings) - min(readings)) < 500 * 1024 * 1024,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
