#!/usr/bin/env python3
"""WeChat directory analyzer (read-only).

Usage:
    python -S scripts/wechat_analyze.py                    # auto-detect root
    python -S scripts/wechat_analyze.py --root <path>      # explicit root

Prints a JSON classification of each account under the root: per-category
bytes + file counts.  All paths are resolved from --root, never hard-coded.

Root auto-detection tries (in order):
    %USERPROFILE%\\Documents\\WeChat Files      (classic WeChat 3.x)
    %USERPROFILE%\\Documents\\xwechat_files    (WeChat 4.x)
If detection fails, pass --root explicitly (in WeChat: Settings -> Files
Management shows the current storage path).

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

Large accounts can hold 30-80 GB; a progress heartbeat is printed to stderr
so the scan never looks frozen (stdout stays clean JSON).
"""
import os, sys, json, argparse

from _cli_utils import Progress, friendly_error, error_code

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

AUTO_DETECT_CANDIDATES = [
    os.path.expanduser(r"~\Documents\WeChat Files"),
    os.path.expanduser(r"~\Documents\xwechat_files"),
    os.path.expanduser(r"~\Documents\WeChat Files (WPS Sync)"),
]


def detect_root():
    """Return (root, candidates_tried). A valid root has at least one
    account-like subdirectory containing WeChat category folders."""
    tried = []
    for cand in AUTO_DETECT_CANDIDATES:
        tried.append(cand)
        if os.path.isdir(cand) and os.listdir(cand):
            return cand, tried
    return None, tried


def walk_size(d):
    t = c = 0
    prog = Progress(os.path.basename(d) or d)
    errors = []
    for dp, _, fs in os.walk(d):
        for f in fs:
            fp = os.path.join(dp, f)
            try:
                sz = os.path.getsize(fp)
                t += sz
                c += 1
                prog.tick(sz)
            except OSError as e:
                errors.append(e)
    prog.done()
    if errors:
        try:
            sys.stderr.write("[hint] %d file(s) unreadable (first: %s)\n"
                             % (len(errors), friendly_error(errors[0])))
        except Exception:
            pass
    return t, c


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", required=False, default=None,
                   help="WeChat Files root directory (default: auto-detect)")
    p.add_argument("--top", type=int, default=20,
                   help="show top N largest files under FileStorage/File (0=off)")
    args = p.parse_args()

    if args.root:
        root = os.path.abspath(args.root)
        if not os.path.isdir(root):
            sys.exit("ERROR: root not found: %s\n"
                     "Hint: in WeChat open Settings -> Files Management to see "
                     "the current storage path, then pass it via --root." % root)
    else:
        root, tried = detect_root()
        if not root:
            sys.exit("ERROR: could not auto-detect a WeChat Files directory.\n"
                     "Tried:\n  " + "\n  ".join(tried) +
                     "\nHint: in WeChat open Settings -> Files Management to see "
                     "the current storage path, then pass it via --root.")

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
