import uuid
import voluptuous as vol
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_API_HOST, SENSOR_TYPES
from .client import EasySmartClient

class EasySmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gerencia o fluxo de configuração para o Easy Smart Monitor."""

    VERSION = 1

    def __init__(self):
        """Inicializa o fluxo com armazenamento temporário."""
        self.data_temp: Dict[str, Any] = {
            "equipments": []
        }
        self.current_equipment: Dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Passo 1: Ativação/Login via API."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = EasySmartClient(
                user_input[CONF_API_HOST],
                user_input["username"],
                user_input["password"],
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
                vol.Required(CONF_API_HOST): str,
                vol.Required("username"): str,
                vol.Required("password"): vol.All(str, vol.Length(min=6)),
            }),
            errors=errors,
        )

    async def async_step_management(self, user_input=None) -> FlowResult:
        """Passo 2: Menu de Gerenciamento."""
        return self.async_show_menu(
            step_id="management",
            menu_options={
                "add_equipment": "Adicionar Novo Equipamento",
                "finish": "Finalizar e Salvar Configurações"
            }
        )

    async def async_step_add_equipment(self, user_input=None) -> FlowResult:
        """Passo 3: Cadastro de Equipamento."""
        if user_input is not None:
            # Gerar IDs automáticos conforme requisito
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
        """Passo 4: Cadastro de Sensores para o Equipamento atual."""
        if user_input is not None:
            sensor_id = len(self.current_equipment["sensors"]) + 1
            user_input["id"] = sensor_id
            user_input["uuid"] = str(uuid.uuid4())

            self.current_equipment["sensors"].append(user_input)

            if user_input.get("add_another"):
                return await self.async_step_add_sensor()

            # Adiciona o equipamento completo à lista e volta ao menu
            self.data_temp["equipments"].append(self.current_equipment)
            return await self.async_step_management()

        # Lista todas as entidades do HA para o combo box
        all