# API 合同

除 `/healthz/`、注册、登录、刷新凭证外均需 `Authorization: Bearer <access>`。请求体必须是 JSON 对象。返回 JSON，错误为 DRF 的字段错误或 `detail`。常见状态：400 输入错误、401 重新登录、404 不存在或不属于当前用户、409 状态冲突、429 请求频率超限。

| Method | Path | 用途 |
|---|---|---|
| POST | /api/auth/register/ | username/password，返回 access、refresh |
| POST | /api/auth/login/ | username/password，返回 access、refresh |
| POST | /api/auth/refresh/ | refresh；轮换并撤销旧 refresh |
| POST | /api/auth/logout/ | 撤销 refresh；已发出的 access 最长仍有效 30 分钟 |
| GET | /api/today/ | 结算时间衰减并返回完整快照 |
| POST | /api/actions/ | 幂等游戏操作 |
| GET/POST | /api/habits/ | 列出/创建习惯 |
| GET/PATCH/DELETE | /api/habits/{id}/ | 修改/归档习惯 |
| POST | /api/health/sync/ | 当天步数、睡眠摘要 |
| GET/PATCH | /api/profile/ | 时区、性格、健康/记忆开关、睡眠目标、安静时段 |
| DELETE | /api/account/ | 删除账号及关联数据 |
| GET | /api/pet/generations/ | 每代档案 |
| DELETE | /api/sessions/{id}/ | 取消未完成的 focus/walk 会话 |
| POST | /api/pet/chat/ | message；返回 emotion/message/suggested_action/urgency/source |
| GET/POST | /api/memories/ | 查看/手动保存记忆 |
| DELETE | /api/memories/{id}/ | 删除记忆及向量 |
| GET/POST | /api/diary/ | 最近日记/幂等生成今天日记 |
| GET | /api/reminders/ | 今日未确认提醒 |
| POST | /api/reminders/{id}/ack/ | 确认已读 |
| POST/DELETE | /api/devices/ | APNs token 注册/解除 |

## 操作

原计划中的 feed/complete/progress/interact 独立写接口统一为 `/api/actions/`，避免 Watch 离线重试走不同幂等路径。所有调用共享同一个所有者行锁。

```json
{
  "id": "一个UUID",
  "generation": 1,
  "kind": "complete",
  "occurred_at": "2026-09-29T10:00:00Z",
  "payload": {"habit_id": 1}
}
```

可用 kind：`feed`、`water`、`play`、`complete`、`progress`、`rebirth`、`walk_start`、`walk_finish`、`focus_start`、`focus_finish`。

- progress：payload 为 `habit_id`、正整数 `amount`。
- complete/focus_start：payload 为 `habit_id`。
- 其余操作 payload 为空对象。
- generation 必须匹配当前宠物；重生后旧代操作不会应用到新宠物。
- 相同用户相同 UUID 和内容返回原结果，不再次执行。
- 重用同一个 UUID 改内容返回 409。
- 每日奖励由 HabitLog 唯一约束 + 事务 + RewardLedger 保证。
- 同一用户的状态修改串行执行，跨用户独立。
- 重试结果可能是当时的快照，清空队列后必须重新 GET today 获取最新状态。
- 拒绝的操作不记录为成功。可修正前置条件后重试相同操作。
- occurred_at 仅审计和有效期校验；不允许客户端设置 XP、库存或历史结算日期。

## Health sync

```json
{"steps": 6521, "sleep_minutes": 412, "observed_at": "2026-09-29T10:00:00Z"}
```

steps 和 sleep_minutes 均可省略或为 null，表示未知/不更新；真实 0 与未知不同。observed_at 默认服务器当前时间，必须属于用户时区的今天，不能明显在未来。旧于当前 observation 的摘要不覆盖新数据。

steps_observed_at 单独记录有真实步数的摘要时间，散步开始要求 5 分钟内步数基线。步数降低可以更新显示，但不会回收已领取档位，也不会再次发同档奖励。

## 数据限制

- 只支持 daily 习惯频率。
- habit target 1–10000；reward_amount 1–100。
- 聊天 1–1000 字符；AI 回复 1–160 字符。
- 记忆最多 500 字符；1536 维向量；检索过滤用户和 embedding 模型。
- 凭证、健康摘要、记忆均不得放入 URL 查询参数或公开日志。
- 服务端存储的 HealthDailySummary 在实现中命名为 Daily，同时保存每日水量和奖励状态。
