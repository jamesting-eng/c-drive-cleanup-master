# C-drive Cleanup Master (c-drive-cleanup-master)

> A safe Windows C: drive cleanup workflow — **measure / scan / delete** with **red lines** and an **11-item pitfalls checklist**.

![License: MIT](https://img.shields.io/badge/license-MIT-yellow)
![Version](https://img.shields.io/badge/version-1.2.0-blue)
![Stages](https://img.shields.io/badge/stages-6-orange)
![Pitfalls](https://img.shields.io/badge/pitfalls-11-red)

## Why this exists

Running out of C: drive space is the most common Windows pain. 99% of online "cleanup guides" only teach `cleanmgr` / `DISM`. They don't tell you **what absolutely must not be deleted**, nor **what looks deletable but will silently break things** (QQPCMgr live mirroring, the parts of `WinSxS` you really can't touch, Windows per-volume Recycle Bins, VSS, parent-directory mtime lies, ...).

This skill encodes "what not to touch" and "how to touch what you can" as a **red-lines + 11-pitfalls checklist + 6-stage pipeline**. Every stage has a red-line gate. Every pitfall has been hit in production with full evidence. All deletions go through the Windows Recycle Bin (`FOF_ALLOWUNDO`) and are fully reversible.

## Features

- 🚦 **Red lines first** — Desktop / Downloads / Documents / system directories / `.workbuddy` are NEVER touched
- 🪤 **11 pitfalls** — each with a full "hit -> evidence -> fix" chain
- 🧰 **6-stage pipeline** — measure -> scan -> grade -> backup-align -> delete-via-recycle -> verify
- 💬 **WeChat cleanup sub-module** — 4 scripts: backup redundancy detection / md5 content dedup / safe recycle execution
- ↩️ **Fully reversible** — every delete lands in the Windows Recycle Bin, recoverable on misclick
- 🌐 **Dual-publish** — GitHub (English, this repo) + SkillHub (Chinese, skillId 187879)

## 30-second quickstart

```bash
# 1) Read SKILL.md  <- the master doc (red lines + 6 stages + 11 pitfalls)
# 2) Measure baseline
python scripts/measure_free.py

# 3) Scan safe targets (read-only)
python scripts/scan_safe_targets.py

# 4) Optional: WeChat cleanup quartet
python scripts/wechat_analyze.py             # whole-tree inventory
python scripts/wechat_backup_inspect.py     # backup redundancy detection
python scripts/wechat_dedup_plan.py         # md5 content dedup
python scripts/wechat_dedup_recycle.py      # execute via recycle (careful!)

# 5) Generic target delete (careful!)
python scripts/delete_safe.py
```

> ⚠️ Before any write operation, read [SKILL.md §0 Red Lines](SKILL.md). All scripts are **pure Python stdlib** — no `pip install` required.

## Workflow

```
[measure] -> [scan] -> [grade] -> [align] -> [delete-via-recycle] -> [verify]
 measure    scan_safe  scan_safe   backup_    delete_safe            scan_safe
  _free     _targets   _targets    inspect    wechat_dedup           _targets
                                                   _recycle
```

## 11 pitfalls (top picks)

| # | Pitfall | One-liner |
|---|---|---|
| **11** | QQPCMgr "software move" is a **live mirror** | Deleting on C: mirror-deletes on E:; parent-dir mtime is not trustworthy |
| 6 | Windows has one Recycle Bin per volume | Clearing C: != clearing E: |
| 8 | Don't blindly clean `WinSxS` | `StartComponentCleanup` removes replaced components only; core OS files are off-limits |
| 5 | Parent-dir mtime doesn't reflect subtree activity | Check **child-dir** second-level mtime for liveness |
| ... | The other 7 are in [SKILL.md §4](SKILL.md) | |

## Docs & License

- 📖 **Master doc**: [SKILL.md](SKILL.md) — full spec (6 stages / 11 pitfalls / red lines / script usage)
- 📜 **License**: [LICENSE](LICENSE) (MIT)
- 🇨🇳 **SkillHub Chinese edition**: skillId 187879 ("C Drive Cleanup Master") — also published as the Chinese sibling under user `user_839f3063`
- ✍️ **Author**: [@jamesting-eng](https://github.com/jamesting-eng)

## Suitable / Not suitable

✅ Suitable for: Windows 10/11 users, red C: drive users, people who want a systematic cleanup  
❌ Not suitable for: anyone wanting a "one-click speed-up" silver bullet (this project sells discipline, not silver bullets)  
⚠️ **No warranty**: the author is not liable for losses from misuse — all deletions go via the Recycle Bin, but **clear it only after a personal review**

---

> 💡 The two most important things: ① Run `measure_free` to capture a baseline before any write op; ② Before assuming "I can delete this", come back and read [SKILL.md §0 Red Lines](SKILL.md).