import uuid
import voluptuous as vol
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_API_HOST,
    SENSOR_TYPES,
    TEST_MODE,
    CONF_USERNAME,
    CONF_PASSWORD
)
from .client import EasySmartClient

class EasySmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gerencia o fluxo de configuração do Easy Smart Monitor."""

    VERSION = 1

    def __init__(self):
        """Inicializa o fluxo com cache temporário."""
        self.data_temp: Dict[str, Any] = {
            "equipments": []
        }
        self.current_equipment: Dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Passo 1: Login/Ativação (Suporta Test Mode)."""
        errors = {}

        if user_input is not None:
            if TEST_MODE:
                # Bypass: Aceita qualquer credencial em modo de teste
                self.data_temp.update(user_input)
                return await self.async_step_management()

            # Validação Real via API
            session = async_get_clientsession(self.hass)
            client = EasySmartClient(
                user_input[CONF_API_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session,
                self.hass
            )

            if await client.authenticate():
                self.data_temp.update(user_input)
                return await self.async_step_management()

            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_HOST, default="http://localhost"): str,
                vol.Required(CONF_USERNAME, default="admin"): str,
                vol.Required(CONF_PASSWORD, default="admin123"): str,
            }),
            errors=errors,
        )

    async def async_step_management(self, user_input=None) -> FlowResult:
        """Passo 2: Menu Principal."""
        return self.async_show_menu(
            step_id="management",
            menu_options={
                "add_equipment": "Adicionar Novo Equipamento",
                "finish": "Finalizar Configuração"
            }
        )

    async def async_step_add_equipment(self, user_input=None) -> FlowResult:
        """Passo 3: Dados do Equipamento."""
        if user_input is not None:
            # Gerar IDs e UUIDs automáticos
            new_id = len(self.data_temp["equipments"]) + 1
            self.current_equipment = {
                "id": new_id,
                "uuid": str(uuid.uuid4()),
                "nome": user_input["nome"],
                "local": user_input["local"],
                "intervalo_fila": user_input.get("intervalo_fila", 30),
                "sensors": []
            }
            return await self.async_step_add_sensor()

        return self.async_show_form(
            step_id="add_equipment",
            data_schema=vol.Schema({
                vol.Required("nome"): str,
                vol.Required("local"): str,
                vol.Optional("intervalo_fila", default=30): int,
            })
        )

    async def async_step_add_sensor(self, user_input=None) -> FlowResult:
        """Passo 4: Vínculo de Sensores (Loop)."""
        if user_input is not None:
            # Adicionar sensor ao equipamento atual
            user_input["id"] = len(self.current_equipment["sensors"]) + 1
            user_input["uuid"] = str(uuid.uuid4())
            self.current_equipment["sensors"].append(user_input)

            # Se o usuário marcar para adicionar outro, reinicia o passo
            if user_input.get("add_another"):
                return await self.async_step_add_sensor()