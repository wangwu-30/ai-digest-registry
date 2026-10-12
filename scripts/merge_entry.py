"""合并后由黄页写入 author_id / joined_at，处理 restore（SKILL.md §5.1、§5.3）。
用法：python scripts/merge_entry.py <name> <author_id> <merge_time_utc_Z>"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import registry as R
name, aid, t = sys.argv[1], int(sys.argv[2]), sys.argv[3]
p = R.ROOT / "curators" / f"{name}.json"
e = json.loads(p.read_text())
e.setdefault("author_id", aid)
e.setdefault("joined_at", t)
if e.pop("restore", None) and R.is_delisted(e):
    e["delist_history"][-1]["to"] = t
p.write_text(json.dumps(e, ensure_ascii=False, indent=2) + "\n")
