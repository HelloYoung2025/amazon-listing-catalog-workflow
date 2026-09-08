# 亚马逊页面优化 · 完整 Skill 套件

一个日常入口，三套配套 Skill 一起安装：

| Skill | 用途 | 随包文件数 |
|---|---|---:|
| [amazon-listing-catalog-workflow](skills/amazon-listing-catalog-workflow/SKILL.md) | 统一入口：预研、提问、多稿生成、买家评审、Listing 成品 | 11 |
| [amazon-premium-aplus-planner](skills/amazon-premium-aplus-planner/SKILL.md) | A+ 模块、视觉简报、ALT、制作与验收 | 6 |
| [amazon-listing-publish-gate](skills/amazon-listing-publish-gate/SKILL.md) | Listing / A+ Bundle 校验、协调器、迁移与只读报告 | 74 |

全部 **91 个 Skill 文件**在 `skills/`，含配套参考、模板、脚本及合成测试样本。
日常只需要记住 `$amazon-listing-catalog-workflow`，由它按工作范围调用另外两套。

## 2026-09-08 完整性修复

首次提交 `e9302b1` 只包含主入口的 11 个文件，没有 A+ 规划器和发布校验器的 80 个文件。
因此单做部分 Listing 创作可以开始，但 A+ 和正式校验无法按文档完整继续。
这是**发布范围遗漏依赖**，不是 GitHub 传输丢文件。

本次补齐依赖并改为标准多 Skill 目录；原三套 Skill 内容保持与发布时的本地安装源逐字节一致。
旧的“把整个仓库直接 clone 到某一个 Skill 目录”安装方法已废止，请用下方完整安装。
此仓库是公开仓库，下载不要求 GitHub 登录或私有仓库权限。

## 最简单的安装方式：把这段话发给 Codex

```text
请从公开仓库 https://github.com/HelloYoung2025/amazon-listing-catalog-workflow
安装完整的亚马逊页面优化 Skill 套件，而不是只安装主入口。
请先把仓库下载到 Skill 安装目录之外，阅读 README，使用 scripts/install.py 安装，
然后用 scripts/check_package.py --installed-root <实际安装目录> 验证三套 Skill。
如果已经安装了旧版，先说明将替换哪三套以及备份位置，经我确认再使用 --replace。
不要上传或操作我的 Amazon 后台。
```

安装完成后，下一轮即可调用。若当前客户端尚未刷新 Skill 列表，打开一个新任务再试。

## 终端安装（Python 3.10+、Git）

macOS / Linux，在你平常保存项目的目录执行，**不要在现有 Skill 目录内部克隆**：

```sh
git clone https://github.com/HelloYoung2025/amazon-listing-catalog-workflow.git amazon-skills-source
cd amazon-skills-source
python3 scripts/check_package.py
python3 scripts/install.py
```

默认目标为 `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）。
也可以指定其他客户端实际支持的 Skill 根目录：

```sh
python3 scripts/install.py --dest /absolute/path/to/skills
python3 scripts/check_package.py --installed-root /absolute/path/to/skills
```

脚本只安装上述三个目录，不安装 README、Git 元数据或发布工具；不下载其他依赖、不调用模型、不访问 Amazon。
安装前先验证文件清单、SHA-256 和 Skill 引用，安装后再次验证。缺一套、缺文件或文件损坏都会失败退出。

### 已装过旧版 / 首次不完整版本

仍然从 **Skill 目录之外的一份新克隆**执行：

```sh
python3 scripts/install.py --replace
```

不带 `--replace` 时，只要三个目标中任意一个已存在就会拒绝修改，避免半安装。
带此参数时，脚本先备份现有的三个目标目录，再安装完整套件；其他 Skill 不动。
备份位于 Skill 根目录的同级 `amazon-skills-backup-*` 目录，完成后会打印精确位置。
旧的 Git 克隆和用户自改文件也会保留在该备份中，不会静默合并旧改动。
回滚时先把新装的三个目录移到别处，再将备份中的同名目录移回；备份只含更新前存在的目录。

### 用 Codex 内置 Skill Installer

可以明确要求它一次安装三个路径：

```text
仓库：HelloYoung2025/amazon-listing-catalog-workflow
路径：
skills/amazon-listing-catalog-workflow
skills/amazon-premium-aplus-planner
skills/amazon-listing-publish-gate
```

不要只提供其中一个路径；不要只下载 SKILL.md。内置安装器不会自动解析本套件的跨 Skill 依赖。
已有同名安装时，优先使用上方带备份的升级方法。

## 开始优化另一个产品

```text
请使用 $amazon-listing-catalog-workflow 启动亚马逊页面优化。
产品链接：[Amazon 产品链接]
附件：[可选：规格、后台截图、历史问答]
先让我选择工作范围，确认后开始。只做内部方案，不改后台。
```

流程：范围确认 → 并行预研 → 第一轮事实与设计初衷提问 → 简报合成 →
多稿独立生成 → 买家评估与事实/规则检查 → 第二轮分歧提问 → 定稿与只读 HTML。

本套件只带 Skill 文件，不包含模型、浏览器、网页搜索、账号权限或图片生成服务。
运行环境需要提供相应能力；没有子智能体时按 Skill 声明单智能体降级，来源无法访问时标记缺口。
安装完整不等于这些外部能力可用，也不等于获得 Amazon 发布授权。

## 可复现检查

```sh
python3 scripts/check_package.py
python3 -B -m unittest discover -s tests -v
python3 -B -m unittest discover -s skills/amazon-listing-publish-gate/tools/listing/scripts -q
python3 -B -m unittest discover -s skills/amazon-listing-publish-gate/tools/aplus/scripts -q
```

原有 Listing 149 项 + A+ 144 项测试检查本地契约；新增测试检查缺依赖、文件损坏、完整安装、覆盖保护和恢复。
GitHub Actions 对仓库内容与一次干净安装执行检查。清单是完整性基线，不是第三方签名或商品事实证明。
维护者改动 Skill 时需从经核验的完整源同步清单，并再次执行测试，不能为使检查变绿而删掉缺失项。

## 数据与权限边界

- 仅包含可复用 Skill 文件，不包含产品项目资料、账号凭据、实际后台截图或客户问答。
- `fixtures*` / `integration_fixtures`、测试内产品编号、证据、审批与回执均为**合成测试数据**。旧路径和旧日期用于契约测试，不是当前商品、平台规则或真实发布证明。
- 默认只读；`publish-gate` 的 PASS 只代表本地合同一致，不等于真实授权、事实正确、最新规则合规或线上页面通过。
- 不含 Amazon 自动上传工具；实际发布需要独立、明确的授权及回读。
