# GPS 项目文档入口

## 当前有效文档

- [产品说明](./PRD.md)
- [部署说明](./DEPLOYMENT.md)
- [变更记录](./CHANGELOG.md)
- [GPS 绑定查询 API](./GPS_BINDING_QUERY_API.md)
- [HBT 数据接入 PRD](./HBT_DATA_INGESTION_PRD.md)

## 运维和报告

- [HBT 增量运行手册](./HBT_INCREMENTAL_RUNNER_RUNBOOK.md)
- [HBT 增量真实运行报告](./HBT_INCREMENTAL_REAL_RUN_REPORT.md)

## 跨项目规则

- 文档标准见门户：`/root/apps/portal/docs/DOCUMENTATION_STANDARD.md`
- 网关、SSO 和 AI 配置主规则见门户：`/root/apps/portal/docs/BRIANHUB_GATEWAY_AND_SSO.md`

## 维护规则

- 产品边界和数据原则更新到 `PRD.md`。
- 运行方式、采集脚本、定时任务更新到 runbook 或当前运行手册。
- 阶段性验证结果放入报告文档，不写入 CHANGELOG 长篇过程。
- 不记录真实密码、内部令牌或 API Key。
