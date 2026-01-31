"""
Migrations para TimescaleDB (Backend v1.3.0).

Ordem de execução:
1. 001_base_tables - Cria tabelas base (users, equipments, sensors, telemetry_data)
2. 002_timescaledb_hypertable - Converte tabela em hypertable
3. 003_continuous_aggregates - Cria continuous aggregates
4. 004_continuous_aggregates_policies - Configura políticas
5. 005_user_security_fields - Campos de segurança do usuário (UserType, UserStatus, etc.)
6. 006_tenant_organization_workspace - Tabelas SaaS base (tenants, organizations, workspaces)
7. 007_tenant_id_users_equipments - tenant_id em users e equipments (Fase 1)
8. 008_org_workspace_in_equipments - organization_id e workspace_id em equipments (Fase 2)
9. 009_tenant_usage_daily - tabela de uso diário por tenant (Fase 4)
10. 010_plans_and_limits - planos e limites por tenant (Fase 5)
11. 011_tenant_billing_events - eventos de billing por tenant (Fase 6)
12. 012_org_workspace_in_users - organization_id/workspace_id em users
13. 013_tenant_usage_daily_scoped - uso diário por org/workspace (Fase 7)
14. 014_alerting_tables - regras/alertas/webhooks (Fase 7)
15. 015_alert_delay_seconds - atraso por plano/tenant (Fase 7)
16. 016_users_refactor - users com tenant obrigatório e arrays
17. 017_equipments_sensors_telemetry_refactor - status enums e scope obrigatório
18. 018_plans_limits_refactor - planos/limites com defaults e totais
19. 019_continuous_aggregates_scoped - aggregates com tenant/org/workspace
20. 020_audit_logs - auditoria administrativa
"""
