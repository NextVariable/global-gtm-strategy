# Global GTM Strategy · 海外市场研究与 GTM 战略

[![Validation / 自动验证](https://github.com/NextVariable/global-gtm-strategy/actions/workflows/validate.yml/badge.svg)](https://github.com/NextVariable/global-gtm-strategy/actions/workflows/validate.yml) · [MIT](LICENSE) · [中文](#中文) · [English](#english)

## 中文

帮助产品团队决定出海先进入哪个市场、服务哪类客户、凭什么被选择，以及如何触达首批付费客户。适用于新产品的市场切入，也适用于已有海外业务的增长瓶颈分析。

研究给出目标市场与客户、价值主张、竞争取舍、优先渠道、购买路径和下一步验证。关键建议附来源、反对证据及调整条件；缺少真实购买数据、成本或币种时明确保留未知，不用行业模板补数。本技能负责研究与策略设计，实际获客、销售、投放和实验执行需另行开展。

### 安装与使用

将完整的 [Skill 目录](skills/global-gtm-strategy/)复制到支持 Agent Skills 的客户端。Codex 示例：

```bash
git clone https://github.com/NextVariable/global-gtm-strategy.git
cd global-gtm-strategy
mkdir -p ~/.agents/skills
cp -R skills/global-gtm-strategy ~/.agents/skills/
```

重新加载客户端后调用 `$global-gtm-strategy`。已有同名技能时先核对版本。技能使用客户端已有的搜索、浏览和文件工具；辅助脚本需要 Python 3.10+，仅使用标准库，无需额外服务或密钥。

```text
使用 $global-gtm-strategy。我们做团队会议工具，目前只有云版，
有三个已付款试点，团队能用英语支持，每月只有 40 小时服务产能。
根据我提供的访谈、成本和购买记录，判断先服务哪类客户，
并设计一项最可能改变这个选择的验证。
```

提供有权使用的产品资料、当前决定和资源约束即可。持续研究的业务资料保存在技能目录之外，按客户、产品和项目区分，见[证据与恢复](skills/global-gtm-strategy/references/evidence-and-state.md)。

### 验证与许可证

运行 `python3 scripts/validate.py` 检查结构、账本与数值计算。持续集成覆盖 Linux、macOS、Windows；模拟案例和自动检查不证明真实增长效果。[验证索引](validation/README.md)说明检查范围与已知局限，[架构说明](docs/architecture.md)说明维护边界。

项目采用 [MIT 许可证](LICENSE)。适用的第三方许可证见[许可声明](THIRD_PARTY_NOTICES.md)。

## English

Help product teams decide which international market to enter, whom to serve, why customers would choose the product, and how to reach the first paying customers. Use it for a new product’s market entry or to investigate growth bottlenecks in an existing overseas business.

The research identifies target markets and customers, value propositions, competitive trade-offs, priority channels, buying journeys, and the next validation step. Key recommendations include sources, opposing evidence, and conditions for revision. Missing purchase data, costs, or currencies remain unknown. The skill handles research and strategy design; acquisition, sales, advertising, and experiment execution require separate work.

### Installation and usage

Copy the entire [skill directory](skills/global-gtm-strategy/) into a client supporting Agent Skills. For Codex:

```bash
git clone https://github.com/NextVariable/global-gtm-strategy.git
cd global-gtm-strategy
mkdir -p ~/.agents/skills
cp -R skills/global-gtm-strategy ~/.agents/skills/
```

Reload the client and invoke `$global-gtm-strategy`. Check the version before replacing an existing installation. The skill uses the client’s search, browsing, and file tools. Helper scripts require Python 3.10+ and only the standard library; no additional services or credentials are needed.

```text
Use $global-gtm-strategy. We build a team meeting tool, currently cloud-only.
We have three paid pilots, can provide support in English, and have only
40 hours of service capacity per month. Based on the interviews, costs,
and purchase records I provide, identify the customer segment to serve
first and design a test most likely to change that choice.
```

Provide product materials you are authorized to use, the decision at hand, and resource constraints. For ongoing research, store business data outside the skill directory and separate it by client, product, and project; see [evidence and resumption](skills/global-gtm-strategy/references/evidence-and-state.md).

### Validation and license

Run `python3 scripts/validate.py` to check structure, ledgers, and calculations. CI covers Linux, macOS, and Windows. Synthetic cases and automated checks do not demonstrate real growth outcomes. The [validation index](validation/README.md) describes check coverage and known limitations; [architecture](docs/architecture.md) describes maintenance boundaries.

The project is licensed under [MIT](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.md) for applicable third-party licenses.
