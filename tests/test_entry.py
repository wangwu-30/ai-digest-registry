"""curator-entry.v1 条目反例 + 跨字段规则（G1）。源类型不受黄页限制：条目里根本没有源类型字段。"""
import json, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import registry as R

OK = {"name": "jane-ai-daily", "url": "https://jane.github.io/ai-daily/", "author": "jane"}

def write(tmp_path, e, fname=None):
    p = tmp_path / f"{fname or e.get('name', 'x')}.json"; p.write_text(json.dumps(e)); return p

BAD = {
    "缺 url": {"name": "jane-ai-daily", "author": "jane"},
    "name 大写": {**OK, "name": "Jane"},
    "name 1 位": {**OK, "name": "j"},
    "name 40 位": {**OK, "name": "j" * 40},
    "http url": {**OK, "url": "http://jane.github.io/ai-daily/"},
    "无点 host": {**OK, "url": "https://localhost/ai/"},
    "author 下划线": {**OK, "author": "ja_ne"},
    "author 以 - 结尾": {**OK, "author": "jane-"},
    "author 40 位": {**OK, "author": "a" * 40},
    "people 51 项": {**OK, "people": [f"p{i}" for i in range(51)]},
    "people 重复": {**OK, "people": ["a", "a"]},
    "people 65 字": {**OK, "people": ["a" * 65]},
    "非法 reason": {**OK, "delist_history": [{"from": "2026-10-01T00:00:00Z", "to": None, "reason": "bored"}]},
    "joined_at 无时区": {**OK, "joined_at": "2026-10-11T22:00:00"},
    "未知字段 topics": {**OK, "topics": ["agents"]},
    "x- 值为数组": {**OK, "x-tags": ["a"]},
    "x- 值超 200 字": {**OK, "x-note": "a" * 201},
    "x-A 大写键": {**OK, "x-A": "1"},
    "opml http": {**OK, "opml": "http://jane.github.io/sources.opml"},
    "restore 为 false": {**OK, "restore": False},
    "delist 区间缺 to": {**OK, "delist_history": [{"from": "2026-10-01T00:00:00Z", "reason": "down"}]},
    "新条目自填 author_id": {**OK, "author_id": 1},
}

def test_ok(tmp_path):
    assert R.check_entry(write(tmp_path, OK), {}) == []

@pytest.mark.parametrize("k", sorted(BAD))
def test_bad(tmp_path, k):
    assert R.check_entry(write(tmp_path, BAD[k], "jane-ai-daily" if "name" not in k else None), {}), k

def test_name_must_match_file(tmp_path):
    assert R.check_entry(write(tmp_path, OK, "other"), {})

def test_url_taken_even_if_delisted(tmp_path):
    other = {"name": "old", "url": "https://www.jane.github.io/ai-daily", "author": "x", "delist_history": [{"from": "2026-10-01T00:00:00Z", "to": None, "reason": "down"}]}
    assert R.check_entry(write(tmp_path, OK), {"old": other})

def test_only_author_id_can_edit(tmp_path):
    base = {**OK, "author_id": 7, "joined_at": "2026-10-12T00:00:00Z"}
    new = {**base, "people": ["karpathy"]}
    assert R.check_entry(write(tmp_path, new), {}, base, opener_id=8)
    assert R.check_entry(write(tmp_path, new), {}, base, opener_id=7) == []

def test_cannot_edit_registry_fields(tmp_path):
    base = {**OK, "author_id": 7, "joined_at": "2026-10-12T00:00:00Z"}
    assert R.check_entry(write(tmp_path, {**base, "joined_at": "2020-01-01T00:00:00Z"}), {}, base, 7)

def test_restore_only_when_delisted(tmp_path):
    base = {**OK, "author_id": 7, "joined_at": "2026-10-12T00:00:00Z"}
    assert R.check_entry(write(tmp_path, {**base, "restore": True}), {}, base, 7)
    dl = {**base, "delist_history": [{"from": "2026-10-20T00:00:00Z", "to": None, "reason": "stale"}]}
    assert R.check_entry(write(tmp_path, {**dl, "restore": True}), {}, dl, 7) == []

def test_delist_to_before_from(tmp_path):
    base = {**OK, "author_id": 7, "delist_history": [{"from": "2026-10-20T00:00:00Z", "to": "2026-10-19T00:00:00Z", "reason": "down"}]}
    assert R.check_entry(write(tmp_path, base), {}, base, 7)

def test_real_entries_valid():
    es = R.all_entries()
    for n in es:
        assert R.check_entry(R.ROOT / "curators" / f"{n}.json", {k: v for k, v in es.items() if k != n}, es[n]) == []
