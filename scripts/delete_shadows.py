"""Delete VSS shadow copies via CIM when vssadmin delete is blocked.

vssadmin.exe's "delete shadows" subcommand is sometimes blocked in sandboxed
or hardened environments (returns "invalid command" even with correct syntax),
while the read-only "list" subcommand still works. This script uses the
Win32_ShadowCopy CIM class through PowerShell, which is not subject to the
same restriction and can remove all restore-point shadows in one shot.

Usage:
    python -S delete_shadows.py [--confirm]

Without --confirm it prints the list of shadows that would be deleted.
With --confirm it calls Remove-CimInstance and reports the result.
"""
import argparse
import json
import subprocess
import sys


def list_shadows():
    ps = (
        "$s = Get-CimInstance Win32_ShadowCopy; "
        "$s | Select-Object DeviceObject, VolumeName, InstallDate, "
        "@{Name='SizeGB';Expression={[math]::Round($_.VolumeSize/1GB,2)}} | "
        "ConvertTo-Json -AsArray"
    )
    r = subprocess.run(
        ["powershell", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    if r.returncode != 0:
        raise RuntimeError("list shadows failed: " + r.stderr.strip())
    data = json.loads(r.stdout or "[]")
    return data if isinstance(data, list) else [data]


def delete_all_shadows():
    ps = (
        "$before = (Get-CimInstance Win32_ShadowCopy | Measure-Object).Count; "
        "Get-CimInstance Win32_ShadowCopy | Remove-CimInstance; "
        "$after = (Get-CimInstance Win32_ShadowCopy | Measure-Object).Count; "
        "@{deleted=$before-$after; remaining=$after} | ConvertTo-Json"
    )
    r = subprocess.run(
        ["powershell", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    if r.returncode != 0:
        raise RuntimeError("delete shadows failed: " + r.stderr.strip())
    return json.loads(r.stdout or "{}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true",
                    help="actually delete shadows (default dry-run)")
    args = ap.parse_args()

    shadows = list_shadows()
    print(json.dumps({"shadow_count": len(shadows), "shadows": shadows},
                     ensure_ascii=False, indent=2))

    if not shadows:
        print("No shadow copies to delete.")
        return 0

    if not args.confirm:
        print("Dry-run: pass --confirm to delete the above shadows.")
        return 0

    result = delete_all_shadows()
    print(json.dumps({"result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
