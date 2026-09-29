# 验证记录与未完成边界

## 本次实际执行

- 后端：真实 PostgreSQL 18.4 + pgvector 0.8.2，独立项目数据库，非 SQLite 替代。
- Python：3.12，依赖锁定在 requirements.lock。
- 自动测试：33 项后端测试通过，8 项独立 Swift 核心检查通过，覆盖时间衰减、死亡、重生、重复奖励、用户隔离、并发库存、健康数据、记忆检索、AI 降级、日记、通知重试等。
- Django system check、迁移一致性检查、Ruff 检查。
- Swift 共享核心：实际编译并执行计时、睡眠区间合并、离线奖励和持久化检查。
- Swift 网络/Keychain 层：在 macOS SDK 下执行 typecheck。
- Watch 全部 Swift 源码：语法解析通过；这不等于 watchOS SDK 类型检查或完整构建。
- Xcode project/Info.plist/entitlements：plutil 格式检查。
- 真实 HTTP/JWT：smoke_api.py 创建专用临时账号，验证奖励和凭证轮换后删除账号。
- docker compose config：配置解析通过；容器尚未实际运行。
- 演示 AI 评估：12 个合成场景、A/B/C 共 36 条回复，每个场景 10 条候选记忆，数据与模式明确记录在 evaluation/results。

## 复核发现并修复

- FocusTimer 的 habitID 与 snake_case 编码规则不兼容，导致重启无法读取；已用独立可执行 Swift 回归检查复现并修复。
- 散步开始可能使用旧步数；现要求新鲜 steps_observed_at，并在 Watch 开始前先同步。
- 未结束的跨日散步会话可阻挡后续操作；Watch 提供取消会话入口。
- 只有睡眠更新不能让旧步数看起来“刚同步”；单独保存步数观察时间。
- 关闭 AI 健康摘要权限后，历史 AI 回复可能把先前健康数据带回上下文；近期上下文只包含用户原话。
- 非对象 JSON、无效记忆类别会造成 500；现在统一返回 400。

已进行一次独立代码复核并收到上述部分反馈；复核代理随后因额度限制停止，未完成全仓审查。后续修复与最终检查由主执行者完成，不将其描述成完整独立审计。

## 仍需外部条件

| 项目 | 当前状态 | 下一步 |
|---|---|---|
| Watch 完整构建 | 没有 Xcode/watchOS SDK | 安装 Xcode 后运行工程或 CI |
| Swift XCTest | 本机缺少 XCTest 框架 | Xcode 环境执行 swift test；已有无 XCTest 的核心检查 |
| 真机 HealthKit | 无已连接授权设备 | 你配对手表并授权，对照健康 App |
| 真实 AI/embedding | 无 API key | 配置服务、预算后运行 --live |
| APNs 实际投递 | 无签名 key/设备凭证 | 配置 capability 和 APNs，真机测试 |
| Docker 镜像构建 | Docker 应用无法启动 | 修复 Docker 后运行 compose |
| CI 云端执行 | 未创建远程仓库/推送 | 你提供仓库并授权推送后运行 |
| 线上部署 | 无云主机/域名 | 按 DEPLOYMENT.md 配置并验证 |
| 研究结论 | 仅合成演示评估 | 扩充独立样本、真实模型、人工评分 |
| 作品集真机素材 | 尚未录制 | 按 DEMO.md 拍摄 |

## 明确的第一版限制

- 进化采用学习/活动累计规则，尚未实现复杂的四维行为归一化模型。
- 离线 UI 按本机时间预览衰减，并顺序预测待同步操作；服务器仍按接收时间结算。设备时钟偏差、跨日或临界死亡附近可能产生冲突，不能声称离线状态与服务器始终完全一致。
- FocusTimer 支持本地暂停/恢复；服务器 focus 会话接口是另一条在线时长校验路径，第一版 Watch 使用用户确认完成的幂等 complete 操作。
- 记忆删除会移除存储向量，但近期用户对话可能仍包含同一事实；如需完整遗忘所有历史，当前可删除账号。独立聊天历史删除接口可后续补充。
- 不保证模型绝不产生不当内容；有提示约束、结构验证、有限医疗短语过滤和降级，需要真实模型评估。
- API 访问令牌退出后最多仍有效 30 分钟；refresh 被撤销。删除账号则访问验证失效。
- DRF 限流是进程内缓存，公开多实例部署前需要共享限流或代理层保护。
- 暂无 App Store 发布素材和经验证的最终 App Icon；不声称已具备全部上架要求。

## 可复现命令

```sh
scripts/check.sh
.venv/bin/python scripts/smoke_api.py
scripts/manage.sh evaluate_ai
swiftc -frontend -parse watch/HabitPet/*.swift watch/HabitPet/Core/*.swift
docker compose config --quiet
```

详细日志保存在 work/，开发状态数据库也在 work/pgdata，请不要把整个 work/ 当作可随意删除的临时目录。

## 最终执行摘要

`./scripts/check.sh`：Django 检查无问题、无遗漏迁移、Ruff 通过、33 passed、8 项 Swift 检查 PASS。真实 HTTP 冒烟通过并删除临时账号。本地 API 保持运行于 127.0.0.1:8000，本地数据库监听 127.0.0.1:55439。
