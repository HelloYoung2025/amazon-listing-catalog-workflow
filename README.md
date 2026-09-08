# 亚马逊页面优化

这是供支持 Skills 的 AI 编程助手读取的指令包，不是可双击运行的程序，也不是粘贴 GitHub 链接便会自动安装的网页应用。

核心能力：Title、Item Highlight、五点、图片构想/ALT、属性内部优化；预研、两轮提问、多稿生成、评审及只读报告。入口见 [SKILL.md](SKILL.md)。

## 推荐安装：Codex

仓库公开可读，不需要 GitHub 账号。需要本地 Git，目标目录尚不存在：

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/HelloYoung2025/amazon-listing-catalog-workflow.git "${CODEX_HOME:-$HOME/.codex}/skills/amazon-listing-catalog-workflow"
```

已有同名目录时不要覆盖，先备份或选择其他目录。安装完成后在下一轮对话中调用；如果技能列表尚未刷新，重开客户端后再检查。

也可把下面完整指令发给 Codex 内置的 `$skill-installer`：

```text
请从 HelloYoung2025/amazon-listing-catalog-workflow 安装技能。
仓库内路径是 .，安装名称必须显式指定为 amazon-listing-catalog-workflow。
调用安装器时使用 --repo HelloYoung2025/amazon-listing-catalog-workflow --path . --name amazon-listing-catalog-workflow
```

**根目录安装注意**：只传仓库首页 URL 会报 `Missing --path for GitHub URL`；只传 `--path .` 而不指定 `--name` 会报 `Invalid skill name`。请使用上面的完整参数。

## ZIP 安装与其他工具

从 [Releases](https://github.com/HelloYoung2025/amazon-listing-catalog-workflow/releases/latest) 下载 `amazon-listing-catalog-workflow.zip`。它的顶层目录固定为 `amazon-listing-catalog-workflow/`，下面直接是 `SKILL.md`、`agents/`、`references/`、`assets/`。

Codex 手动安装：将 ZIP 内这个完整目录放进自己的 skills 目录。不要只复制 `SKILL.md`，也不要再嵌套一层同名目录。GitHub 的 “Code → Download ZIP” 是源码压缩包，目录名通常带 `-main`，不等于本项目提供的安装 ZIP。

其他工具请使用其支持的技能导入方式；普通聊天框上传 ZIP 不等于完成技能注册。目前只实际验证了 Codex 安装器和 ZIP 解压后的包结构，尚未验证 Claude / Cursor 各版本的 UI 导入兼容性。`agents/openai.yaml` 是 Codex 元数据，其他工具是否识别取决于其自身实现。

## 调用

```text
请使用 $amazon-listing-catalog-workflow 启动亚马逊页面优化。
产品链接：[Amazon 产品链接]
先让我选择工作范围，确认后开始。
```

预期先识别产品并给出范围选择；资料不足时先澄清，不会直接声称已完成完整调研。没有子智能体时可顺序执行并声明非独立评审；没有联网能力时使用你提供的页面资料；没有文件写入能力时交付聊天内 Markdown。

## 可选依赖

| 功能 | 本包是否可独立完成 |
|---|---|
| A/B/C/D/F 内部 Listing 优化 | 是，需要相应资料与宿主工具能力 |
| A+ 交接简报 | 是 |
| 完整 A+ / Premium A+ 规划 | 否，需另装 `amazon-premium-aplus-planner` |
| 正式 Bundle / preflight 校验 | 否，需另装 `amazon-listing-publish-gate` |
| Amazon / ERP 在线写入 | 不属于本技能 |

缺少可选技能不会阻塞基础 Listing 工作，也不会伪装成已执行完整 A+ 或发布校验。

## 常见问题

- **找不到技能**：检查 `skills/amazon-listing-catalog-workflow/SKILL.md` 是否直接存在，避免目录多嵌套一层，并检查实际使用的 `CODEX_HOME`。
- **提示目录已存在**：安装器为避免覆盖会主动停止；不是仓库不可访问。
- **读不到 Amazon 页面**：这属于页面访问/资料问题，可提供页面文字或截图继续，不能据此推断安装失败。
- **找不到 A+ / publish-gate**：参见依赖表，本包只对相应功能给出交接或能力缺失说明。

## 维护与发布检查

以下命令用于维护者检查与打包，普通使用者无需安装 Python/PyYAML：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/check_release.py
```

检查会校验 YAML、名称、相对资源链接、安装包目录、模板渲染及解压后文件一致性，并生成安装 ZIP。GitHub Actions 对 push、PR 运行相同检查。每次发布还需在空白临时目录用实际 Codex 安装器安装远程提交；模板和格式通过不能代表文案质量或所有客户端都可用。
