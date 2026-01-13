import pytest
import asyncio
from unittest.mock import MagicMock
from custom_components.easy_smart_monitor.sensor import FreezerMonitorSensor

@pytest.mark.asyncio
async def test_siren_timer_logic():
    """Valida se a sirene ativa após o tempo determinado."""
    coordinator = MagicMock()
    config = {
        "nome_sensor": "Porta Freezer",
        "uuid_sensor": "123",
        "id_equipment": 1,
        "tipo_sensor": "porta"
    }

    sensor = FreezerMonitorSensor(coordinator, config)

    # Simula porta aberta
    # Reduzimos o sleep no mock para o teste não demorar 120s reais
    with patch("asyncio.sleep", return_value=None):
        await sensor.async_update_status("aberto")
        assert sensor._sirene_active is True

    # Simula fechamento da porta
    await sensor.async_update_status("fechado")
    assert sensor._sirene_active is False