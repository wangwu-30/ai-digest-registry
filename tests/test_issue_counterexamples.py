"""第一轮审查的 22 个日报反例（ai-digest-review R1）：schema + 脚本检查必须全部拒绝。"""
import copy, json, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import registry as R

BASE = "https://www.wangwu.ai/daily/"
GOOD = json.loads((Path(__file__).parent / "fixtures" / "issue.json").read_text())

def item(d, i=0):
    return [it for _, it in R.issue_items(d)][i]

def mut(f):
    def g():
        d = copy.deepcopy(GOOD); f(d); return d
    g.__name__ = f.__name__; return g

C = {}
def case(name):
    def deco(f):
        C[name] = mut(f); return f
    return deco

@case("01 summary 5000 字")
def _(d): item(d)["summary"] = "长" * 5000
@case("02 canonical_url 为 javascript:")
def _(d): item(d)["canonical_url"] = "javascript:alert(1)"
@case("03 canonical_url 为 null")
def _(d): item(d)["canonical_url"] = None
@case("04 canonical_url 指向日报自己")
def _(d): item(d)["canonical_url"] = BASE + "2026-10-12/"; item(d)["url"] = BASE + "2026-10-12/"
@case("05 date 为 2026-13-45")
def _(d): d["date"] = "2026-13-45"
@case("06 generated_at 为 2026-02-30T99:99Z")
def _(d): d["generated_at"] = "2026-02-30T99:99Z"
@case("07 language 为 english!!")
def _(d): d["language"] = "english!!"
@case("08 topics 为空")
def _(d): d["topics"] = []
@case("09 sections 为空")
def _(d): d["sections"] = []
@case("10 item.section 与父级不一致")
def _(d): item(d)["section"] = d["sections"][1]["id"]
@case("11 signals 为空对象")
def _(d): item(d)["signals"] = {}
@case("12 via 5 跳")
def _(d): item(d)["via"] = [{"name": f"p{i}", "url": f"https://p{i}.dev/daily/", "item_url": f"https://p{i}.dev/daily/x"} for i in range(5)]
@case("13 via.url 为 zzz")
def _(d): item(d)["via"] = [{"name": "p", "url": "zzz", "item_url": "zzz"}]
@case("14 sources.url 为 zzz")
def _(d): item(d)["sources"] = [{"url": "zzz"}]
@case("15 published_at 为 yesterday")
def _(d): item(d)["published_at"] = "yesterday"
@case("16 title 为空字符串")
def _(d): item(d)["title"] = ""
@case("17 tags 含空串")
def _(d): item(d)["tags"] = [""]
@case("18 自带全文 body 字段")
def _(d): item(d)["body"] = "全文" * 100
@case("19 同一条目重复出现")
def _(d): d["sections"][0]["items"].append(copy.deepcopy(item(d)))
@case("20 curator.url 为 https://")
def _(d): d["curator"]["url"] = "https://"
@case("21 schema_version 2.0")
def _(d): d["schema_version"] = "2.0"
@case("22 缺 generator.version")
def _(d): d["generator"].pop("version", None)

def test_good_fixture_passes():
    assert R.check_issue(GOOD, BASE) == []

def test_there_are_22():
    assert len(C) == 22

@pytest.mark.parametrize("name", sorted(C))
def test_counterexample_rejected(name):
    assert R.check_issue(C[name](), BASE), f"反例未被拒绝：{name}"

def test_aggregator_as_source_rejected_but_ok_in_via():
    d = copy.deepcopy(GOOD); item(d)["sources"] = [{"url": "https://news.ycombinator.com/item?id=1"}]
    assert R.check_issue(d, BASE)
