# 证据、隔离与恢复

## 项目边界

一个运行目录对应且只对应 `client/product/project` 三元组。建议用户数据目录 `growth-workspaces/<client>/<product>/<project>/`，而非技能安装目录。ID 采用无个人信息的稳定 slug；产品改名不换 ID。`identity.json` 固定三元组及 schema_version=1，所有业务记录携带相同 identity。读取之前核对身份，不扫描邻居客户或默认共享 `.agents/product-marketing.md`。既有背景只有确认归属后才能导入。脚本拒绝目录及固定业务文件的符号链接；它是防误读检查，不是操作系统权限沙箱。敏感原始访谈、CRM、付款材料保存在用户允许的位置，分享时脱敏；不能为了完成研究要求上传隐私数据。

同产品不同项目的共享需明确授权，保留原记录标识、导入日期、用途及重新核验结果；复制引用不能创造第二个独立来源。整个技能包固定五个独立 Skill：本 Skill、产品定位与增长内容、产品发布与渠道获客、销售/转化与客户增长、增长实验/执行与复盘。后四个尚未实现，共享此约定而非共享无边界文件夹。

## 最小运行资料

初始化产生以下文件。可以只完成有关记录，不为了填满模板研究无关字段。

| 文件 | 内容及修改方式 |
|---|---|
| identity.json | 不可变身份；不得就地换客户 |
| context.json | goal、product、constraints、facts(只引用经核验观察 claim ID)、observations(仅看到材料陈述的claim ID)、assumptions(只引用假设 claim ID)、user_statements(原话/日期/限制) |
| evidence.jsonl | 追加来源记录，旧来源不覆盖；更新价格添加新 evidence，标记 supersedes |
| claims.jsonl | 追加观察/推断/假设/建议，纠正时新 ID + supersedes；保留原判断 |
| decisions.jsonl | 追加版本、依据/反对/撤回条件，supersedes 指向上一决策 |
| state.json | checkpoint：阶段、completed、next_action、open_questions、budget/consumption、updated_at、inputs_digest；可替换当前 checkpoint |
| handoff.md | 最新决策交接，明确身份与版本，旧决策仍在 ledger |

每次有新材料或改变判断就保存。恢复：核对 identity → 校验文件 → 阅读 context/state → 找未被 supersedes 的决策与证据 → 检查价格、功能、法规等是否需刷新 → 从 next_action 继续。`inputs_digest` 记录决定本轮判断的输入文件哈希；hash 改变只是复查提醒，不证明资料真实。中断之前记录已经做过的调用，不重复“重新开始”。

JSONL 每行一个对象；必需字段及可运行实例见 [records.json](../templates/records.json)。空 ledger 是初始化状态，不是完成结果。结束必须有至少一条决策及一条可执行 next_validation。

文字字段使用字符串，不用布尔值或数字充当核验说明、推理或验证任务。limits、unknowns、withdraw_if、completed、open_questions 使用字符串列表；constraints、budget、consumption、inputs_digest 使用对象。next_validation 的六个字段使用自包含文字；需要详细配置时可在文字中定位项目内附件。字段类型正确仍不代表内容具体或来源可靠。

## 证据分类与溯源

每条 evidence 保存 id、identity、source(url 或用户授权本地路径)、acquired_at(ISO 日期)、material_date(日期或 null+理由)、region、source_kind、origin_group(原始材料/事件稳定标识)、locator(章节/页码/行/时间戳)、excerpt(必要短摘录)、limits、status(current/historical/unverified/conflicted)、可选 valid_until/supersedes。本地材料不是“公网可查”，需注明由谁提供及审计位置。原始网页不可访问时保留访问错误，转载可提供线索，不能冒充读过原文。

企业自述适合核对其公开产品和自报指标，不独立证明客户价值；第三方流量是估计且受覆盖/地区/模型影响，不能换算实际客户；评论有选择偏差，不能当代表性普查；访谈口头意向只是意向；日志中的使用需定义事件、队列、重复用户和时间窗；付款需币种、订单状态、退款、续费/一次性、样本授权，不能把预售当留存。没有统一证据等级可自动决定所有问题：产品功能查文档/试用，购买看成交，工作流看过去行为，各自限制不同。

来源同域不必同事件，异域也可能同一转载；用 origin_group 去重并人工检查共同上游。主动追问“最能证明推荐错误的材料是什么”，检索失败写已检查范围，不写不存在。时间冲突优先比较同地区同套餐同口径最新直接来源，解释旧材料为何不同；新不一定正确，若可信来源互相冲突保留冲突并指出决定性补证。过期价格只能描述历史，不作为当前 ROI 基础。没有发布日期不编造，获取日期不能替代材料日期。

## 四类 claim 与决策

`observation`：来源陈述或直接观察，sources 非空，措辞限于来源范围（如“企业在年报中报告”）。`inference`：premises/sources 非空，写 reasoning 和限制，不升级为来源事实。`hypothesis`：未经验证的可证伪命题，写 validation；可无来源但必须明确待验证。`recommendation`：依赖已记录 premises，写 reasoning 和撤回条件，不当事实。每条记录 text、sources、premises；一个claim只表达一项会影响决策的命题，来源应与该命题相匹配，不能把无关材料全部拼成O1再让所有结论引用它。来源陈述与推断不要混在一个观察中。推断与建议可引用假设，但必须披露条件。只允许引用先前 claim，防循环。supersedes 只保留追踪关系，不抹去旧判断。

decision 包含 status(recommend/provisional/defer)、claims、counter_evidence（找到则 ID，未找到也须解释已查范围）、unknowns、withdraw_if、next_validation(object/action/observable/criterion/resource_limit/branches)、supersedes。next_validation各字段必须自包含具体对象、动作、可观察行为、判定与资源，不能只写“见正文/按上述”作为唯一内容；共享账本要能单独交给第五个Skill执行设计。正文可以引用同一任务而不重复长篇。推荐必须逐条回到来源或假设；关键信息不足时状态 provisional 或 defer，不能用小数评分掩盖。

共享 facts 不是全部 observation 的集合。只有已核验且来源状态 current 的观察才能进入，并须在 claim 中提供 verification={method,checked_at,scope}，说明核验的是功能、付款还是“企业在某页如此陈述”；不能扩大到企业陈述的效果本身。未核验来源、历史价格、模拟资料和仅读冻结摘要的观察放 context.observations，保留限制，不传播为共享业务事实。模拟测试身份可记录模拟观察，但仍不进入业务 facts。

更新后，共享 facts 不得继续引用已被 supersedes 的 claim 或依赖已替代的 evidence；旧记录仍可留在历史账本和观察列表中。需重新核验且登记新命题，不能仅改 verification 日期。observations 只收 observation，假设留在 assumptions。

上述限制适用于整条依赖链，不仅是 facts 的直接 sources。中间观察不能洗掉历史、过期、未核验、冲突或模拟来源的限制；依赖推断、假设或建议的结论不得作为已核验观察传播。核验日期不得早于依赖链上任一证据的获取日期。需要表达推导结论时登记 inference，而不是给它添加 verification 后放入 facts。

脚本检查字段、日期、同身份、ID唯一/引用有效/引用顺序、过期来源与决策依赖提醒；不会判定摘录真实性、原始来源独立性、支持关系、因果、决策是否正确。输出 execution_readiness=not_assessed；--complete 仅要求账本结构的交付字段，不能证明下一验证可执行。资源未定或内容占位时，人工审阅标记未就绪。任何通过日志都要写“结构检查通过”，不要写“市场验证通过”。

恢复时，当前决策若经中间 claim 依赖已替代或非当前证据，脚本会给 active decision 提醒。需要人工判定它描述的是合法历史还是当前判断的失效基础；不能仅因结构检查通过就继续执行。新材料改变关键条件时追加新决策并 supersedes 旧版；仅改变无关字段则说明为何原结论仍适用。
