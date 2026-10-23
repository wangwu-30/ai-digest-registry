import datetime as dt
from html.parser import HTMLParser
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_site as B

EXISTING = (
    "我已有一份在更新的 AI 日报网页：<URL>。不要从零重建。按 "
    "https://github.com/wangwu-30/ai-digest-registry 的收录规则检查 "
    "latest.json、index.json、最新一期 data.json、feed.xml；按 "
    "https://github.com/wangwu-30/daily-skill 最小补齐，然后开 PR 加入黄页。"
)
MD = """# x
## 中文
**把这句话发给你的 agent：**

> 读 SKILL.md 帮我搭日报

### 你只需要告诉 agent 三件事

1. **关注什么**：话题。
2. **信任哪些人和来源**：人。
3. **偏好什么风格**：口吻。

### 加入黄页

> 把我的日报加入黄页 https://x

### 已有成熟日报，直接收录

> EXISTING

## English
> Read it
> Do not rebuild it from scratch.
""".replace("EXISTING", EXISTING.replace("<URL>", r"\<URL\>"))


class Prompts(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.pre = {}
        self.targets = []
        self.ids = []
        self.current = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "pre":
            self.current = attrs["id"]
            self.pre[self.current] = ""
        if "data-copy" in attrs:
            assert tag == "button"
            self.targets.append(attrs["data-copy"])

    def handle_data(self, data):
        if self.current is not None:
            self.pre[self.current] += data

    def handle_endtag(self, tag):
        if tag == "pre":
            self.current = None


def test_extract():
    assert B.onboarding(MD) == {
        "setup": "读 SKILL.md 帮我搭日报", "join": "把我的日报加入黄页 https://x",
        "list_existing": EXISTING, "three": ["关注什么", "信任哪些人和来源", "偏好什么风格"],
    }


def test_existing_before_join_does_not_replace_join():
    # Both quotes mention 黄页; their relative order must not select the wrong join.
    join = "> 把我的日报加入黄页 https://x\n"
    reordered = MD.replace(join, "").replace("## English", join + "\n## English")
    assert B.onboarding(reordered) == B.onboarding(MD)


def test_missing_and_escape():
    assert B.onboarding("## 中文\n无引用") is None
    assert "daily-skill" in B.onboard_html(None)
    old_md = MD[:MD.index("### 已有成熟")]
    old = B.onboarding(old_md)
    assert old["list_existing"] == ""
    fallback = B.onboard_html(old)
    assert "已有日报，直接收录</a>" in fallback
    assert "prompt-existing" not in fallback
    ob = {"setup": "<script>", "join": "", "list_existing": "<script> & <URL>"}
    markup = B.onboard_html(ob)
    assert "<script>" not in markup
    assert Prompts(markup).pre == {"prompt-setup": "<script>", "prompt-existing": "<script> & <URL>"}


def test_two_prompts_and_all_copy_targets():
    markup = B.render([], dt.datetime.now(dt.timezone.utc), B.onboarding(MD))
    parsed = Prompts(markup)
    assert parsed.pre == {
        "prompt-setup": "读 SKILL.md 帮我搭日报\n把我的日报加入黄页 https://x",
        "prompt-existing": EXISTING,
    }
    assert parsed.targets.count("prompt-setup") == 3  # hero, popup, bottom
    assert parsed.targets.count("prompt-existing") == 2  # hero, popup
    assert set(parsed.targets) == set(parsed.pre)
    assert len(parsed.ids) == len(set(parsed.ids))
    assert "<h2>从零做一份 AI 日报</h2>" in markup
    assert "<h2>已有日报，直接收录</h2>" in markup
    assert "查看提示词" in markup
    assert "同一套准入" in markup


def test_local_readme_build(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text(MD, encoding="utf-8")
    monkeypatch.setattr(B.R, "all_entries", lambda: {})

    def unexpected_fetch():
        raise AssertionError("Local README must not fetch remote prompts")

    monkeypatch.setattr(B, "fetch_onboarding", unexpected_fetch)
    out = tmp_path / "site"
    B.main(out, readme)
    assert Prompts((out / "index.html").read_text()).pre["prompt-existing"] == EXISTING


def test_enrich():
    pages = {"https://x.io/d/": '<meta name="description" content="一句话 &amp; 简介">',
             "https://x.io/d/latest.json": '{"sections":[{"items":[{"title":"头条"},{"title":"b"}]}]}'}
    x = B.enrich({"url": "https://x.io/d/"}, {}, get=lambda u: pages[u])
    assert x == {"desc": "一句话 & 简介", "headline": "头条", "count": 2}
    def boom(u): raise OSError
    assert B.enrich({"url": "https://x.io/d/", "description": "d"}, {}, get=boom)["desc"] == "d"
    h = B.card_html({"name": "n", "e": {"url": "https://x.io/d/", "author": "a"}, "info": {"title": "<b>"}, "st": "ok", "x": x}, dt.date.today())
    assert "<b>" not in h and "头条" in h
