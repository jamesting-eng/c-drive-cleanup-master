#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Move files or directories to Windows Recycle Bin.
Never permanently deletes. Default dry-run; use --confirm to actually move.
Requires send2trash (pip install send2trash) or falls back to ctypes SHFileOperationW.
All output is ASCII-only; paths are printed as-is.
"""
import argparse
import ctypes
import os
import sys
from ctypes import wintypes

try:
    from send2trash import send2trash
except Exception:
    send2trash = None


FO_DELETE = 0x0003
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_SILENT = 0x0004
FOF_NOERRORUI = 0x0400


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.UINT),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def move_with_shfileoperation(path):
    """Fallback using SHFileOperationW (Vista+)."""
    full = os.path.abspath(path)
    src = full + '\x00\x00'
    shfo = SHFILEOPSTRUCTW()
    shfo.hwnd = None
    shfo.wFunc = FO_DELETE
    shfo.pFrom = src
    shfo.pTo = None
    shfo.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    shfo.fAnyOperationsAborted = False
    shfo.hNameMappings = None
    shfo.lpszProgressTitle = None

    shell32 = ctypes.windll.shell32
    shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell32.SHFileOperationW.restype = wintypes.INT
    ret = shell32.SHFileOperationW(ctypes.byref(shfo))
    if ret == 0 and not shfo.fAnyOperationsAborted:
        return True, None
    return False, f"SHFileOperationW returned {ret}, aborted={shfo.fAnyOperationsAborted}"


def move_to_recycle_bin(path):
    """Move path to Recycle Bin. Returns (ok, error_msg)."""
    if not os.path.exists(path):
        return False, "not found"
    if send2trash is not None:
        try:
            send2trash(path)
            return True, None
        except Exception as e:
            return move_with_shfileoperation(path)
    return move_with_shfileoperation(path)


def du(path):
    total = 0
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    for dp, dn, fn in os.walk(path):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def main():
    parser = argparse.ArgumentParser(description="Move paths to Recycle Bin (never permanent delete)")
    parser.add_argument("paths", nargs="+", help="files or directories to move")
    parser.add_argument("--confirm", action="store_true", help="actually move; default is dry-run")
    args = parser.parse_args()

    total = 0
    plan = []
    for p in args.paths:
        sz = du(p)
        total += sz
        plan.append((p, sz))
        print(f"[PLAN] {p}: {sz/1024**2:.2f} MB")
    print(f"\nTotal planned: {total/1024**2:.2f} MB")

    if not args.confirm:
        print("\nDRY-RUN: use --confirm to move to Recycle Bin.")
        return

    moved = 0
    failed = 0
    for p, sz in plan:
        ok, err = move_to_recycle_bin(p)
        if ok:
            moved += sz
            print(f"[MOVED] {p}")
        else:
            failed += 1
            print(f"[FAIL]  {p}: {err}")

    print(f"\nMoved estimate: {moved/1024**2:.2f} MB")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
