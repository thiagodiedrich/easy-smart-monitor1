import pytest
from unittest.mock import AsyncMock, MagicMock
from custom_components.easy_smart_monitor.coordinator import EasySmartCoordinator

@pytest.mark.asyncio
async def test_coordinator_update_and_sync(hass):
    """Testa se o coordinator chama o envio da fila."""
    client_mock = MagicMock()
    client_mock.send_queue = AsyncMock(return_value=True)
    client_mock.queue = [{"sensor": "temp", "value": 25.5}]

    coordinator = EasySmartCoordinator(hass, client_mock, update_interval=30)

    # Força atualização
    await coordinator._async_update_data()

    # Verifica se o cliente tentou enviar os dados para a API
    client_mock.send_queue.assert_called_once()