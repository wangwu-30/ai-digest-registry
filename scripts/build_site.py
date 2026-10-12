"""从 curators/ 和各日报站点实时生成目录页（docs 产物不提交，随时可重建）。

页面原则：信息密度优先——一屏扫尽量多的条目，结论（名称/状态/更新时间）先行，次要信息收起。
纯静态 HTML + 少量原生 JS（搜索/筛选/排序），无框架，无 JS 时表格照常可读。
"""
import html, json, re, sys, urllib.request, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import registry as R

E = html.escape
SKILL = "https://github.com/wangwu-30/daily-skill"
SKILL_README = "https://raw.githubusercontent.com/wangwu-30/daily-skill/main/README.md"
JOIN = "https://github.com/wangwu-30/ai-digest-registry#readme"

def onboarding(md):
    """从 daily-skill README 中文段抽取接入提示词（单一真相源，页面不另写一份）。"""
    zh = md.split("## English")[0]
    quotes = re.findall(r"^> (.+)$", zh, re.M)
    three = re.search(r"### 你只需要告诉 agent 三件事\n+((?:\d\. .+\n?)+)", zh)
    items = [re.sub(r"\*\*(.+?)\*\*", r"\1", x).split("：")[0] for x in re.findall(r"^\d\. (.+)$", three.group(1), re.M)] if three else []
    if not quotes:
        return None
    return {"setup": quotes[0], "join": next((q for q in quotes[1:] if "黄页" in q), ""), "three": items}

def fetch_onboarding():
    try:
        with urllib.request.urlopen(SKILL_README, timeout=15) as r:
            return onboarding(r.read().decode())
    except Exception as x:
        print(f"警告：读取 daily-skill README 失败（{x}），接入区只显示链接", file=sys.stderr)
        return None

def onboard_html(ob):
    """头部小入口：核心是"做一份自己的日报"，收录进黄页只是末步。全文收进 <details> 默认不显示。"""
    three = "关注什么、信谁、喜欢什么风格"  # 短说法；完整问题在提示词（daily-skill README）里
    head = (f"<div class='cta-t'><b>做一份你自己的 AI 日报</b>"
            f"<span>告诉你的 agent {E(three)}，它帮你搭好并收录进黄页</span></div>")
    if not ob:
        return f"<div class='cta'>{head}<div class='join'><a href='{SKILL}'>开始</a></div></div>"
    prompt = ob["setup"] + ("\n" + ob["join"] if ob["join"] else "")
    return (f"<div class='cta'>{head}<div class='join'><button id='cp' type='button' title='复制提示词，发给你的 agent'>复制给 agent</button>"
            f"<details><summary>查看</summary><div class='pop'>"
            f"<p>发给你的 agent 后回答它三个问题；建仓、部署、定时发布、最后提 PR 收录进黄页都由它完成。</p>"
            f"<pre id='prompt'>{E(prompt)}</pre><p><a href='{SKILL}'>daily-skill</a> · <a href='{JOIN}'>收录说明</a></p></div></details></div></div>")

STATUS = {"ok": "正常", "fail": "检查未通过", "off": "已下架"}

def ago(date, today):
    try:
        d = (today - dt.date.fromisoformat(str(date)[:10])).days
    except Exception:
        return ""
    return "今天" if d <= 0 else ("昨天" if d == 1 else f"{d} 天前")

def row_html(r, today):
    e, info, st = r["e"], r["info"], r["st"]
    base = e["url"].rstrip("/")
    title = info.get("title") or r["name"]
    topics = info.get("topics") or []
    latest = info.get("latest") or ""
    links = [f"<a href='{E(base)}/feed.xml'>Atom</a>", f"<a href='{E(base)}/latest.json'>JSON</a>"]
    if info.get("opml"):
        links.append(f"<a href='{E(info['opml'])}'>OPML</a>")
    tags = ''.join(f'<button class=tag data-tag="{E(t)}">{E(t)}</button>' for t in topics)
    hay = " ".join([r["name"], title, e["author"], *topics, info.get("language") or ""]).lower()
    return (f"<tr data-s='{st}' data-t='{E(' '.join(topics))}' data-l='{E(info.get('language') or '')}' "
            f"data-d='{E(latest)}' data-n='{E(title.lower())}' data-q='{E(hay)}'>"
            f"<td class='nm'><span class='dot {st}' title='{STATUS[st]}'></span>"
            f"<a href='{E(e['url'])}'>{E(title)}</a><span class='host'>{E(base.split('://')[-1])}</span></td>"
            f"<td class='au'><a href='https://github.com/{E(e['author'])}'>@{E(e['author'])}</a></td>"
            f"<td class='tp'>{tags}</td>"
            f"<td class='lg'>{E(info.get('language') or '')}</td>"
            f"<td class='dt'><time datetime='{E(latest)}'>{E(latest)}</time><span class='ago'>{ago(latest, today)}</span></td>"
            f"<td class='st'><span class='pill {st}'>{STATUS[st]}</span></td>"
            f"<td class='lk'>{' · '.join(links)}</td></tr>")

CSS = """
:root{--bg:#fff;--fg:#18181b;--mu:#71717a;--bd:#e4e4e7;--hv:#f4f4f5;--ac:#2563eb;--ok:#16a34a;--fail:#d97706;--off:#a1a1aa;color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{--bg:#0b0b0d;--fg:#e4e4e7;--mu:#8b8b94;--bd:#26262b;--hv:#17171b;--ac:#60a5fa}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:13.5px/1.45 ui-sans-serif,system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
a{color:inherit;text-decoration:none}a:hover{color:var(--ac)}
.wrap{max-width:1200px;margin:0 auto;padding:20px 16px 40px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;margin-bottom:12px}
h1{font-size:18px;margin:0;letter-spacing:-.01em}.sub{color:var(--mu);font-size:12.5px}.sub a{color:var(--ac)}
.stats{display:flex;gap:14px;font-size:12px;color:var(--mu);margin-left:4px;align-self:center}
header{align-items:center}.stats b{color:var(--fg);font-variant-numeric:tabular-nums}
.bar{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;flex-wrap:wrap;gap:6px;padding:8px 0;border-bottom:1px solid var(--bd)}
.bar input,.bar select{font:inherit;color:inherit;background:var(--hv);border:1px solid var(--bd);border-radius:6px;padding:5px 9px}
.bar input{flex:1;min-width:180px}.bar input:focus{outline:2px solid var(--ac);outline-offset:-1px}
#chips{display:flex;flex-wrap:wrap;gap:4px;padding:8px 0}
.tag{font:inherit;font-size:11.5px;color:var(--mu);background:none;border:1px solid var(--bd);border-radius:999px;padding:0 7px;cursor:pointer;line-height:18px}
.tag:hover,.tag.on{color:var(--bg);background:var(--fg);border-color:var(--fg)}
table{width:100%;border-collapse:collapse}th{position:sticky;top:46px;background:var(--bg);text-align:left;font-weight:500;font-size:11.5px;color:var(--mu);padding:6px 8px;border-bottom:1px solid var(--bd);white-space:nowrap}
th[data-k]{cursor:pointer}th[data-k]:hover{color:var(--fg)}
td{padding:6px 8px;border-bottom:1px solid var(--bd);vertical-align:middle}tr:hover td{background:var(--hv)}
.nm{min-width:200px}.nm a{font-weight:600}.host{display:block;font-size:11.5px;color:var(--mu)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:1px}
.dot.ok,.pill.ok{--c:var(--ok)}.dot.fail,.pill.fail{--c:var(--fail)}.dot.off,.pill.off{--c:var(--off)}.dot{background:var(--c)}
.pill{font-size:11.5px;color:var(--c);white-space:nowrap}
.au,.lg,.lk{color:var(--mu);white-space:nowrap}.tp{display:flex;flex-wrap:wrap;gap:3px}td.tp{display:table-cell}.tp .tag{margin:1px}
.dt{white-space:nowrap;font-variant-numeric:tabular-nums}.ago{display:block;font-size:11.5px;color:var(--mu)}
.lk a{color:var(--ac)}#empty{display:none;color:var(--mu);padding:24px 8px}
.cta{display:flex;align-items:center;gap:10px;margin-left:auto}.join{flex-shrink:0;white-space:nowrap}.cta-t{min-width:0}.cta-t{display:flex;flex-direction:column;line-height:1.3;text-align:right}.cta-t b{font-size:12.5px}.cta-t span{font-size:11.5px;color:var(--mu)}
.join{position:relative;display:flex;align-items:center;border:1px solid var(--bd);border-radius:999px;font-size:12px;line-height:24px}
.join>button,.join>a{font:inherit;font-weight:500;border:0;background:none;color:var(--ac);padding:0 10px;cursor:pointer;border-radius:999px 0 0 999px}
.join>button:hover{background:var(--hv)}.join>button.done{color:var(--ok)}
.join summary{list-style:none;cursor:pointer;color:var(--mu);padding:0 10px 0 8px;border-left:1px solid var(--bd)}.join summary::-webkit-details-marker{display:none}
.join summary:hover,.join details[open] summary{color:var(--fg)}
.pop{position:absolute;right:0;top:30px;z-index:5;width:min(440px,calc(100vw - 32px));background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;box-shadow:0 8px 24px rgba(0,0,0,.12);line-height:1.5;color:var(--mu)}
.pop p{margin:0}.pop a{color:var(--ac)}.pop pre{margin:8px 0;font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-all;color:var(--fg);background:var(--hv);border-radius:6px;padding:8px}
footer{margin-top:18px;font-size:12px;color:var(--mu)}footer a{color:var(--ac)}
@media(max-width:720px){thead{display:none}table,tbody,tr,td{display:block}
 tr{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:9px 2px;border-bottom:1px solid var(--bd)}
 td{border:0;padding:0}td.nm{grid-column:1}td.dt{grid-column:2;grid-row:1;text-align:right}
 td.au,td.lg,td.st{display:none}td.tp{grid-column:1/-1}td.lk{grid-column:1/-1;font-size:12px}
 .bar input{flex-basis:100%}.cta{width:100%;justify-content:space-between}.cta-t{text-align:left}.bar select{flex:1}th{top:0}}
"""

JS = """
const $=s=>document.querySelector(s),rows=[...document.querySelectorAll('tbody tr')];let tag='',sk='d',asc=false;
function apply(){const q=$('#q').value.trim().toLowerCase(),s=$('#fs').value,l=$('#fl').value;let n=0;
 for(const r of rows){const v=(!q||q.split(/\\s+/).every(w=>r.dataset.q.includes(w)))&&(!s||r.dataset.s==s)&&(!l||r.dataset.l==l)&&(!tag||r.dataset.t.split(' ').includes(tag));r.hidden=!v;n+=v}
 $('#empty').style.display=n?'none':'block';$('#shown').textContent=n;
 document.querySelectorAll('.tag').forEach(b=>b.classList.toggle('on',b.dataset.tag==tag));
 const p=new URLSearchParams();q&&p.set('q',q);tag&&p.set('tag',tag);s&&p.set('s',s);l&&p.set('l',l);history.replaceState(null,'',p.size?'?'+p:location.pathname)}
function sort(){const tb=$('tbody');rows.sort((a,b)=>(a.dataset[sk]>b.dataset[sk]?1:-1)*(asc?1:-1)).forEach(r=>tb.appendChild(r))}
document.addEventListener('click',e=>{const b=e.target.closest('.tag');if(b){tag=tag==b.dataset.tag?'':b.dataset.tag;apply()}
 const h=e.target.closest('th[data-k]');if(h){asc=sk==h.dataset.k?!asc:h.dataset.k!='d';sk=h.dataset.k;sort()}});
['#q','#fs','#fl'].forEach(i=>$(i).addEventListener('input',apply));
document.addEventListener('keydown',e=>{if(e.key=='/'&&document.activeElement!=$('#q')){e.preventDefault();$('#q').focus()}});
const cp=$('#cp');cp&&cp.addEventListener('click',async()=>{const t=$('#prompt').textContent;try{await navigator.clipboard.writeText(t)}catch(_){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}cp.textContent='已复制 ✓';cp.classList.add('done');setTimeout(()=>{cp.textContent='复制给 agent';cp.classList.remove('done')},1600)});
const P=new URLSearchParams(location.search);$('#q').value=P.get('q')||'';tag=P.get('tag')||'';$('#fs').value=P.get('s')||'';$('#fl').value=P.get('l')||'';sort();apply();
"""

def render(rows, now, ob=None):
    today = now.astimezone(dt.timezone(dt.timedelta(hours=8))).date()
    rows = sorted(rows, key=lambda r: r["info"].get("latest") or "", reverse=True)
    topics = sorted({t for r in rows for t in (r["info"].get("topics") or [])})
    langs = sorted({r["info"].get("language") for r in rows if r["info"].get("language")})
    cnt = {k: sum(r["st"] == k for r in rows) for k in STATUS}
    body = "\n".join(row_html(r, today) for r in rows)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 日报黄页</title>
<meta name="description" content="每个人用自己的 agent 收集、重排、发布的 AI 日报目录">
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>AI 日报黄页</h1><span class="sub">每人一份 agent 处理过的 AI 日报</span>{onboard_html(ob)}</header>
<div class="bar"><input id="q" type="search" placeholder="搜索名称、作者、话题…（按 / 聚焦）" aria-label="搜索">
<select id="fs" aria-label="状态"><option value="">全部状态</option>{''.join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items())}</select>
<select id="fl" aria-label="语言"><option value="">全部语言</option>{''.join(f'<option>{E(l)}</option>' for l in langs)}</select><div class="stats"><span>收录 <b>{len(rows)}</b></span><span>正常 <b>{cnt['ok']}</b></span><span>显示 <b id="shown">{len(rows)}</b></span></div></div>
<div id="chips">{''.join(f'<button class="tag" data-tag="{E(t)}">{E(t)}</button>' for t in topics)}</div>
<table><thead><tr><th data-k="n">日报</th><th>作者</th><th>话题</th><th>语言</th><th data-k="d">最近更新</th><th>状态</th><th>订阅</th></tr></thead>
<tbody>
{body}
</tbody></table><div id="empty">没有匹配的日报</div>
<footer><a href="registry.json">registry.json</a> · 信息都从各站点实时读取，生成于 {now.strftime("%Y-%m-%d %H:%M UTC")} · 每天复检，连续失效或超过 14 天未更新会被下架</footer>
</div><script>{JS}</script></body></html>"""

def main(out="_site"):
    out = R.ROOT / out; out.mkdir(exist_ok=True)
    rows = []
    for name, e in R.all_entries().items():
        g2, g3, info = R.live_check(e)
        st = "off" if R.is_delisted(e) else ("ok" if not (g2 or g3) else "fail")
        rows.append({"name": name, "e": e, "info": info, "st": st})
    now = dt.datetime.now(dt.timezone.utc)
    (out / "index.html").write_text(render(rows, now, fetch_onboarding()))
    (out / "registry.json").write_text(json.dumps(
        [{"name": r["name"], "url": r["e"]["url"], "author": r["e"]["author"], "delisted": R.is_delisted(r["e"]),
          **{k: r["info"].get(k) for k in ("title", "topics", "language", "latest")}} for r in rows], ensure_ascii=False, indent=2))
    print(f"生成 {len(rows)} 个条目 → {out}")

if __name__ == "__main__":
    main(*sys.argv[1:])
