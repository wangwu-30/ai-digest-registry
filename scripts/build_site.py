"""从 curators/ 和各日报站点实时生成目录页（docs 产物不提交，随时可重建）。"""
import html, json, sys, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import registry as R

def main(out="_site"):
    out = R.ROOT / out; out.mkdir(exist_ok=True)
    rows = []
    for name, e in R.all_entries().items():
        g2, g3, info = R.live_check(e)
        status = "已下架" if R.is_delisted(e) else ("正常" if not (g2 or g3) else "检查未通过")
        rows.append((name, e, info, status))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tr = "\n".join(
        f"<tr><td><a href='{html.escape(e['url'])}'>{html.escape(info.get('title') or name)}</a></td>"
        f"<td>{html.escape(', '.join(info.get('topics') or []))}</td><td>{html.escape(info.get('language') or '')}</td>"
        f"<td>{html.escape(info.get('latest') or '')}</td><td>{status}</td>"
        f"<td><a href='https://github.com/{html.escape(e['author'])}'>@{html.escape(e['author'])}</a></td>"
        f"<td><a href='{html.escape(e['url'].rstrip('/'))}/feed.xml'>Atom</a> · <a href='{html.escape(e['url'].rstrip('/'))}/latest.json'>JSON</a>"
        + (f" · <a href='{html.escape(info['opml'])}'>OPML</a>" if info.get("opml") else "") + "</td></tr>"
        for name, e, info, status in rows)
    (out / "index.html").write_text(f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 日报黄页</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;max-width:960px;margin:2em auto;padding:0 1em}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:.4em;text-align:left}}</style>
<h1>AI 日报黄页</h1><p>每个人用自己的 agent 收集、重排、发布的 AI 日报。信息都从各站点实时读取，生成于 {now}。
<a href="https://github.com/wangwu-30/ai-digest-registry">如何加入</a> · <a href="registry.json">registry.json</a></p>
<table><tr><th>日报</th><th>话题</th><th>语言</th><th>最新一期</th><th>状态</th><th>作者</th><th>订阅</th></tr>
{tr}</table></html>""")
    (out / "registry.json").write_text(json.dumps(
        [{"name": n, "url": e["url"], "author": e["author"], "delisted": R.is_delisted(e), **{k: info.get(k) for k in ("title", "topics", "language", "latest")}}
         for n, e, info, _ in rows], ensure_ascii=False, indent=2))
    print(f"生成 {len(rows)} 个条目 → {out}")

if __name__ == "__main__":
    main(*sys.argv[1:])
