"""
Migrations para TimescaleDB (Backend v1.1.0).

Ordem de execução:
1. 001_base_tables - Cria tabelas base (users, equipments, sensors, telemetry_data)
2. 002_timescaledb_hypertable - Converte tabela em hypertable
3. 003_continuous_aggregates - Cria continuous aggregates
4. 004_continuous_aggregates_policies - Configura políticas
5. 005_user_security_fields - Campos de segurança do usuário (UserType, UserStatus, etc.)
6. 006_tenant_organization_workspace - Tabelas SaaS base (tenants, organizations, workspaces)
7. 007_tenant_id_users_equipments - tenant_id em users e equipments (Fase 1)
8. 008_org_workspace_in_equipments - organization_id e workspace_id em equipments (Fase 2)
"""
