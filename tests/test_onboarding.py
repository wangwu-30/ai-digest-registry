import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_site as B
MD = """# x\n## 中文\n**把这句话发给你的 agent：**\n\n> 读 SKILL.md 帮我搭日报\n\n### 你只需要告诉 agent 三件事\n\n1. **关注什么**：话题。\n2. **信任哪些人和来源**：人。\n3. **偏好什么风格**：口吻。\n\n### 加入黄页\n\n> 把我的日报加入黄页 https://x\n\n## English\n> Read it\n"""
def test_extract():
    ob = B.onboarding(MD)
    assert ob == {"setup": "读 SKILL.md 帮我搭日报", "join": "把我的日报加入黄页 https://x", "three": ["关注什么", "信任哪些人和来源", "偏好什么风格"]}
def test_missing_and_escape():
    assert B.onboarding("## 中文\n无引用") is None
    assert "<script>" not in B.onboard_html({"setup": "<script>", "join": "", "three": []})
    assert "daily-skill" in B.onboard_html(None)
    h = B.onboard_html({"setup": "a", "join": "b", "three": ["x"]})
    assert "做一份你自己的 AI 日报" in h and "复制给 agent" in h and h.index(">a\nb<") > 0
