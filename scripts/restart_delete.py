#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schedule file deletions for next reboot via PendingFileRenameOperations.
Requires admin rights. Never deletes immediately; Windows performs the
actual delete during the next Session Manager phase (before logon).

This is the ONLY permitted bypass of the Recycle Bin, and only for
computer-housekeeper-class system junk (Windows event logs, Prefetch,
CBS/DISM logs, etc.) that the OS recreates automatically.
"""
import argparse
import ctypes
import os
import sys

try:
    import winreg
except ImportError:
    winreg = None


REG_PATH = r"SYSTEM\CurrentControlSet\Control\Session Manager"
REG_VALUE = "PendingFileRenameOperations"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def list_pending():
    """Return list of source paths currently scheduled for delete/rename."""
    if winreg is None:
        return []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_READ) as key:
            data, _ = winreg.QueryValueEx(key, REG_VALUE)
            if not data:
                return []
            # data is a list of strings in source/destination pairs
            return [data[i] for i in range(0, len(data), 2)]
    except FileNotFoundError:
        return []
    except OSError as e:
        print(f"[WARN] cannot read pending list: {e}", file=sys.stderr)
        return []


def schedule_deletes(paths):
    """Append paths to PendingFileRenameOperations as delete operations."""
    if winreg is None:
        return False, "winreg not available"
    if not is_admin():
        return False, "admin rights required"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                existing, _ = winreg.QueryValueEx(key, REG_VALUE)
                existing = list(existing) if existing else []
            except FileNotFoundError:
                existing = []

            new_pairs = []
            for p in paths:
                src = os.path.abspath(p)
                if not os.path.exists(src):
                    return False, f"not found: {src}"
                # NT path prefix used by Session Manager
                new_pairs.append("\\??\\" + src)
                new_pairs.append("")  # empty destination == delete

            winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_MULTI_SZ,
                              existing + new_pairs)
            return True, None
    except OSError as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Schedule paths for deletion at next reboot")
    parser.add_argument("paths", nargs="*", help="files or directories to schedule")
    parser.add_argument("--confirm", action="store_true",
                        help="actually schedule; default is dry-run")
    parser.add_argument("--list", action="store_true",
                        help="list currently pending operations")
    args = parser.parse_args()

    if args.list:
        pending = list_pending()
        if pending:
            print(f"Pending operations ({len(pending)}):")
            for p in pending:
                print(f"  {p}")
        else:
            print("No pending operations.")
        return

    if not args.paths:
        parser.print_help()
        return

    if not is_admin():
        print("[FAIL] admin rights required for PendingFileRenameOperations")
        sys.exit(1)

    total = 0
    for p in args.paths:
        sz = 0
        if os.path.isfile(p):
            try:
                sz = os.path.getsize(p)
            except OSError:
                pass
        elif os.path.isdir(p):
            for dp, _, fns in os.walk(p):
                for fn in fns:
                    try:
                        sz += os.path.getsize(os.path.join(dp, fn))
                    except OSError:
                        pass
        total += sz
        print(f"[PLAN] {p}: {sz/1024**2:.2f} MB -> restart-delete")

    print(f"\nTotal planned: {total/1024**2:.2f} MB")

    if not args.confirm:
        print("\nDRY-RUN: use --confirm to schedule for next reboot.")
        return

    ok, err = schedule_deletes(args.paths)
    if ok:
        print(f"[SCHEDULED] {len(args.paths)} item(s) for deletion at next reboot.")
    else:
        print(f"[FAIL] {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
