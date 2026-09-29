# HabitPet 手把手操作指南

## 先看结论

项目已放在 `/Users/a33/Downloads/virtualpet`。后端、数据库迁移、游戏规则、AI/记忆适配、Watch 源码、离线队列、实验工具和部署文件均在此目录。

**尚不能视为已上架成品**：此 Mac 没有完整 Xcode/watchOS SDK；Docker Desktop 启动失败；未提供真实模型密钥、APNs 密钥或云账号。已使用本机独立 PostgreSQL/pgvector 验证后端，使用 Swift 命令行验证共享核心。完整 Watch 构建、真机、远程通知及真实模型效果需要后续验证。

## 1. 本机直接启动后端（当前电脑）

打开“终端”，复制：

```sh
cd /Users/a33/Downloads/virtualpet
.venv/bin/python scripts/local_db.py start
scripts/manage.sh migrate
scripts/dev.sh
```

最后一个窗口保持打开。浏览器打开 `http://127.0.0.1:8000/healthz/`，看到 `{"status":"ok"}` 表示服务可达。

若提示 8000 已占用，可能是服务仍在运行；先访问上述地址，不必重复启动。也可以使用 `DEV_BIND=127.0.0.1:8001 scripts/dev.sh`。

### 验证真实操作闭环

另开一个终端：

```sh
cd /Users/a33/Downloads/virtualpet
.venv/bin/python scripts/smoke_api.py
```

它自动创建自己的临时账号，完成习惯、重复提交、喂食、刷新登录凭证，再删除该临时账号。成功输出 PASS。

### 建立自己的演示账号

Watch 登录页可直接勾选“创建新账号”。若要提前建立 demo 账号：

```sh
scripts/manage.sh seed_demo
```

首次会显示随机密码，请自己保存。再次运行不会重置已有密码。忘记密码：

```sh
scripts/manage.sh changepassword demo
```

## 2. 在另一台电脑安装

需要 Python 3.12 或更新的兼容版本、PostgreSQL 18 和 C 编译工具，或 Docker Desktop。

```sh
cd /你的路径/virtualpet
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
python3 scripts/create_env.py
.venv/bin/python scripts/local_db.py start
scripts/manage.sh migrate
scripts/dev.sh
```

`local_db.py` 只建立项目内 `work/pgdata` 数据库，监听本机 55439 端口，不启动或修改系统已有集群。源码编译 pgvector 使用官方发布包，需联网。它使用本机开发 trust 认证，**不得拿这套本地集群直接对公网开放**。

Docker 恢复正常后，也可：

```sh
python3 scripts/create_env.py
docker compose up --build
```

这是不同数据库，Docker 数据保存在名为 pgdata 的卷中。本机 `work/pgdata` 与 Docker 卷不会自动互相迁移。

## 3. 在 Xcode 打开 Watch App

这是目前最重要的人工准备步骤。

1. 从 App Store 安装完整 Xcode，首次打开并完成附加组件安装。
2. 在 Xcode → Settings → Platforms/Components 中安装 watchOS 模拟器组件。
3. 打开项目中的 `watch/HabitPet.xcodeproj`。
4. 选择 HabitPet target → Signing & Capabilities。
5. 登录自己的 Apple Account，选择 Team。
6. 把 `com.example.habitpet` 改成自己的唯一 Bundle Identifier。
7. 检查 HealthKit capability 存在。项目仅申请读取，不写入健康记录。
8. 选择 Apple Watch 模拟器，再按运行按钮。
9. 注册账号并填写后端地址。

项目最低部署版本暂设 watchOS 10。可根据你的设备版本调整；完整编译必须在安装 Xcode 后再执行，当前不能保证没有 SDK 特定问题。

### 后端地址如何填

- 模拟器通常可尝试 `http://127.0.0.1:8000`；若不可达使用 Mac 的局域网名称。
- 真机上的 `127.0.0.1` 指向手表自身，不能指向 Mac。
- 真机推荐填写部署后的 HTTPS 域名。
- 局域网开发：在 `.env` 的 `ALLOWED_HOSTS` 加上 Mac 的 `.local` 主机名，使用 `DEV_BIND=0.0.0.0:8000 scripts/dev.sh`，Watch 与 Mac 在可互通网络，再填写 `http://你的Mac主机名.local:8000`。
- 防火墙提示时由你决定是否允许局域网访问。不要把开发服务器映射到公网。
- 项目允许本地网络 ATS 例外，不放开所有公网 HTTP。若局域网 IP 被系统拦截，优先使用 `.local` 名称或 HTTPS。

### 第一次真机验收顺序

- 创建“日语学习 30 分钟”，先用手动确认完成验证流程。
- 确认获得食物 ×1，点击喂食，确认食物归零、饱腹上升。
- 快速重复点击，确认没有重复奖励。
- 开始专注，离开 App 后回来，检查倒计时；暂停后时间不减少。
- 关闭网络，完成另一个习惯，再喂食；重启 App 检查待同步操作仍在。
- 恢复网络，点击刷新，确认库存一致。
- 如出现冲突，界面保留队列并提供“放弃首个操作”，不会静默丢弃。
- 点击健康同步，亲自选择读取权限。没数据不会被当作“睡眠为零”。
- 开始散步先同步当前步数；完成时再次同步。旧会话可以取消。

## 4. 接入真实 AI

默认 `AI_MODE=demo`，无需密钥，也不会花费模型费用。演示向量是词元哈希，**不是语义 embedding**。

编辑项目 `.env`：

```dotenv
AI_MODE=live
AI_BASE_URL=https://你的兼容服务/v1
AI_API_KEY=自己填写
AI_MODEL=支持JSON-Schema结构化输出的模型名称
EMBEDDING_MODEL=支持1536维输出的embedding模型名称
```

服务须支持 `/chat/completions` 的 JSON Schema 和 `/embeddings` 的 `dimensions=1536`。不是所有“兼容”服务都实现这两项。API key 只放后端，不放 Watch，不提交 Git。

修改后重启后端。聊天回复应标记 live；若服务失败，会使用规则 fallback。请检查日志中的错误类别，确认不是一直在降级。

设置页面的“允许 AI 使用健康摘要”默认关闭；“长期记忆”也默认关闭。只有你开启后才生效。

演示模式用“记住：……”保存明确偏好。live 模式还会尝试从用户原话提取长期信息，只有能在原文找到证据片段才保存。该机制仍需人工评估，不代表推断永远正确。

从 demo 切换 live 后，检索会按 embedding 模型标识过滤，避免混合不兼容向量。已有记忆需运行 `scripts/manage.sh reembed_memories --live` 重新生成向量；这会调用付费接口，先检查预算。

## 5. 通知

### 无需 APNs 的本地提醒

在 Watch 设置中授权通知，可以安排本地 19:00 提醒；专注计时结束也使用本地通知。通知权限只能由你在设备上操作。

### AI 远程提醒

后端 `scripts/manage.sh run_jobs` 每次处理提醒和晚间日记；部署后 jobs 服务每 15 分钟运行。

未配置 APNs 时，提醒保存在 App 收件箱，打开“日记与记忆”时拉取；这不等于后台远程通知。

若启用 APNs：

1. 在 Apple 开发者账号为应用启用 Push Notifications，在 Xcode 添加此 capability。
2. 创建 APNs signing key，保存在服务器的私有路径。
3. 设置 `.env` 的 `APNS_KEY_PATH`、`APNS_KEY_ID`、`APNS_TEAM_ID`、`APNS_TOPIC`。
4. APNS_TOPIC 必须等于实际 Watch Bundle ID。开发签名使用 `APNS_SANDBOX=1`。
5. 若用 Docker，将密钥只读挂载到 api/jobs 容器，环境变量填容器内路径。
6. Watch 登录后点击“注册远程提醒”。
7. 再运行后台任务并查看日志，最后在真机确认收到。

代码有重试、退避、设备失效处理与 collapse-id；极端网络不确定性下可能重复投递，不承诺严格 exactly-once。系统也不保证每条通知立即展示。

## 6. 测试与评估

```sh
scripts/check.sh
scripts/manage.sh evaluate_ai
```

结果位于 `evaluation/results/`：

- `report.json`：模式、模型标识、Recall@K、限制。
- `responses.json`：三组系统的实际输出。
- `retrieval.json`：各场景检索结果。
- `human-ratings.csv`：打乱顺序的人工评分表。
- `blind-key.json`：评分后再查看组别映射。

当前 12 个场景只是合成冒烟测试。演示检索分数高不能证明 pgvector 或 LLM 提高用户体验，更不能用于论文结论。

配置真实模型后：

```sh
scripts/manage.sh evaluate_ai --live
set -a; . ./.env; set +a
.venv/bin/python scripts/judge_responses.py --live
```

这两条会消耗 API 额度。先扩充独立测试集、标注正确记忆，再做人工盲评。模型评分不能替代人工评分。

## 7. 谁负责什么

| 任务 | 已由代码完成/可继续协助 | 必须你办理 |
|---|---|---|
| 后端规则与接口 | 实现、迁移、测试、排错 | 体验奖励节奏 |
| Watch 工程 | SwiftUI、服务层、离线队列、测试源码 | 安装 Xcode、登录 Team、设备配对 |
| HealthKit | 读取、睡眠去重、每日摘要 | 健康权限与真实数据 |
| AI | 模型适配、上下文、记忆、失败降级 | 模型账号、密钥、预算 |
| 远程通知 | APNs 发送与重试代码 | 开发者能力、签名 key、设备验证 |
| 部署 | Docker、反向代理配置、操作文档 | 云主机/域名/费用与登录 |
| 研究评估 | 场景、脚本、报告生成 | 人工评分、参与者同意 |
| 求职展示 | README、架构、演示脚本 | 真机截图、实际演示录像 |

## 8. 日常停止与备份

在后端运行窗口按 Control-C 停止 API。

```sh
.venv/bin/python scripts/local_db.py stop
```

数据库仍在项目目录，停止不会删除。不要删除 `work/pgdata`，那里有本机数据。

备份示例（本机开发）：

```sh
pg_dump -h 127.0.0.1 -p 55439 -U habitpet -Fc habitpet > work/habitpet.backup
```

备份可能含健康摘要、聊天和偏好，只保存在你控制的地方。恢复先对新建空数据库测试，不直接覆盖已有数据。
