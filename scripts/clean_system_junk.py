#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan common C-drive system/software junk and move it to Recycle Bin.
Default dry-run; use --confirm to actually move files.
Identifies junctions (0xA0000003) and skips them to avoid cross-disk miscounts.
All deletions go through Recycle Bin; locked items are reported, not forced.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from delete_to_recyclebin import move_to_recycle_bin, du


# (name, mode, paths)
# mode = 'whole'  -> move the directory itself
# mode = 'contents' -> move entries inside but keep the root directory
TARGETS = [
    ("Windows Event Logs", "contents", [r"C:\Windows\System32\winevt\Logs"]),
    ("User Temp", "contents", [os.path.expanduser(r"~\AppData\Local\Temp")]),
    ("Recent Items", "whole", [os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Recent")]),
    ("Windows Temp", "contents", [r"C:\Windows\Temp"]),
    ("Edge/IE Cache", "whole", [os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\INetCache")]),
    ("ThumbCache", "whole", [os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Explorer")]),
    ("Notifications", "whole", [os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Notifications")]),
    ("Windows Logs", "contents", [r"C:\Windows\Logs"]),
    ("Prefetch", "contents", [r"C:\Windows\Prefetch"]),
]

PROTECTED_ROOTS = {
    os.path.expanduser(r"~\Documents"),
    os.path.expanduser(r"~\Desktop"),
    os.path.expanduser(r"~\Downloads"),
    os.path.expanduser(r"~\Pictures"),
    os.path.expanduser(r"~\Videos"),
    os.path.expanduser(r"~\Music"),
}


def is_junction(path):
    try:
        return os.path.isdir(path) and getattr(os.lstat(path), "st_reparse_tag", 0) == 0xA0000003
    except OSError:
        return False


def is_safe_path(path):
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return False, "not found"
    if not abs_path.upper().startswith("C:\\"):
        return False, "not on C drive"
    if is_junction(abs_path):
        return False, "is a junction (target not on C)"
    for pr in PROTECTED_ROOTS:
        if abs_path.lower().startswith(os.path.abspath(pr).lower() + os.sep):
            return False, f"under protected root {pr}"
    return True, ""


def main():
    parser = argparse.ArgumentParser(description="Scan and move C-drive system junk to Recycle Bin")
    parser.add_argument("--confirm", action="store_true", help="actually move files to Recycle Bin")
    args = parser.parse_args()

    total_size = 0
    plan = []
    for name, mode, paths in TARGETS:
        for p in paths:
            safe, reason = is_safe_path(p)
            if not safe:
                print(f"[SKIP] {name}: {p} ({reason})")
                continue
            items = []
            if mode == "whole":
                sz = du(p)
                if sz == 0:
                    print(f"[SKIP] {name}: {p} (empty or unreadable)")
                    continue
                items = [p]
                total_size += sz
                print(f"[PLAN] {name}: {p} = {sz/1024**2:.2f} MB (whole dir)")
            else:
                try:
                    entries = os.listdir(p)
                except Exception as e:
                    print(f"[SKIP] {name}: {p} (cannot list: {e})")
                    continue
                if not entries:
                    print(f"[SKIP] {name}: {p} (empty)")
                    continue
                sz = 0
                for e in entries:
                    full = os.path.join(p, e)
                    esz = du(full)
                    if esz > 0:
                        items.append(full)
                        sz += esz
                if not items:
                    print(f"[SKIP] {name}: {p} (no movable contents)")
                    continue
                total_size += sz
                print(f"[PLAN] {name}: {p} -> {len(items)} entries = {sz/1024**2:.2f} MB (contents only)")
            plan.append((name, p, mode, items, sz))

    print(f"\nTotal planned: {total_size/1024**2:.2f} MB ({total_size/1024**3:.3f} GB)")

    if not args.confirm:
        print("\nDRY-RUN: use --confirm to send to Recycle Bin.")
        return

    if not plan:
        print("Nothing to clean.")
        return

    print("\nMoving to Recycle Bin...")
    moved = 0
    failed = []
    for name, root_path, mode, items, sz in plan:
        for item in items:
            try:
                ok, err = move_to_recycle_bin(item)
                if ok:
                    moved += du(item) if os.path.exists(item) else sz / len(items)
                    print(f"[MOVED] {name}: {item}")
                else:
                    failed.append((name, item, err))
                    print(f"[FAIL]  {name}: {item} -> {err}")
            except Exception as e:
                failed.append((name, item, str(e)))
                print(f"[FAIL]  {name}: {item} -> {e}")

    print(f"\nMoved estimate: {moved/1024**2:.2f} MB")
    if failed:
        print(f"Failed: {len(failed)} items")
        for name, item, err in failed:
            print(f"  - {name}: {item} -> {err}")
    else:
        print("No failures.")


if __name__ == "__main__":
    main()
