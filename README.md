# 亚马逊页面优化

`amazon-listing-catalog-workflow` 是 Amazon Listing 页面优化技能，支持 Title、Item Highlight、五点、图片构想与 ALT、属性及 A+ 交接。

本仓库保存 2026-09-08 从本地安装目录导出的当前版本，技能源文件保持原样。入口见 [SKILL.md](SKILL.md)。

## 工作方式

范围确认 → 并行预研 → 第一轮事实与设计初衷提问 → 简报合成 → 多稿独立生成 → 买家评估与事实/规则检查 → 第二轮分歧提问 → 定稿与交付。

产物包括事实台账、竞争取舍表、三通道文案（SAFE / CANDIDATE / HOLD）、购物 AI 答案地图及只读 HTML。运行环境不支持子智能体时，按技能内的降级规则执行。

## 安装与使用

在已配置 GitHub 私有仓库访问权限的环境中：

```sh
git clone https://github.com/HelloYoung2025/amazon-listing-catalog-workflow.git ~/.codex/skills/amazon-listing-catalog-workflow
```

目标目录需尚不存在；已有安装时先自行备份或选择其他位置克隆。

使用示例：

```text
请使用 $amazon-listing-catalog-workflow 启动亚马逊页面优化。
产品链接：[Amazon 产品链接]
先让我选择工作范围，确认后开始。
```

## 文件结构

- `SKILL.md`：入口及编排规则。
- `agents/openai.yaml`：显示名称、默认提示与调用策略。
- `references/`：范围、预研、提问、生成、评审、答案地图、字段分工与品类参考。
- `assets/listing-staff-entry-shell.html`：只读交付模板。

## 配套技能与边界

- A+ 规划交接使用 `amazon-premium-aplus-planner`，本仓库不包含该技能。
- 正式 Bundle、preflight 与发布支持使用 `amazon-listing-publish-gate`，本仓库不包含该技能。
- 默认只做内部方案；不会因此获得 Amazon 或 ERP 的写入权限。
- 字段能力及平台规则应在实际使用时核实。规则示例不替代当前官方要求。

本仓库仅包含可复用技能文件，不包含产品项目资料、账号凭据或本次 Listing 优化成果。
