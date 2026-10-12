# AI 日报黄页

收录每个人用自己的 agent **收集、重排、发布**出来的 AI 日报网站。不同人处理后的信息本身就有价值：你可以直接读，也可以让自己的 agent 把它们当作信息源。

**目录页：** https://wangwu-30.github.io/ai-digest-registry/

## 怎么浏览

- 打开上面的目录页：每份日报的标题、话题、语言、最新一期和状态，都是生成时从各站点实时读取的。
- 想订阅：每份日报都有 Atom（`feed.xml`）和 JSON（`latest.json`），目录页里有链接。
- 让 agent 订阅：在你的日报配置里加一个 `type: registry` 的来源（daily-skill SKILL.md §5.4），它会按话题挑选未下架的日报。

## 怎么加入

先用 [daily-skill](https://github.com/wangwu-30/daily-skill) 让你的 agent 搭好日报。然后对它说一句：

> 把我的日报加入黄页 https://github.com/wangwu-30/ai-digest-registry

agent 会 fork 本仓库，新增 `curators/<名字>.json`，开 PR。条目只有三个必填字段：

```json
{"name": "jane-ai-daily", "url": "https://jane.github.io/ai-daily/", "author": "jane"}
```

可选：`people`（你信任的人）、`opml`（只有你公开了源清单时才填，**不是必须**）。不限来源类型：RSS、社媒（小红书、即刻……）、API 都行，黄页只看你的产出。

### 准入只看三项（CI 自动检查）

1. **条目**：符合 `schema/curator-entry.v1.json`；名字等于文件名，名字和网址都没被占用；`url` 等于日报 `latest.json` 里的 `curator.url`。
2. **存活**：`latest.json`、`index.json`、最新一期 `data.json`、`feed.xml` 都能访问，且通过 schema 和内容检查（栏目一致、来源链接合法、没有重复条目）。
3. **新鲜**：最近一期在 14 天内发布。

其它检查只做报告，不拦截。

### 下架与恢复

- 每天北京时间 9:17 复检。存活检查连续 3 次失败下架（`down`），超过 14 天没更新下架（`stale`）。条目文件保留，名字不会被别人占用。
- 恢复：日报恢复更新后，对 agent 说「恢复我在黄页的条目」，它会开一个只加 `"restore": true` 的 PR。
- 只有当初提交的 GitHub 账号（`author_id`）能修改或恢复自己的条目。

## 单一真相源

本仓库只存条目（`curators/`）和黄页自己的配置（`registry.json`、`topics.json`、`aggregators.json`）。话题、语言、标题、更新时间都不复制，目录页每次从各日报站点重新生成。

## 开发

```
pip install -r requirements.txt
pytest -q tests                               # schema、22 个日报反例、条目反例
python scripts/admit.py origin/main           # 对当前分支的改动跑 G1–G3
python scripts/build_site.py _site            # 本地生成目录页
```

规则来源：daily-skill SKILL.md §5、ACCEPTANCE.md §R（G1–G3）。schema 文件逐字节复制自 daily-skill，hash 见 SKILL.md §4.3。授权：MIT。
