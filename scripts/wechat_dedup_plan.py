#!/usr/bin/env python3
"""WeChat FileStorage/File deduplication planner (read-only).

Usage:
    python -S scripts/wechat_dedup_plan.py \
        --root <path-to-WeChat-Files> \
        --cache <path-to-cache.json> \
        --out <path-to-output-dir>

For every account under <root>, walks FileStorage/File, hashes each file
with md5 (block-by-block), groups files that share the same hash, and:

  * keeps one copy per group (shortest basename = most likely the original)
  * marks the rest for recycle-bin

Writes:
  <out>/file_dedup_plan.json  - the keep/delete plan
  <out>/wechat_dedup_report.html - interactive review report (search/filter)

This script never deletes anything.  Run scripts/wechat_dedup_recycle.py
with the plan JSON and --confirm to actually send duplicates to the
Windows Recycle Bin (recoverable, <=N per batch).
"""
import os, sys, json, argparse, hashlib, re
from _cli_utils import load_locale


CACHE_VERSION = 1
BLOCK = 1024 * 1024  # 1 MiB


def file_signature(p):
    try:
        st = os.stat(p)
        return (st.st_size, int(st.st_mtime), st.st_size)
    except OSError:
        return None


def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(BLOCK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def stem_of(path):
    """Strip trailing ' (n)' / '(n)(m)' decorative copies from a basename."""
    base = os.path.basename(path)
    name, _ext = os.path.splitext(base)
    name = re.sub(r"(\s*\(\d+\))+$", "", name)
    return name


WX_HTML_TMPL = """<!doctype html><html lang="__LANG__"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f8fb;--card:#fff;--ink:#1f2733;--sub:#5b6b7f;--line:#e6ebf1;
--accent:#2f6df6;--warn:#e8552a;--ok:#1a9d6b;--warnbg:#fff4ef;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
background:var(--bg);color:var(--ink);line-height:1.5;}
header{background:linear-gradient(135deg,#2f6df6,#5b8def);color:#fff;padding:22px 26px;}
header h1{margin:0 0 4px;font-size:22px}
header p{margin:0;opacity:.92;font-size:13px}
.wrap{max-width:1080px;margin:0 auto;padding:20px 18px 60px}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0 22px}
.card{flex:1 1 180px;background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:16px 18px;box-shadow:0 1px 3px rgba(20,40,80,.05)}
.card .n{font-size:26px;font-weight:800;color:var(--accent)}
.card .l{font-size:12px;color:var(--sub);margin-top:2px}
.card.warn .n{color:var(--warn)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
input[type=text]{flex:1 1 260px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:14px}
.btn{padding:9px 14px;border:1px solid var(--line);border-radius:10px;background:#fff;cursor:pointer;font-size:13px;color:var(--ink)}
.btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--line);font-size:13px;vertical-align:top}
th{background:#f0f4fa;color:var(--sub);font-weight:600;position:sticky;top:0}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}
.b-cnt{background:#eaf1ff;color:#2f6df6}
.b-flag{background:var(--warnbg);color:var(--warn)}
.b-ok{background:#e8f7f0;color:var(--ok)}
.keep{color:var(--ok);font-weight:600;word-break:break-all}
.del{color:var(--sub);word-break:break-all;font-size:12px}
details{margin-top:4px}
summary{font-size:12px;color:var(--accent);cursor:pointer}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;color:var(--sub)}
.note{background:#fff;border:1px solid var(--line);border-left:4px solid var(--warn);
border-radius:10px;padding:14px 16px;margin:18px 0;font-size:13px}
.foot{margin-top:22px;font-size:12px;color:var(--sub)}
</style></head><body>
<header><h1>__H1__</h1>
<p>__SUB__</p></header>
<div class="wrap">
  <div class="cards">
    <div class="card"><div class="n">__GROUPS__</div><div class="l">__CARD_GROUPS__</div></div>
    <div class="card"><div class="n">__DEL__</div><div class="l">__CARD_DEL__</div></div>
    <div class="card"><div class="n">__GB__ GB</div><div class="l">__CARD_GB__</div></div>
    <div class="card warn"><div class="n">__FLAG__</div><div class="l">__CARD_FLAG__</div></div>
  </div>
  <div class="note">
    <b>Plan:</b> __NOTE__
  </div>
  <div class="toolbar">
    <input type="text" id="q" placeholder="__SEARCH_PH__">
    <button class="btn active" id="fAll" onclick="setF('all')">__BTN_ALL__</button>
    <button class="btn" id="fFlag" onclick="setF('flag')">__BTN_FLAG__</button>
    <span class="mono" id="cnt"></span>
  </div>
  <table>
    <thead><tr><th style="width:42px">__TH_IDX__</th><th style="width:70px">__TH_COPIES__</th>
      <th>__TH_KEEP__</th><th>__TH_DEL__</th><th style="width:90px">__TH_STATUS__</th></tr></thead>
    <tbody id="tb"></tbody>
  </table>
  <div class="foot">__FOOT__</div>
</div>
<script>
const I18N = __I18N__;
const DATA = __DATA__;
const tb=document.getElementById('tb'), q=document.getElementById('q'), cnt=document.getElementById('cnt');
let filt='all';
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function fmt(b){return (b/1048576).toFixed(2)+' MB';}
function fmt2(s,a,b){return s.replace('%d',a).replace('%d',b);}
function row(g,i){
  let dels='';
  if(g.deletes.length){
    dels='<details><summary>'+I18N.show_n.replace('%d',g.deletes.length)+'</summary>'+
      g.deletes.map(d=>'<div class="del">'+esc(d)+'</div>').join('')+'</details>';
  }
  const st = g.flag ? '<span class="badge b-flag">'+I18N.mismatch+'</span>'
                    : '<span class="badge b-ok">'+I18N.safe+'</span>';
  return '<tr>'+
    '<td>'+(i+1)+'</td>'+
    '<td><span class="badge b-cnt">'+g.copies+'x</span></td>'+
    '<td><div class="keep">'+esc(g.keep.split(/[\\\\/]/).pop())+'</div>'+
       '<div class="mono">'+esc(g.keep)+'</div></td>'+
    '<td><div class="del">'+I18N.reclaim+' '+fmt(g.reclaim)+' ('+I18N.drop+' '+g.deletes.length+')</div>'+dels+'</td>'+
    '<td>'+st+'</td>'+
  '</tr>';
}
function render(){
  const t=q.value.trim().toLowerCase();
  let arr=DATA.groups.filter(g=>{
    if(filt==='flag'&&!g.flag)return false;
    if(!t)return true;
    const hay=(g.keep+' '+g.deletes.join(' ')).toLowerCase();
    return hay.includes(t);
  });
  tb.innerHTML=arr.map(row).join('');
  cnt.textContent=fmt2(I18N.showing, arr.length, DATA.groups.length);
}
function setF(f){filt=f;
  document.getElementById('fAll').classList.toggle('active',f==='all');
  document.getElementById('fFlag').classList.toggle('active',f==='flag');
  render();
}
q.addEventListener('input',render);
render();
</script></body></html>"""


def build_wechat_html(plan, groups_for_html, lang):
    L = load_locale(lang, base="wechat_locale")
    note = L["note"].replace("__BATCH__", "10")
    sub = L["sub"].replace("__GEN__", plan["generated_at"])
    i18n = json.dumps({
        "reclaim": L["js_reclaim"],
        "drop": L["js_drop"],
        "show_n": L["js_show_n"],
        "showing": L["js_showing"],
    }, ensure_ascii=False)
    return (WX_HTML_TMPL
            .replace("__LANG__", L["html_lang"])
            .replace("__TITLE__", L["title"])
            .replace("__H1__", L["h1"])
            .replace("__SUB__", sub)
            .replace("__CARD_GROUPS__", L["card_groups"])
            .replace("__CARD_DEL__", L["card_del"])
            .replace("__CARD_GB__", L["card_gb"])
            .replace("__CARD_FLAG__", L["card_flag"])
            .replace("__NOTE__", note)
            .replace("__SEARCH_PH__", L["search_ph"])
            .replace("__BTN_ALL__", L["btn_all"])
            .replace("__BTN_FLAG__", L["btn_flag"])
            .replace("__TH_IDX__", L["th_idx"])
            .replace("__TH_COPIES__", L["th_copies"])
            .replace("__TH_KEEP__", L["th_keep"])
            .replace("__TH_DEL__", L["th_del"])
            .replace("__TH_STATUS__", L["th_status"])
            .replace("__FOOT__", L["foot"])
            .replace("__GROUPS__", str(plan["dup_groups"]))
            .replace("__DEL__", str(plan["to_delete_count"]))
            .replace("__GB__", "%.2f" % (plan["to_delete_bytes"] / 1e9))
            .replace("__FLAG__", str(plan["flagged_groups"]))
            .replace("__I18N__", i18n)
            .replace("__DATA__", json.dumps({"groups": groups_for_html}, ensure_ascii=False)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="WeChat Files root directory")
    ap.add_argument("--cache", required=True, help="JSON cache file path (reuse between runs)")
    ap.add_argument("--out", required=True, help="output directory for plan + HTML report")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh",
                    help="report language: zh (default, SkillHub) or en (GitHub)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit("ERROR: root not found: " + root)

    cache = {}
    if os.path.isfile(args.cache):
        try:
            cache = json.load(open(args.cache, encoding="utf-8"))
        except Exception:
            cache = {}

    files_to_scan = []
    for acct in sorted(os.listdir(root)):
        fs_dir = os.path.join(root, acct, "FileStorage", "File")
        if not os.path.isdir(fs_dir):
            continue
        for dp, _, fs in os.walk(fs_dir):
            for f in fs:
                fp = os.path.join(dp, f)
                files_to_scan.append(fp)

    total = len(files_to_scan)
    hash_of = {}
    new_hashed = 0
    for i, fp in enumerate(files_to_scan, 1):
        sig = file_signature(fp)
        if sig is None:
            continue
        key = fp
        cached = cache.get(key)
        if cached and cached[0] == sig:
            hash_of[fp] = cached[1]
            continue
        try:
            h = md5_file(fp)
        except OSError:
            continue
        cache[key] = (sig, h)
        hash_of[fp] = h
        new_hashed += 1
        if new_hashed % 50 == 0:
            print("hashed %d new files (%.1fs)" % (new_hashed, 0.0), flush=True)

    # save cache
    with open(args.cache, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    # group by hash
    groups = {}
    for fp, h in hash_of.items():
        groups.setdefault(h, []).append(fp)

    unique_hashes = [h for h, lst in groups.items() if len(lst) == 1]
    dup_groups = [(h, lst) for h, lst in groups.items() if len(lst) > 1]

    keep = []
    delete = []
    flagged_groups = 0
    for h, lst in sorted(dup_groups, key=lambda kv: -len(kv[1])):
        # keep the one with the shortest basename; tie-breaker: earliest path
        lst_sorted = sorted(lst, key=lambda p: (len(os.path.basename(p)), p))
        kp = lst_sorted[0]
        dps = lst_sorted[1:]
        size = os.path.getsize(kp) if os.path.isfile(kp) else 0
        stems = {stem_of(p) for p in lst}
        if len(stems) > 1:
            flagged_groups += 1
        keep.append({"hash": h, "keep_path": kp, "size": size, "copies": len(lst)})
        for d in dps:
            delete.append({"hash": h, "delete_path": d, "size": size, "copies": len(lst)})

    to_delete_bytes = sum(d["size"] for d in delete)

    plan = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": root,
        "total_files_scanned": total,
        "unique": len(unique_hashes) + len(dup_groups),
        "dup_groups": len(dup_groups),
        "to_keep_count": len(keep),
        "to_delete_count": len(delete),
        "to_delete_bytes": to_delete_bytes,
        "flagged_groups": flagged_groups,
        "to_keep": keep,
        "to_delete": delete,
    }

    os.makedirs(args.out, exist_ok=True)
    plan_path = os.path.join(args.out, "file_dedup_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    # ---- HTML report ----
    # group deletes by keep_path so the HTML shows "keep + N deletes"
    del_by_hash = {}
    for d in delete:
        del_by_hash.setdefault(d["hash"], []).append(d["delete_path"])

    groups_for_html = []
    for k in keep:
        d_list = del_by_hash.get(k["hash"], [])
        groups_for_html.append({
            "keep": k["keep_path"],
            "deletes": d_list,
            "copies": k["copies"],
            "size": k["size"],
            "reclaim": k["size"] * max(0, len(d_list)),
            "flag": len({stem_of(k["keep_path"])} | {stem_of(p) for p in d_list}) > 1,
        })
    groups_for_html.sort(key=lambda g: -g["reclaim"])

    html_path = os.path.join(args.out, "wechat_dedup_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_wechat_html(plan, groups_for_html, args.lang))

    print("PLAN:", plan_path)
    print("HTML:", html_path)
    print("duplicates=%d  groups=%d  reclaim=%d bytes (%.2f GB)" %
          (plan["to_delete_count"], plan["dup_groups"], plan["to_delete_bytes"],
           plan["to_delete_bytes"] / 1e9))


if __name__ == "__main__":
    main()