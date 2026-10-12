"""黄页准入与每日复检（SKILL.md §5，ACCEPTANCE §R G1–G3）。

黄页只存条目；所有其余信息（话题、语言、标题、更新时间）都在检查时从日报站点实时读取。
"""
import json, os, re, sys, ipaddress, datetime as dt, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
sys.path.insert(0, str(Path(__file__).parent))
from canon import canonical

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema"
DIGEST_SCHEMAS = {"1.0": "digest.v1.json", "1.1": "digest.v1.1.json", "1.2": "digest.v1.2.json", "1.3": "digest.v1.3.json"}
ATOM = "{http://www.w3.org/2005/Atom}"
BAD_HOSTS = ("example.com", "example.org", "example.net", "localhost")
UA = "ai-digest-registry-check/1.0 (+https://github.com/wangwu-30/ai-digest-registry)"


def _validator(name):
    return Draft202012Validator(json.loads((SCHEMA / name).read_text()), format_checker=FormatChecker())


def schema_errors(doc, name):
    return [f"{name}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message[:160]}"
            for e in _validator(name).iter_errors(doc)]


def parse_instant(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_json(p):
    return json.loads(Path(p).read_text())


def aggregators():
    return set(load_json(ROOT / "aggregators.json"))


# ---------- G1：条目 ----------
def check_entry(path, others, base_entry=None, opener_id=None):
    """path：条目文件；others：{name: entry} 其他条目；base_entry：主分支上的旧版本（新条目为 None）。"""
    errs = []
    path = Path(path)
    try:
        e = load_json(path)
    except Exception as x:
        return [f"G1 不是合法 JSON：{x}"]
    if not isinstance(e, dict):
        return ["G1 条目必须是 JSON 对象"]
    errs += [f"G1 {m}" for m in schema_errors(e, "curator-entry.v1.json")]
    if e.get("name") != path.stem:
        errs.append(f"G1 name ({e.get('name')}) 必须等于文件名 ({path.stem})")
    try:
        cu = canonical(e.get("url", ""))
    except Exception:
        cu = None
        errs.append("G1 url 无法规范化")
    for n, o in others.items():
        if n == path.stem:
            continue
        try:
            if cu and canonical(o.get("url", "")) == cu:
                errs.append(f"G1 url 已被条目 {n} 使用（含已下架条目）")
        except Exception:
            pass
    reg_fields = ("author_id", "joined_at", "delist_history")
    if base_entry is None:
        for f in reg_fields:
            if f in e:
                errs.append(f"G1 新条目不能自己填写 {f}（由黄页在合并时写入）")
        if "restore" in e:
            errs.append("G1 新条目不能带 restore")
    else:
        for f in reg_fields:
            if e.get(f) != base_entry.get(f):
                errs.append(f"G1 PR 不能修改 {f}")
        if opener_id is not None and base_entry.get("author_id") not in (None, opener_id):
            errs.append("G1 只有 author_id 对应的账号能修改这个条目")
        if e.get("restore") and not is_delisted(base_entry):
            errs.append("G1 条目未下架，不能带 restore")
        if is_delisted(base_entry) and (e.get("url") != base_entry.get("url") or e.get("name") != base_entry.get("name")):
            errs.append("G1 下架期间不能改名或迁移，请先恢复")
    for iv in e.get("delist_history", []) or []:
        try:
            if iv.get("to") and parse_instant(iv["to"]) < parse_instant(iv["from"]):
                errs.append("G1 delist_history 区间 to 早于 from")
        except Exception:
            pass
    return errs


def is_delisted(e):
    h = (e or {}).get("delist_history") or []
    return bool(h) and h[-1].get("to") is None


# ---------- 日报内容检查（G2 的一部分：B3/B4/B5/B6/B13 + 脚本项 C1/C4/D1） ----------
def _host(u):
    try:
        return canonical(u).split("/")[0].split(":")[0]
    except Exception:
        return None


def bad_host(u, aggs, allow_agg=False):
    h = _host(u)
    if not h:
        return "无法解析"
    if h in BAD_HOSTS or h.endswith(".example") or h.endswith(".local") or any(h.endswith("." + b) for b in BAD_HOSTS):
        return "占位/本地域名"
    try:
        ip = ipaddress.ip_address(h.strip("[]"))
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return "私网 IP"
    except ValueError:
        pass
    if not allow_agg and any(h == a or h.endswith("." + a) for a in aggs):
        return "聚合站不能作为原始来源"
    return None


def issue_items(doc):
    for s in doc.get("sections") or []:
        for it in s.get("items") or []:
            yield s, it


def check_issue(doc, base, label="data.json", aggs=None):
    aggs = aggregators() if aggs is None else aggs
    errs = []
    if not isinstance(doc, dict):
        return [f"{label}: 不是 JSON 对象"]
    sv = doc.get("schema_version")
    if sv not in DIGEST_SCHEMAS:
        return [f"{label}: 未知 schema_version {sv!r}"]
    errs += [f"{label} {m}" for m in schema_errors(doc, DIGEST_SCHEMAS[sv])]
    if errs:
        return errs
    cbase = canonical(base)
    # B13
    if canonical(doc["curator"]["url"]) != cbase:
        errs.append(f"{label}: B13 curator.url 必须等于日报地址 {base}")
    # C1
    ids = [s.get("id") for s in doc["sections"]]
    if len(ids) != len(set(ids)):
        errs.append(f"{label}: C1 section id 重复")
    seen_id, seen_url = set(), set()
    for s, it in issue_items(doc):
        if it.get("section") != s.get("id"):
            errs.append(f"{label}: C1 条目 {it.get('id')} 的 section 与所在栏目不一致")
        # C4
        for u in [it.get("canonical_url")] + [x.get("url") for x in it.get("sources") or []]:
            if u:
                r = bad_host(u, aggs)
                if r:
                    errs.append(f"{label}: C4 {u} {r}")
                elif canonical(u).startswith(cbase + "/") or canonical(u) == cbase:
                    errs.append(f"{label}: C4 {u} 指向日报自己")
        for v in it.get("via") or []:
            r = bad_host(v.get("url", ""), aggs, allow_agg=True)
            if r:
                errs.append(f"{label}: C4 via {v.get('url')} {r}")
        # D1
        if it.get("id") in seen_id:
            errs.append(f"{label}: D1 id {it.get('id')} 重复")
        seen_id.add(it.get("id"))
        k = (canonical(it["canonical_url"]), it.get("entry"))
        if k in seen_url:
            errs.append(f"{label}: D1 同一链接 {it['canonical_url']} 出现两次")
        seen_url.add(k)
    return errs


def check_index(idx, base):
    errs = [f"index.json {m}" for m in schema_errors(idx, "index.v1.json")]
    if not errs and canonical(idx["curator"]["url"]) != canonical(base):
        errs.append("index.json: B13 curator.url 必须等于日报地址")
    return errs


def check_feed(xml_bytes, base, newest_date):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as x:
        return [f"feed.xml: B6 不是合法 XML（{x}）"]
    if root.tag != ATOM + "feed":
        return ["feed.xml: B6 不是 Atom feed"]
    entries = root.findall(ATOM + "entry")
    if not entries:
        return ["feed.xml: B6 没有 entry"]
    errs = []
    if any(True for _ in root.iter(ATOM + "content")):
        errs.append("feed.xml: B6 不允许 content 元素")
    def upd(e):
        t = e.findtext(ATOM + "updated") or ""
        try:
            return parse_instant(t)
        except Exception:
            return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    top = max(entries, key=upd)
    links = [l.get("href") for l in top.findall(ATOM + "link") if l.get("rel", "alternate") == "alternate"]
    want = canonical(base.rstrip("/") + f"/{newest_date}/")
    if not any(l and canonical(l) == want for l in links):
        errs.append(f"feed.xml: B6 最新 entry 没有链接到 {base.rstrip('/')}/{newest_date}/")
    return errs


# ---------- 网络 ----------
def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def live_check(entry, now=None, fetcher=fetch, aggs=None):
    """返回 (g2_errors, g3_errors, info)。info 是从站点读到的展示信息，不落盘到条目。"""
    now = now or dt.datetime.now(dt.timezone.utc)
    base = entry["url"].rstrip("/") + "/"
    g2, g3, info = [], [], {}
    def get_json(u, label):
        st, ct, body = fetcher(u)
        if st != 200:
            raise ValueError(f"{label} 返回 {st}")
        if "json" not in ct:
            g2.append(f"{label}: Content-Type 不是 JSON（{ct}）")
        return json.loads(body)
    try:
        latest = get_json(base + "latest.json", "latest.json")
        idx = get_json(base + "index.json", "index.json")
    except Exception as x:
        return [f"G2 {x}"], ["G3 无法读取 index.json"], info
    g2 += check_index(idx, base)
    g2 += check_issue(latest, base, "latest.json", aggs)
    if latest.get("generated_from") == "fixture":
        g2.append("G1 latest.json 是 fixture，不能收录")
    dates = sorted((d for d in idx.get("dates") or [] if isinstance(d, dict)), key=lambda d: d.get("date", ""))
    if not dates:
        return g2 + ["G2 index.json 没有日期"], ["G3 没有已发布的期"], info
    newest = dates[-1]
    if latest.get("date") != newest.get("date"):
        g2.append(f"latest.json: B4 date {latest.get('date')} 不是 index.json 中最新的 {newest.get('date')}")
    try:
        data = get_json(newest["json"], f"{newest['date']}/data.json")
        if data.get("date") != newest["date"]:
            g2.append(f"{newest['date']}/data.json: B3 date 不一致")
        g2 += check_issue(data, base, f"{newest['date']}/data.json", aggs)
    except Exception as x:
        g2.append(f"G2 {x}")
    for k in ("html", "md"):
        try:
            st, _, _ = fetcher(newest[k])
            if st != 200:
                g2.append(f"B5 {newest[k]} 返回 {st}")
        except Exception as x:
            g2.append(f"B5 {newest.get(k)} 不可访问（{x}）")
    try:
        st, ct, body = fetcher(base + "feed.xml")
        g2 += [f"feed.xml 返回 {st}"] if st != 200 else check_feed(body, base, newest["date"])
    except Exception as x:
        g2.append(f"G2 feed.xml 不可访问（{x}）")
    pubs = []
    for d in dates:
        try:
            pubs.append(parse_instant(d["published_at"]))
        except Exception:
            pass
    if not pubs:
        g3.append("G3 index.json 没有 published_at")
    elif max(pubs) < now - dt.timedelta(days=14):
        g3.append(f"G3 最近一期发布于 {max(pubs).isoformat()}，超过 14 天")
    try:
        topics = set(json.loads((ROOT / "topics.json").read_text()))
        extra = [t for t in idx.get("topics") or [] if t not in topics]
        if extra:
            info["unknown_topics"] = extra  # 报告，不拦截；话题词表通过 PR 扩充
    except Exception:
        pass
    info.update(title=idx.get("title"), language=idx.get("language"), topics=idx.get("topics"),
                timezone=idx.get("timezone"), latest=newest.get("date"), published_at=newest.get("published_at"),
                opml=idx.get("sources_opml"))
    if entry.get("opml") and not idx.get("sources_opml"):
        g2.append("G1 条目带 opml，但日报 index.json 没有 sources_opml")
    return g2, g3, info


def all_entries():
    return {p.stem: load_json(p) for p in sorted((ROOT / "curators").glob("*.json"))}
