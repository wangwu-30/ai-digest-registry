"""每日复检（SKILL.md §5.3）。只改 delist_history，并在 state/checks.jsonl 记录每次检查结果（用于计算连续失败）。"""
import json, datetime as dt, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import registry as R

STATE = R.ROOT / "state" / "checks.jsonl"

def probe():
    try:
        st, _, _ = R.fetch(json.loads((R.ROOT / "registry.json").read_text())["probe_url"])
        return st < 500
    except Exception:
        return False

def history(name):
    if not STATE.exists():
        return []
    return [r for r in map(json.loads, STATE.read_text().splitlines()) if r["name"] == name]

def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    ts = now.isoformat().replace("+00:00", "Z")
    if not probe():
        print("黄页自身网络探测失败，本次作废（不计入、不清零）。")
        return
    STATE.parent.mkdir(exist_ok=True)
    cfg = json.loads((R.ROOT / "registry.json").read_text())
    log = []
    for name, e in R.all_entries().items():
        g2, g3, _ = R.live_check(e, now)
        prev = history(name)
        streak = 0
        for r in reversed(prev):
            if r["g2"]: break
            streak += 1
        down = (not g2) and streak + 1 >= cfg["down_after_failed_checks"]
        rec = {"name": name, "at": ts, "g2": not g2, "g3": not g3}
        log.append(rec)
        reason = "down" if down else ("stale" if g3 else None)
        if reason and not R.is_delisted(e):
            e.setdefault("delist_history", []).append({"from": ts, "to": None, "reason": reason})
            (R.ROOT / "curators" / f"{name}.json").write_text(json.dumps(e, ensure_ascii=False, indent=2) + "\n")
            print(f"下架 {name}：{reason}；{(g2 + g3)[:3]}")
        else:
            print(f"{name}: G2 {'PASS' if not g2 else 'FAIL'}，G3 {'PASS' if not g3 else 'FAIL'}" + ("" if not (g2 or g3) else f"；{(g2+g3)[:3]}"))
    with STATE.open("a") as f:
        for r in log:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
