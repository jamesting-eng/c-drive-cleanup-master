#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan common C-drive system/software junk and route each item to the
appropriate deletion method based on the safety gate:

  * computer-housekeeper-class system junk -> restart-delete (optional,
    needs --allow-restart-delete and admin rights)
  * skill deep-governance targets           -> Recycle Bin

Default dry-run; use --confirm to actually act.
Identifies junctions (0xA0000003) and skips them to avoid cross-disk miscounts.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from delete_to_recyclebin import move_to_recycle_bin, du
from restart_delete import schedule_deletes, is_admin


# (name, mode, method, paths)
# mode  = 'whole'    -> move/delete the directory itself
#       = 'contents' -> move/delete entries inside but keep the root directory
# method = 'recycle'        -> must go through Recycle Bin (deep governance)
#        = 'restart_delete' -> system-managed junk that OS recreates (optional)
TARGETS = [
    # --- computer-housekeeper-class system junk (safe for restart-delete) ---
    ("Windows Event Logs", "contents", "restart_delete", [r"C:\Windows\System32\winevt\Logs"]),
    ("Windows Logs", "contents", "restart_delete", [r"C:\Windows\Logs"]),
    ("Prefetch", "contents", "restart_delete", [r"C:\Windows\Prefetch"]),

    # --- skill deep-governance targets (must go through Recycle Bin) ---
    ("User Temp", "contents", "recycle", [os.path.expanduser(r"~\AppData\Local\Temp")]),
    ("Recent Items", "whole", "recycle", [os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Recent")]),
    ("Windows Temp", "contents", "recycle", [r"C:\Windows\Temp"]),
    ("Edge/IE Cache", "whole", "recycle", [os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\INetCache")]),
    ("ThumbCache", "whole", "recycle", [os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Explorer")]),
    ("Notifications", "whole", "recycle", [os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Notifications")]),
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


def collect_plan():
    total_size = 0
    plan = []
    for name, mode, method, paths in TARGETS:
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
                print(f"[PLAN] {name}: {p} = {sz/1024**2:.2f} MB (whole dir, {method})")
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
                print(f"[PLAN] {name}: {p} -> {len(items)} entries = {sz/1024**2:.2f} MB (contents only, {method})")
            plan.append((name, p, mode, method, items, sz))
    return plan, total_size


def main():
    parser = argparse.ArgumentParser(
        description="Scan and clean C-drive system junk via Recycle Bin or restart-delete")
    parser.add_argument("--confirm", action="store_true",
                        help="actually act; default is dry-run")
    parser.add_argument("--allow-restart-delete", action="store_true",
                        help="allow restart-delete for system-managed junk (needs admin)")
    args = parser.parse_args()

    plan, total_size = collect_plan()
    print(f"\nTotal planned: {total_size/1024**2:.2f} MB ({total_size/1024**3:.3f} GB)")

    recycle_items = [(n, it, s) for n, _, _, m, its, s in plan for it in its if m == "recycle"]
    restart_items = [(n, it, s) for n, _, _, m, its, s in plan for it in its if m == "restart_delete"]

    if restart_items:
        print(f"\n[SAFETY GATE] {len(restart_items)} item(s) are system-managed junk eligible for restart-delete.")
        if not args.allow_restart_delete:
            print("              Pass --allow-restart-delete to schedule them for next reboot.")
        elif not is_admin():
            print("[FAIL] --allow-restart-delete requires admin rights.")
            sys.exit(1)

    if not args.confirm:
        print("\nDRY-RUN: use --confirm to execute.")
        return

    if not plan:
        print("Nothing to clean.")
        return

    # Execute Recycle Bin items
    if recycle_items:
        print("\nMoving to Recycle Bin...")
        moved = 0
        failed = []
        for name, item, sz in recycle_items:
            try:
                ok, err = move_to_recycle_bin(item)
                if ok:
                    moved += du(item) if os.path.exists(item) else sz
                    print(f"[MOVED] {name}: {item}")
                else:
                    failed.append((name, item, err))
                    print(f"[FAIL]  {name}: {item} -> {err}")
            except Exception as e:
                failed.append((name, item, str(e)))
                print(f"[FAIL]  {name}: {item} -> {e}")
        print(f"\nRecycle Bin moved estimate: {moved/1024**2:.2f} MB")
        if failed:
            print(f"Recycle Bin failures: {len(failed)}")
            for name, item, err in failed:
                print(f"  - {name}: {item} -> {err}")

    # Execute restart-delete items
    if restart_items and args.allow_restart_delete:
        print("\nScheduling restart-delete...")
        paths = [item for _, item, _ in restart_items]
        ok, err = schedule_deletes(paths)
        if ok:
            total = sum(s for _, _, s in restart_items)
            print(f"[SCHEDULED] {len(paths)} item(s) for deletion at next reboot ({total/1024**2:.2f} MB).")
        else:
            print(f"[FAIL] restart-delete scheduling failed: {err}")


if __name__ == "__main__":
    main()
