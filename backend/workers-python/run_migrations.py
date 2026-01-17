"""
Script para executar migrations do TimescaleDB.

Uso:
    python run_migrations.py upgrade
    python run_migrations.py downgrade
"""
import asyncio
import sys
from app.migrations import (
    upgrade as upgrade_002,
    downgrade as downgrade_002
)
from app.migrations.002_timescaledb_hypertable import upgrade as upgrade_002_impl, downgrade as downgrade_002_impl
from app.migrations.003_continuous_aggregates import upgrade as upgrade_003_impl, downgrade as downgrade_003_impl
from app.migrations.004_continuous_aggregates_policies import upgrade as upgrade_004_impl, downgrade as downgrade_004_impl


async def run_migrations(command):
    """Executa todas as migrations."""
    migrations = [
        ("002_timescaledb_hypertable", upgrade_002_impl, downgrade_002_impl),
        ("003_continuous_aggregates", upgrade_003_impl, downgrade_003_impl),
        ("004_continuous_aggregates_policies", upgrade_004_impl, downgrade_004_impl),
    ]
    
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
