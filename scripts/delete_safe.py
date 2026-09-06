import os, sys, json, shutil, argparse

# ---- Allowlist (safe to delete). Everything else is rejected. ----
SAFE_DIR_PREFIXES = [
    r"c:\windows\temp",
    r"c:\windows\panther",
    r"c:\windows\logs",
    r"c:\windows\softwaredistribution\download",
    r"c:\windows\system32\codecache",
    r"c:\programdata\microsoft\windows\wer",
]
JUNK_EXT = (".dmp", ".tmp", ".log")


def norm(p):
    return os.path.abspath(p).lower().replace("/", "\\")


def is_allowed(path):
    n = norm(path)
    # whole-dir safe roots
    for pre in SAFE_DIR_PREFIXES:
        if n == pre or n.startswith(pre + "\\"):
            return True
    # per-user safe subdirs
    if n.startswith(r"c:\users\\"):
        for sub in [
            r"\appdata\local\temp",
            r"\appdata\local\microsoft\edge\user data\default\cache",
            r"\appdata\local\microsoft\edge\user data\default\code cache",
            r"\appdata\local\pip\cache",
        ]:
            if n == r"c:\users\\" + sub or n.startswith(r"c:\users\\" + sub + "\\"):
                return True
    # ProgramData junk files only (never QQPCMgr, never whole dirs)
    if n.startswith(r"c:\programdata\\") and "qqpcmgr" not in n:
        if os.path.isfile(path) and n.endswith(JUNK_EXT):
            return True
    return False


def schedule_reboot_delete(path):
    """Try to queue a delete-at-reboot via PendingFileRenameOperations."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager",
            0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            cur, _ = winreg.QueryValueEx(key, "PendingFileRenameOperations")
            if isinstance(cur, str):
                cur = [cur]
        except FileNotFoundError:
            cur = []
        src = "\\??\\" + os.path.abspath(path)
        cur = list(cur) + [src, ""]
        winreg.SetValueEx(key, "PendingFileRenameOperations", 0,
                          winreg.REG_MULTI_SZ, cur)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def delete_one(path, confirm):
    if not is_allowed(path):
        return (path, "SKIPPED", "not in allowlist")
    if not os.path.exists(path) and not os.path.islink(path):
        return (path, "SKIPPED", "not found")
    if not confirm:
        return (path, "DRYRUN", "would delete")
    try:
        if os.path.islink(path) or os.path.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path)
        return (path, "DELETED", "")
    except (PermissionError, OSError) as e:
        # locked -> try queue reboot delete
        if schedule_reboot_delete(path):
            return (path, "QUEUED_REBOOT", str(e))
        return (path, "LOCKED", str(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True, help="JSON file with {\"paths\":[...]}")
    ap.add_argument("--confirm", action="store_true", help="actually delete (default dry-run)")
    args = ap.parse_args()

    with open(args.targets, "r", encoding="utf-8") as f:
        data = json.load(f)
    paths = data.get("paths", [])

    results = []
    for p in paths:
        results.append(delete_one(p, args.confirm))

    deleted = sum(1 for r in results if r[1] == "DELETED")
    queued = sum(1 for r in results if r[1] == "QUEUED_REBOOT")
    skipped = sum(1 for r in results if r[1] in ("SKIPPED", "LOCKED"))
    print(json.dumps({
        "confirm": args.confirm,
        "total": len(results),
        "deleted": deleted,
        "queued_reboot": queued,
        "skipped_or_locked": skipped,
        "details": [{"path": r[0], "status": r[1], "info": r[2]} for r in results],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
