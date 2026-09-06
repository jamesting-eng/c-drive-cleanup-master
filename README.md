# C-drive 清理主控 (c-drive-cleanup-master)

> 安全 Windows C: 硬盘清理工作流 —— **测量 / 扫描 / 删除**,内置**红线**和**11 条踩坑清单**。

![License: MIT](https://img.shields.io/badge/license-MIT-yellow)
![Version](https://img.shields.io/badge/version-1.2.0-blue)
![Stage](https://img.shields.io/badge/stages-6-orange)
![Pitfalls](https://img.shields.io/badge/pitfalls-11-red)

## 为什么做这个

C 盘红了是 Windows 用户最常碰到的痛点。网上 99% 的"清理教程"只教 `cleanmgr` / `DISM`,**不告诉你哪些绝对不能删**,**也不告诉你哪些看着能删其实删了会出事**(QQPCMgr 实时镜像、`WinSxS` 真正不能动的部分、Windows 双回收站、卷影副本、父目录 mtime 假象……)。

这个 skill 把"红线和踩坑"做成**铁律清单 + 6 阶段流水线**,每一步有红线把关,每一条坑都有实测证据,所有删除走 Windows 回收站(`FOF_ALLOWUNDO`)全程可还原。

## 核心特性

- 🚦 **红线先行** —— Desktop / Downloads / Documents / 系统目录 / `.workbuddy` 永!不!触!碰
- 🪤 **11 条踩坑清单** —— 每一条都有"踩过 → 实证 → 修复"完整链路
- 🧰 **6 阶段流水线** —— 测量 → 扫描 → 分级 → 备份对齐 → 走回收站删除 → 复核
- 💬 **微信专清子模块** —— 4 个脚本处理备份冗余识别 / md5 内容去重 / 安全回收
- ↩️ **全程可还原** —— 删除 100% 进 Windows 回收站,误操作可还原
- 🌐 **双发** —— GitHub(英文/中文双 README)+ SkillHub 中文版(skillId 187879)

## 30 秒上手

```bash
# 1) 读 SKILL.md  ← 主文档,红线 + 6 阶段 + 11 踩坑全在
# 2) 测基线
python scripts/measure_free.py

# 3) 扫可回收目标(只看不动)
python scripts/scan_safe_targets.py

# 4) 可选:微信专清四件套
python scripts/wechat_analyze.py             # 全树盘点
python scripts/wechat_backup_inspect.py     # 备份冗余识别
python scripts/wechat_dedup_plan.py         # md5 内容去重
python scripts/wechat_dedup_recycle.py       # 走回收站执行(慎!)

# 5) 通用目标删除(慎!)
python scripts/delete_safe.py
```

> ⚠️ 任何写操作前先看 [SKILL.md §0 红线](SKILL.md)。本项目所有脚本都是**纯 Python 标准库**,无需 `pip install` 任何东西。

## 工作流

```
[测量基线] → [安全扫描] → [红线分级] → [备份对齐] → [走回收站删除] → [复核]
 measure      scan_safe      scan_safe      backup_      delete_safe      scan_safe
  _free       _targets       _targets       inspect      wechat_dedup     _targets
                                                              _recycle
```

## 11 条踩坑(精选)

| # | 坑 | 一句话教训 |
|---|---|---|
| **11** | QQPCMgr 软件搬家是**实时镜像** | 删 C 盘会同步删 E 盘,父目录 mtime 不可信 |
| 6 | Windows 每个盘有独立回收站 | C 盘清空 ≠ E 盘清空 |
| 8 | `WinSxS` 别瞎清 | "开始组件清理"清的是被取代组件,核心组件删了系统直接挂 |
| 5 | 父目录 mtime 不代表子树活跃度 | 看活跃度要看**子目录**秒级 mtime |
| ··· | 其余 7 条见 [SKILL.md §4](SKILL.md) | |

## 文档与许可

- 📖 **主文档**:[SKILL.md](SKILL.md)——完整规范(6 阶段 / 11 踩坑 / 红线清单 / 脚本用法)
- 📜 **许可证**:[LICENSE](LICENSE) (MIT)
- 🇨🇳 **SkillHub 中文版**:`skillhub.cn` 搜索"**C盘清理大师**"(skillId 187879)
- ✍️ **作者**:[@jamesting-eng](https://github.com/jamesting-eng)

## 适用 / 不适用

✅ 适合:Windows 10/11 用户、C 盘红了不知道删啥、想系统化做清理  
❌ 不适合:想要"一键加速"的银弹(本项目强调纪律,不卖银弹)  
⚠️ **不承诺**:本项目作者不为误用造成的损失负责——所有删除走回收站,但**清空回收站前请自己再过一遍**

---

> 💡 **最重要的两件事**:① 跑任何写操作前先 `measure_free` 留基线;② 任何"我以为这样能删"之前,先回来读 [SKILL.md §0 红线](SKILL.md)。
