#!/usr/bin/env python3
"""WeChat directory analyzer (read-only).

Usage:
    python -S scripts/wechat_analyze.py --root <path-to-WeChat-Files>

Prints a JSON classification of each account under the root: per-category
bytes + file counts.  All paths are resolved from --root, never hard-coded.

Categories (by directory name under each <account>):
    BackupFiles          - WeChat backup archives (may contain many redundant copies)
    FileStorage/File     - received documents (the largest "personal" bucket)
    FileStorage/MsgAttach- message attachments (images/videos/files)
    FileStorage/Cache    - thumbnail cache (usually tiny after app cleanup)
    FileStorage/Video    - downloaded videos
    FileStorage/Sns      - Moments attachments (often empty)
    Msg                  - chat DB files (NEVER touch)
    Other                - everything else

The script never deletes anything.  Use the produced JSON to decide what to
target with wechat_dedup_plan.py (for File) or wechat_backup_inspect.py
(for BackupFiles).
"""
import os, sys, json, argparse

CATEGORIES = [
    "BackupFiles",
    "FileStorage/File",
    "FileStorage/MsgAttach",
    "FileStorage/Cache",
    "FileStorage/Video",
    "FileStorage/Sns",
    "Msg",
    "Log",
    "All Users", "Applet", "WMPF",
]

PROTECT = {"Msg"}


def walk_size(d):
    t = c = 0
    for dp, _, fs in os.walk(d):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(dp, f))
                c += 1
            except OSError:
                pass
    return t, c


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", required=True, help="WeChat Files root directory")
    p.add_argument("--top", type=int, default=20,
                   help="show top N largest files under FileStorage/File (0=off)")
    args = p.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit("ERROR: root not found: " + root)

    accounts = {}
    for name in sorted(os.listdir(root)):
        ap = os.path.join(root, name)
        if not os.path.isdir(ap):
            continue
        cats = {}
        for cat in CATEGORIES:
            cp = os.path.join(ap, cat)
            if os.path.isdir(cp):
                t, c = walk_size(cp)
                cats[cat] = {"bytes": t, "files": c, "protected": cat in PROTECT}
        accounts[name] = cats

    top = []
    if args.top > 0:
        big = []
        for name in accounts:
            fs_dir = os.path.join(root, name, "FileStorage", "File")
            if os.path.isdir(fs_dir):
                for dp, _, fs in os.walk(fs_dir):
                    for f in fs:
                        fp = os.path.join(dp, f)
                        try:
                            big.append((os.path.getsize(fp), fp))
                        except OSError:
                            pass
        big.sort(reverse=True)
        top = [{"bytes": b, "path": p} for b, p in big[:args.top]]

    out = {
        "root": root,
        "accounts": accounts,
        "top_files_under_FileStorage_File": top,
        "warning": ("Msg/* are chat DBs - do not delete. BackupFiles may "
                    "contain redundant copies - run wechat_backup_inspect.py."),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()