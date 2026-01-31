"""
Script para executar migrations do TimescaleDB.

Uso:
    python run_migrations.py upgrade
    python run_migrations.py downgrade
"""
import asyncio
import importlib
import sys


def _load_migration(module_name):
    """Carrega upgrade/downgrade de um módulo cujo nome começa com número (ex.: 002_...)."""
    mod = importlib.import_module(f"app.migrations.{module_name}")
    return mod.upgrade, mod.downgrade


async def run_migrations(command):
    """Executa todas as migrations."""
    migration_names = [
        "001_base_tables",
        "002_timescaledb_hypertable",
        "003_continuous_aggregates",
        "004_continuous_aggregates_policies",
        "005_user_security_fields",
        "006_tenant_organization_workspace",
        "007_tenant_id_users_equipments",
        "008_org_workspace_in_equipments",
    ]
    migrations = [(name, *_load_migration(name)) for name in migration_names]
    
    if command == "upgrade":
        print("🚀 Aplicando migrations...")
        for name, upgrade_fn, _ in migrations:
            print(f"\n📦 Executando {name}...")
            try:
                await upgrade_fn()
                print(f"✅ {name} aplicada com sucesso!")
            except Exception as e:
                print(f"❌ Erro em {name}: {e}")
                sys.exit(1)
        print("\n✅ Todas as migrations aplicadas!")
    
    elif command == "downgrade":
        print("⬇️  Revertendo migrations...")
        for name, _, downgrade_fn in reversed(migrations):
            print(f"\n📦 Revertendo {name}...")
            try:
                await downgrade_fn()
                print(f"✅ {name} revertida!")
            except Exception as e:
                print(f"❌ Erro ao reverter {name}: {e}")
                sys.exit(1)
        print("\n✅ Todas as migrations revertidas!")
    
    else:
        print("Uso: python run_migrations.py [upgrade|downgrade]")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python run_migrations.py [upgrade|downgrade]")
        sys.exit(1)
    
    command = sys.argv[1]
    asyncio.run(run_migrations(command))
