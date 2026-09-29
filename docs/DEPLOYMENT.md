# 部署操作清单

部署配置已准备，尚未登录云平台、开通付费资源、修改 DNS 或发布。

## 先满足条件

- 一台能运行 Docker Compose 的 Linux 主机。
- 一个由你控制并指向主机的域名。
- 服务器 80/443 端口开放；不要公开数据库端口。
- `.env` 填写强随机 SECRET_KEY、DB_PASSWORD、`DOMAIN=pet.example.com`、`ALLOWED_HOSTS=pet.example.com`。
- Docker 镜像标签已固定 pgvector 0.8.2 / PostgreSQL 18，运行前确认镜像可拉取；当前 Mac 未实际完成 Docker 启动验证。

## 操作

```sh
python3 scripts/create_env.py
# 编辑 .env，填写自己的域名和凭证
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up --build -d
docker compose logs --tail=100 api jobs
```

Caddy 自动处理 HTTPS。API 只通过内部网络交给 Caddy，原始宿主机 8000 绑定 127.0.0.1。API 信任的 forwarded-proto 必须仅由此可信代理设置，不能另将 API 直接公开。

检查：`https://你的域名/healthz/`，然后用 `scripts/smoke_api.py --url https://你的域名` 做一次真实账号临时冒烟检查。

## 生产前需要补验

- 初始迁移需能 CREATE EXTENSION；托管数据库可由管理员提前安装 vector。
- 示例 Compose 使用一个数据库角色便于启动。公开长期服务应拆成迁移角色和最小权限运行角色，再做权限验证。
- 当前 DRF 内存限流是每进程计数；多 worker/多实例不能视为全局额度控制。公开服务前在反向代理/共享缓存增加限流，并在模型提供商设置硬预算。
- 完成真实模型结构化输出与 embedding 维度兼容检查。
- 真实 Apple 签名、HealthKit、APNs、后台通知投递和耗电测试。
- HealthKit、第三方模型、存储地区和保留期限的隐私披露需与你实际部署一致。
- 定期执行 token 清理：`python manage.py flushexpiredtokens`。

## APNs 密钥

把 `.p8` 密钥放在服务器私有目录，不复制到仓库。通过 Docker override 给 api/jobs 增加只读挂载，`APNS_KEY_PATH` 填容器内路径。不要把密钥写进镜像。

## 备份与恢复演练

```sh
# 输出文件包含私人数据，自己妥善保管
docker compose exec -T db pg_dump -U habitpet -Fc habitpet > habitpet.backup
```

先恢复到新的空数据库，再进行账号、库存、记忆数量和向量检索检查。实际生产角色分离后按对应角色执行。

升级前备份，执行迁移并检查；失败时先判断迁移是否可逆。不能承诺所有数据库变更都可通过回退镜像自动回滚。

## 运维观察

健康检查、HTTP 状态/延迟、AI fallback 比例、模型 token usage、APNs 失败码、后台任务错误。现有日志避免记录密钥和完整健康/聊天内容。模型费用按提供商账单核对，代码不编造费用数字。
