import pytest
from unittest.mock import patch
from homeassistant import config_entries, data_entry_flow
from custom_components.easy_smart_monitor.const import DOMAIN

@pytest.mark.asyncio
async def test_flow_user_init_success(hass):
    """Teste do fluxo de login com sucesso."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Verifica se abriu a primeira tela (User)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.easy_smart_monitor.client.EasySmartClient.authenticate",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "admin", "password": "password123", "api_host": "http://api.test"},
        )

        # Verifica se avançou para o menu de gerenciamento
        assert result2["type"] == data_entry_flow.FlowResultType.MENU
        assert result2["step_id"] == "management"

@pytest.mark.asyncio
async def test_flow_user_init_invalid_auth(hass):
    """Teste de falha na autenticação."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.easy_smart_monitor.client.EasySmartClient.authenticate",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "wrong", "password": "wrong", "api_host": "http://api.test"},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}