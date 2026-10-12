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

STATUS = {"ok": "正常", "fail": "检查未通过", "off": "已下架"}
ICON = {
 "rss": "<svg viewBox='0 0 24 24'><path d='M5 19a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16'/></svg>",
 "json": "<svg viewBox='0 0 24 24'><path d='M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1M16 3h1a2 2 0 0 1 2 2v5a2 2 0 0 0 2 2 2 2 0 0 0-2 2v5a2 2 0 0 1-2 2h-1'/></svg>",
 "opml": "<svg viewBox='0 0 24 24'><path d='M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01'/></svg>",
 "ext": "<svg viewBox='0 0 24 24'><path d='M7 17 17 7M8 7h9v9'/></svg>",
 "copy": "<svg viewBox='0 0 24 24'><rect x='9' y='9' width='12' height='12' rx='2'/><path d='M5 15V5a2 2 0 0 1 2-2h10'/></svg>",
 "search": "<svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='7'/><path d='m20 20-3.5-3.5'/></svg>",
}

def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-digest-registry"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def enrich(e, info, get=_get):
    """构建时补充卡片信息：简介（条目 description > 站点 meta description）、最新头条、条数。失败不影响收录。"""
    x = {"desc": e.get("description") or "", "headline": "", "count": 0}
    base = e["url"].rstrip("/")
    if not x["desc"]:
        try:
            m = re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)", get(e["url"]), re.I)
            x["desc"] = html.unescape(m.group(1)).strip() if m else ""
        except Exception:
            pass
    try:
        d = json.loads(get(base + "/latest.json"))
        items = [i for sec in d.get("sections") or [] for i in sec.get("items") or []]
        x["count"] = len(items)
        x["headline"] = (items[0].get("title") or "") if items else ""
    except Exception:
        pass
    return x

def onboard_html(ob):
    """hero 右侧主按钮：核心是"做一份自己的日报"，收录进黄页只是末步；全文收进浮层默认不显示。"""
    if not ob:
        return f"<a class='btn pri' href='{SKILL}'>做一份你自己的 AI 日报</a>"
    prompt = ob["setup"] + ("\n" + ob["join"] if ob["join"] else "")
    return (f"<div class='cta'><button id='cp' class='btn pri' type='button' title='复制提示词，发给你的 agent'>"
            f"{ICON['copy']}<span>做一份你自己的 AI 日报</span></button>"
            f"<details class='more'><summary class='btn ghost'>查看提示词</summary><div class='pop'>"
            f"<p class='pop-h'>复制给你的 agent，回答它三个问题：关注什么、信谁、喜欢什么风格。建仓、部署、定时发布、最后收录进黄页都由它完成。</p>"
            f"<pre id='prompt'>{E(prompt)}</pre><p class='pop-f'><a href='{SKILL}'>daily-skill {ICON['ext']}</a><a href='{JOIN}'>收录说明 {ICON['ext']}</a></p></div></details></div>")

def ago(date, today):
    try:
        d = (today - dt.date.fromisoformat(str(date)[:10])).days
    except Exception:
        return ""
    return "今天" if d <= 0 else ("昨天" if d == 1 else f"{d} 天前")

def avatar(title, url):
    host = url.split("://")[-1].split("/")[0]
    letter = (title.strip() or host)[0].upper()
    hue = sum(map(ord, host)) % 360
    return (f"<span class='av' style='--h:{hue}'><span>{E(letter)}</span>"
            f"<img src='https://www.google.com/s2/favicons?domain={E(host)}&amp;sz=64' alt='' loading='lazy' onerror='this.remove()' onload='this.naturalWidth<17&amp;&amp;this.remove()'></span>")

def card_html(r, today):
    e, info, st, x = r["e"], r["info"], r["st"], r.get("x") or {}
    base = e["url"].rstrip("/")
    title = info.get("title") or r["name"]
    topics = info.get("topics") or []
    latest = info.get("latest") or ""
    desc = x.get("desc") or ""
    hl = x.get("headline") or ""
    tags = "".join(f"<button class='tag' data-tag='{E(t)}'>{E(t)}</button>" for t in topics)
    subs = [f"<a class='ic' href='{E(base)}/feed.xml' title='Atom 订阅'>{ICON['rss']}</a>",
            f"<a class='ic' href='{E(base)}/latest.json' title='JSON'>{ICON['json']}</a>"]
    if info.get("opml"):
        subs.append(f"<a class='ic' href='{E(info['opml'])}' title='OPML 源清单'>{ICON['opml']}</a>")
    hay = " ".join([r["name"], title, e["author"], desc, hl, *topics, info.get("language") or ""]).lower()
    body = (f"<p class='desc'>{E(desc)}</p>" if desc else "") + (
        f"<p class='hl'><span>今日头条</span>{E(hl)}</p>" if hl else "")
    meta = [f"<a href='https://github.com/{E(e['author'])}'>@{E(e['author'])}</a>"]
    if info.get("language"):
        meta.append(E(info["language"]))
    if x.get("count"):
        meta.append(f"{x['count']} 条")
    return (f"<article class='card' data-s='{st}' data-t='{E(' '.join(topics))}' data-l='{E(info.get('language') or '')}' "
            f"data-d='{E(latest)}' data-n='{E(title.lower())}' data-q='{E(hay)}'>"
            f"<header class='ch'>{avatar(title, e['url'])}<div class='ct'><a class='nm' href='{E(e['url'])}'>{E(title)}</a>"
            f"<span class='host'>{E(base.split('://')[-1])}</span></div>"
            f"<span class='st {st}' title='{STATUS[st]}'><i></i>{ago(latest, today) or STATUS[st]}</span></header>"
            f"{body}<div class='tags'>{tags}</div>"
            f"<footer class='cf'><span class='meta'>{' · '.join(meta)}</span><span class='subs'>{''.join(subs)}</span></footer></article>")

CSS = """
:root{--bg:#fafafa;--bg2:#fff;--fg:#0a0a0a;--fg2:#3f3f46;--mu:#71717a;--bd:rgba(0,0,0,.08);--bd2:rgba(0,0,0,.14);--hv:rgba(0,0,0,.035);--ac:#5b5bd6;--ok:#22c55e;--fail:#f59e0b;--off:#a1a1aa;
--sh:0 1px 2px rgba(0,0,0,.04),0 1px 1px rgba(0,0,0,.02);--sh2:0 8px 24px -6px rgba(0,0,0,.12),0 2px 6px rgba(0,0,0,.04);color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{--bg:#09090b;--bg2:#111113;--fg:#fafafa;--fg2:#d4d4d8;--mu:#8b8b94;--bd:rgba(255,255,255,.07);--bd2:rgba(255,255,255,.14);--hv:rgba(255,255,255,.04);--ac:#8b8cf8;
--sh:0 1px 0 rgba(255,255,255,.03) inset;--sh2:0 12px 32px -8px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.06)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI","PingFang SC","Hiragino Sans GB","Noto Sans SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased;font-feature-settings:"cv11","ss01"}
body:before{content:"";position:fixed;inset:0 0 auto;height:320px;z-index:-1;background:radial-gradient(600px 200px at 15% -40px,color-mix(in srgb,var(--ac) 14%,transparent),transparent),radial-gradient(500px 180px at 85% -60px,color-mix(in srgb,#ec4899 8%,transparent),transparent)}
a{color:inherit;text-decoration:none}svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:16px 24px;flex-wrap:wrap;padding:36px 0 20px}
.brand{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--mu);margin-bottom:10px}.brand b{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:6px;background:var(--fg);color:var(--bg);font-size:11px}
h1{margin:0;font-size:28px;line-height:1.15;letter-spacing:-.025em;font-weight:650}
.lead{margin:6px 0 0;color:var(--mu);font-size:14.5px}
.btn{display:inline-flex;align-items:center;gap:7px;height:34px;padding:0 13px;border-radius:9px;font:inherit;font-size:13px;font-weight:550;cursor:pointer;white-space:nowrap;transition:background .15s,transform .15s,box-shadow .15s,color .15s;border:1px solid transparent}
.btn.pri{background:var(--fg);color:var(--bg);box-shadow:var(--sh2)}.btn.pri:hover{transform:translateY(-1px)}.btn.pri:active{transform:none}.btn.pri.done{background:var(--ok);color:#fff}
.btn.ghost{color:var(--fg2);border-color:var(--bd2);background:var(--bg2)}.btn.ghost:hover{background:var(--hv)}
.cta{display:flex;gap:8px;align-items:center}.more{position:relative}.more summary{list-style:none}.more summary::-webkit-details-marker{display:none}
.pop{position:absolute;right:0;top:42px;z-index:20;width:min(460px,calc(100vw - 40px));background:var(--bg2);border:1px solid var(--bd2);border-radius:12px;padding:14px;box-shadow:var(--sh2);animation:in .14s ease-out}
@keyframes in{from{opacity:0;transform:translateY(-4px)}}
.pop-h{margin:0 0 10px;font-size:12.5px;color:var(--mu)}.pop pre{margin:0;font:12px/1.6 ui-monospace,"SF Mono",Menlo,monospace;white-space:pre-wrap;word-break:break-all;background:var(--hv);border:1px solid var(--bd);border-radius:8px;padding:10px;color:var(--fg2)}
.pop-f{display:flex;gap:14px;margin:10px 0 0;font-size:12.5px}.pop-f a{display:inline-flex;align-items:center;gap:3px;color:var(--ac)}.pop-f svg{width:12px;height:12px}
.bar{position:sticky;top:0;z-index:10;padding:10px 0;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:saturate(180%) blur(12px);-webkit-backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--bd)}
.bar .wrap{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.sb{flex:1;min-width:220px;display:flex;align-items:center;gap:8px;height:34px;padding:0 11px;background:var(--bg2);border:1px solid var(--bd2);border-radius:9px;color:var(--mu);transition:border-color .15s,box-shadow .15s}
.sb:focus-within{border-color:var(--ac);box-shadow:0 0 0 3px color-mix(in srgb,var(--ac) 18%,transparent)}
.sb input{flex:1;min-width:0;border:0;outline:0;background:none;font:inherit;color:var(--fg)}.sb kbd{font:11px ui-monospace,monospace;border:1px solid var(--bd2);border-radius:5px;padding:0 5px;color:var(--mu)}
.seg{display:flex;padding:3px;gap:2px;background:var(--hv);border:1px solid var(--bd);border-radius:9px}
.seg button{font:inherit;font-size:12.5px;border:0;background:none;color:var(--mu);padding:0 10px;height:26px;border-radius:6px;cursor:pointer}.seg button.on{background:var(--bg2);color:var(--fg);box-shadow:var(--sh2)}
select{font:inherit;font-size:12.5px;height:34px;padding:0 10px;border-radius:9px;border:1px solid var(--bd2);background:var(--bg2);color:var(--fg2)}
.count{font-size:12.5px;color:var(--mu);font-variant-numeric:tabular-nums;margin-left:auto}
#chips{display:flex;gap:6px;overflow-x:auto;padding:12px 0 2px;scrollbar-width:none}#chips::-webkit-scrollbar{display:none}
.tag{font:inherit;font-size:11.5px;line-height:20px;padding:0 8px;border-radius:6px;border:1px solid var(--bd);background:var(--hv);color:var(--fg2);cursor:pointer;white-space:nowrap;transition:all .12s}
.tag:hover{border-color:var(--bd2);color:var(--fg)}.tag.on{background:var(--ac);border-color:var(--ac);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;padding:14px 0 8px}
.card{display:flex;flex-direction:column;gap:10px;background:var(--bg2);border:1px solid var(--bd);border-radius:14px;padding:14px 14px 12px;box-shadow:var(--sh);transition:border-color .15s,box-shadow .2s,transform .2s}
.card:hover{border-color:var(--bd2);box-shadow:var(--sh2);transform:translateY(-2px)}
.ch{display:flex;align-items:center;gap:10px;min-width:0}
.av{position:relative;flex-shrink:0;width:36px;height:36px;border-radius:10px;display:grid;place-items:center;overflow:hidden;font-weight:650;font-size:15px;color:#fff;background:linear-gradient(135deg,hsl(var(--h) 70% 58%),hsl(calc(var(--h) + 40) 70% 48%));box-shadow:inset 0 0 0 1px rgba(255,255,255,.15)}
.av img{position:absolute;inset:0;width:100%;height:100%;padding:7px;background:var(--bg2);object-fit:contain;box-shadow:inset 0 0 0 1px var(--bd)}
.ct{min-width:0;flex:1}.nm{display:block;font-weight:600;font-size:14.5px;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nm:hover{color:var(--ac)}
.host{display:block;font-size:12px;color:var(--mu);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.st{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--mu);white-space:nowrap;align-self:flex-start;padding:2px 8px;border-radius:999px;background:var(--hv)}
.st i{width:6px;height:6px;border-radius:50%;background:var(--c)}.st.ok{--c:var(--ok)}.st.ok i{box-shadow:0 0 0 3px color-mix(in srgb,var(--ok) 22%,transparent)}.st.fail{--c:var(--fail)}.st.off{--c:var(--off)}
.desc{margin:0;color:var(--fg2);font-size:13px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.hl{margin:0;font-size:13px;color:var(--fg2);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.hl span{font-size:11px;font-weight:600;color:var(--ac);margin-right:6px;padding:1px 6px;border-radius:5px;background:color-mix(in srgb,var(--ac) 12%,transparent)}
.tags{display:flex;flex-wrap:wrap;gap:4px}
.cf{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:auto;padding-top:10px;border-top:1px solid var(--bd)}
.meta{font-size:12px;color:var(--mu)}.meta a:hover{color:var(--fg)}
.subs{display:flex;gap:2px}.ic{display:grid;place-items:center;width:28px;height:28px;border-radius:7px;color:var(--mu);transition:all .12s}.ic:hover{background:var(--hv);color:var(--fg)}
.add{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;min-height:150px;border:1px dashed var(--bd2);border-radius:14px;color:var(--mu);font-size:13px;cursor:pointer;background:none;font-family:inherit;transition:all .15s}
.add:hover{color:var(--fg);border-color:var(--fg2);background:var(--hv)}.add b{font-size:22px;font-weight:300;line-height:1}
#empty{display:none;color:var(--mu);padding:40px 0;text-align:center}
.foot{padding:20px 0 40px;font-size:12px;color:var(--mu)}.foot a{color:var(--fg2)}.foot a:hover{color:var(--ac)}
@media(max-width:640px){.wrap{padding:0 14px}.hero{padding:22px 0 14px;align-items:flex-start}h1{font-size:22px}.lead{font-size:13.5px}
 .cta{width:100%}.cta .btn.pri{flex:1;justify-content:center}.sb{min-width:100%;order:-1}.seg{flex:1}.seg button{flex:1}
 .grid{grid-template-columns:1fr;gap:10px;padding-top:10px}.card{padding:12px}.add{min-height:90px}.pop{right:0}}
"""

JS = """
const $=s=>document.querySelector(s),cards=[...document.querySelectorAll('.card')];let tag='',st='';
function apply(){const q=$('#q').value.trim().toLowerCase(),l=$('#fl').value;let n=0;
 for(const c of cards){const v=(!q||q.split(/\\s+/).every(w=>c.dataset.q.includes(w)))&&(!st||c.dataset.s==st)&&(!l||c.dataset.l==l)&&(!tag||c.dataset.t.split(' ').includes(tag));c.hidden=!v;n+=v}
 $('#empty').style.display=n?'none':'block';$('#shown').textContent=n;
 document.querySelectorAll('.tag').forEach(b=>b.classList.toggle('on',b.dataset.tag==tag));
 document.querySelectorAll('.seg button').forEach(b=>b.classList.toggle('on',b.dataset.s==st));
 const p=new URLSearchParams();q&&p.set('q',q);tag&&p.set('tag',tag);st&&p.set('s',st);l&&p.set('l',l);history.replaceState(null,'',p.size?'?'+p:location.pathname)}
document.addEventListener('click',e=>{const b=e.target.closest('.tag');if(b){tag=tag==b.dataset.tag?'':b.dataset.tag;apply()}
 const s=e.target.closest('.seg button');if(s){st=s.dataset.s;apply()}
 const m=document.querySelector('details.more[open]');if(m&&!m.contains(e.target))m.open=false});
$('#q').addEventListener('input',apply);$('#fl').addEventListener('input',apply);
document.addEventListener('keydown',e=>{if(e.key=='/'&&document.activeElement!=$('#q')){e.preventDefault();$('#q').focus()}if(e.key=='Escape'){const m=document.querySelector('details.more[open]');m&&(m.open=false)}});
async function copy(btn){const t=$('#prompt').textContent;try{await navigator.clipboard.writeText(t)}catch(_){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}
 if(btn==cp){const s=cp.querySelector('span'),o=s.textContent;s.textContent='已复制，发给你的 agent';cp.classList.add('done');setTimeout(()=>{s.textContent=o;cp.classList.remove('done')},1800)}}
const cp=$('#cp');cp&&cp.addEventListener('click',()=>copy(cp));const ad=$('.add');ad&&cp&&ad.addEventListener('click',()=>{copy(cp);window.scrollTo({top:0,behavior:'smooth'})});
const P=new URLSearchParams(location.search);$('#q').value=P.get('q')||'';tag=P.get('tag')||'';st=P.get('s')||'';$('#fl').value=P.get('l')||'';apply();
"""

def render(rows, now, ob=None):
    today = now.astimezone(dt.timezone(dt.timedelta(hours=8))).date()
    rows = sorted(rows, key=lambda r: (r["st"] != "ok", r["info"].get("latest") or ""), reverse=False)
    rows = sorted(rows, key=lambda r: r["info"].get("latest") or "", reverse=True)
    rows = sorted(rows, key=lambda r: r["st"] != "ok")
    topics = sorted({t for r in rows for t in (r["info"].get("topics") or [])})
    langs = sorted({r["info"].get("language") for r in rows if r["info"].get("language")})
    cnt = {k: sum(r["st"] == k for r in rows) for k in STATUS}
    cards = "\n".join(card_html(r, today) for r in rows)
    add = "<button class='add' type='button'><b>+</b>做一份你自己的，收录在这里</button>" if ob else ""
    seg = "".join(f"<button data-s='{k}'>{v}</button>" for k, v in [("", f"全部 {len(rows)}"), ("ok", f"正常 {cnt['ok']}")])
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 日报黄页</title>
<meta name="description" content="每个人用自己的 agent 收集、重排、发布的 AI 日报目录。做一份你自己的，收录在这里。">
<meta name="color-scheme" content="light dark"><style>{CSS}</style></head><body>
<div class="wrap"><section class="hero"><div><div class="brand"><b>黄</b>AI Digest Registry</div>
<h1>AI 日报黄页</h1><p class="lead">每人一份由自己的 agent 收集、重排、发布的 AI 日报，按话题挑着订。</p></div>{onboard_html(ob)}</section></div>
<div class="bar"><div class="wrap"><label class="sb">{ICON['search']}<input id="q" type="search" placeholder="搜索日报、作者、话题…" aria-label="搜索"><kbd>/</kbd></label>
<div class="seg">{seg}</div><select id="fl" aria-label="语言"><option value="">全部语言</option>{''.join(f'<option>{E(l)}</option>' for l in langs)}</select>
<span class="count">显示 <b id="shown">{len(rows)}</b></span></div></div>
<main class="wrap"><div id="chips">{''.join(f'<button class="tag" data-tag="{E(t)}">{E(t)}</button>' for t in topics)}</div>
<div class="grid">{cards}{add}</div><div id="empty">没有匹配的日报</div>
<footer class="foot"><a href="registry.json">registry.json</a> · <a href="{JOIN}">收录规则</a> · 信息从各站点实时读取，生成于 {now.strftime("%Y-%m-%d %H:%M UTC")} · 每天复检，连续失效或 14 天未更新自动下架</footer></main>
<script>{JS}</script></body></html>"""

def main(out="_site"):
    out = R.ROOT / out; out.mkdir(exist_ok=True)
    rows = []
    for name, e in R.all_entries().items():
        g2, g3, info = R.live_check(e)
        st = "off" if R.is_delisted(e) else ("ok" if not (g2 or g3) else "fail")
        rows.append({"name": name, "e": e, "info": info, "st": st, "x": enrich(e, info)})
    now = dt.datetime.now(dt.timezone.utc)
    (out / "index.html").write_text(render(rows, now, fetch_onboarding()))
    (out / "registry.json").write_text(json.dumps(
        [{"name": r["name"], "url": r["e"]["url"], "author": r["e"]["author"], "delisted": R.is_delisted(r["e"]),
          **{k: r["info"].get(k) for k in ("title", "topics", "language", "latest")}} for r in rows], ensure_ascii=False, indent=2))
    print(f"生成 {len(rows)} 个条目 → {out}")

if __name__ == "__main__":
    main(*sys.argv[1:])
