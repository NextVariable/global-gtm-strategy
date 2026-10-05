# 架构与维护 · Architecture and maintenance

可安装单元为 `skills/global-gtm-strategy/`。`SKILL.md` 是入口，`references/` 按决策需要加载市场选择、客户研究、替代方案、商业机会和进入策略；`templates/` 提供输入与交接约定，`agents/` 提供客户端元数据。业务资料应保存在安装目录之外。

The installable unit is `skills/global-gtm-strategy/`. `SKILL.md` is the entry point; references cover market selection, customer research, alternatives, commercial opportunity, and entry strategy, loaded as needed. Templates define inputs and handoffs; agents provide client metadata. Store business data outside the installed skill.

业务脚本只处理账本初始化、只读校验和区间计算，不联网、不执行获客动作。账本校验不判断来源是否真实或建议是否有效；数值结果是情景区间，单位、相关性与现实可行性仍需核对。

Business helpers initialize ledgers, perform read-only checks, and calculate intervals. They do not access the network or execute acquisition. Ledger validation does not assess truth or strategic quality; interval results require checks of units, dependencies, and feasibility.

维护入口为 `scripts/validate.py`，测试集中于 `tests/`。[验证说明](../validation/README.md)记录检查范围与局限。持续集成覆盖 Linux 的 Python 3.10–3.14，以及 macOS、Windows 的 Python 3.12。许可证随安装目录保留。

Maintenance runs through `scripts/validate.py`, with active tests in `tests/`. The [validation notes](../validation/README.md) describe coverage and limitations. CI covers Python 3.10–3.14 on Linux and Python 3.12 on macOS and Windows. Licenses remain bundled with the skill.
