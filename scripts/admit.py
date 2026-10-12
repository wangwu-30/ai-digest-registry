"""PR 准入：只看 G1（条目）、G2（存活）、G3（14 天内新鲜）。
用法：python scripts/admit.py <base_ref>    （在 PR 的检出目录里运行；环境变量 PR_AUTHOR_ID）
"""
import json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import registry as R

def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, cwd=R.ROOT).stdout

def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    opener = int(os.environ["PR_AUTHOR_ID"]) if os.environ.get("PR_AUTHOR_ID") else None
    changed = [l.split("\t") for l in git("diff", "--name-status", f"{base}...HEAD").splitlines()]
    fails, report = [], []
    for st, *paths in changed:
        path = paths[-1]
        if st.startswith("D") and path.startswith("curators/"):
            fails.append(f"{path}: 不允许删除条目（离开即下架，文件保留）")
        if st.startswith("R") and paths[0].startswith("curators/"):
            fails.append(f"{paths[0]}: 不允许重命名条目文件；改名请新增文件并保留旧文件")
    touched = [p[-1] for st, *p in changed if p[-1].startswith("curators/") and p[-1].endswith(".json") and not st.startswith("D")]
    others = R.all_entries()
    for path in touched:
        name = Path(path).stem
        old = git("show", f"{base}:{path}")
        base_entry = json.loads(old) if old.strip() else None
        errs = R.check_entry(R.ROOT / path, {k: v for k, v in others.items() if k != name}, base_entry, opener)
        if not errs:
            g2, g3, info = R.live_check(json.loads((R.ROOT / path).read_text()))
            errs = g2 + g3
            report.append(f"- {name}: {info.get('title')}，最新一期 {info.get('latest')}" + (f"；词表外话题 {info['unknown_topics']}" if info.get("unknown_topics") else ""))
        fails += [f"{path}: {e}" for e in errs]
    print("## 准入结果\n")
    print("\n".join(report) or "（本 PR 没有改动条目）")
    if fails:
        print("\n### 未通过\n" + "\n".join(f"- {f}" for f in fails))
        sys.exit(1)
    print("\nG1–G3 全部通过。")

if __name__ == "__main__":
    main()
