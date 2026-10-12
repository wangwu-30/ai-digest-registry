"""G2/G3 用假网络测试：14 天新鲜度、feed 检查。"""
import json, sys, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import registry as R

BASE = "https://www.wangwu.ai/daily/"
ISSUE = json.loads((Path(__file__).parent / "fixtures" / "issue.json").read_text())
D = ISSUE["date"]
IDX = {"schema_version": "1.3", "curator": ISSUE["curator"], "topics": ISSUE["topics"], "language": "zh-CN",
       "title": "t", "latest": D, "schema": "https://www.wangwu.ai/daily/schema/digest.v1.3.json", "timezone": "Asia/Shanghai",
       "dates": [{"date": D, "generated_at": ISSUE["generated_at"], "published_at": ISSUE["published_at"],
                  "html": f"{BASE}{D}/", "md": f"{BASE}{D}/index.md", "json": f"{BASE}{D}/data.json"}]}
FEED = f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>t</title><id>{BASE}</id><updated>{ISSUE['published_at']}</updated>
<entry><title>t</title><id>{BASE}{D}/</id><updated>{ISSUE['published_at']}</updated><link rel="alternate" href="{BASE}{D}/"/></entry></feed>""".encode()

def fake(feed=FEED):
    def f(u):
        m = {BASE + "latest.json": ISSUE, BASE + "index.json": IDX, f"{BASE}{D}/data.json": ISSUE}
        if u in m: return 200, "application/json", json.dumps(m[u]).encode()
        if u.endswith("feed.xml"): return 200, "application/atom+xml", feed
        return 200, "text/html", b"ok"
    return f

E = {"name": "wangwu-daily", "url": BASE, "author": "wangwu-30"}
NOW = R.parse_instant(ISSUE["published_at"]) + dt.timedelta(days=1)

def test_index_fixture_valid():
    assert R.check_index(IDX, BASE) == []

def test_pass():
    g2, g3, _ = R.live_check(E, NOW, fake())
    assert (g2, g3) == ([], [])

def test_stale():
    _, g3, _ = R.live_check(E, NOW + dt.timedelta(days=14), fake())
    assert g3

def test_feed_with_content_rejected():
    g2, _, _ = R.live_check(E, NOW, fake(FEED.replace(b"</entry>", b"<content>x</content></entry>")))
    assert g2

def test_down():
    g2, _, _ = R.live_check(E, NOW, lambda u: (404, "text/html", b""))
    assert g2
