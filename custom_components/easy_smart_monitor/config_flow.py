import voluptuous as vol
import uuid
import logging
import copy
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

# Importações necessárias para limpar o registro do HA
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_API_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EQUIPMENTS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_INTERVALO_COLETA,
    DEFAULT_TEMPO_PORTA_ABERTA,
    DEFAULT_EQUIPAMENTO_ATIVO,
    DEFAULT_SIRENE_ATIVA,
    DEFAULT_UPDATE_INTERVAL,
    TEST_MODE
)
from .client import EasySmartClient

_LOGGER = logging.getLogger(__name__)

class EasySmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gerencia o fluxo de configuração inicial."""

    VERSION = 1

    def __init__(self):
        self.data = {}
        self.equipments = []

    async def async_step_user(self, user_input=None):
        """Passo 1: Credenciais da API."""
        errors = {}

        default_host = "http://localhost:5000" if TEST_MODE else ""
        default_user = "admin_teste" if TEST_MODE else ""
        default_pass = "senha_teste" if TEST_MODE else ""

        if user_input is not None:
            if TEST_MODE:
                _LOGGER.info("MODO TESTE: Pulando validação de API.")
                self.data = user_input
                return await self.async_step_add_equipment()

            session = async_get_clientsession(self.hass)
            client = EasySmartClient(
                user_input[CONF_API_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session,
                self.hass
            )

            try:
                if await client.authenticate():
                    self.data = user_input
                    return await self.async_step_add_equipment()
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.error("Erro config flow: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_HOST, default=default_host): str,
                vol.Required(CONF_USERNAME, default=default_user): str,
                vol.Required(CONF_PASSWORD, default=default_pass): str,
            }),
            errors=errors,
        )

    async def async_step_add_equipment(self, user_input=None):
        """Passo 2: Cadastro de Freezer/Geladeira."""
        if user_input is not None:
            new_equip = {
                "uuid": str(uuid.uuid4()),
                "nome": user_input["nome"],
                "local": user_input["local"],
                "ativo": DEFAULT_EQUIPAMENTO_ATIVO,
                "sirene_ativa": DEFAULT_SIRENE_ATIVA,
                "intervalo_coleta": DEFAULT_INTERVALO_COLETA,
                "tempo_porta": DEFAULT_TEMPO_PORTA_ABERTA,
                "sensors": []
            }
            self.equipments.append(new_equip)
            return await self.async_step_add_sensor()

        return self.async_show_form(
            step_id="add_equipment",
            data_schema=vol.Schema({
                vol.Required("nome", default="Freezer Principal"): str,
                vol.Required("local", default="Cozinha"): str,
            }),
        )

    async def async_step_add_sensor(self, user_input=None):
        """Passo 3: Vínculo de sensores."""
        if user_input is not None:
            current_equip = self.equipments[-1]
            current_equip["sensors"].append({
                "uuid": str(uuid.uuid4()),
                "ha_entity_id": user_input["ha_entity_id"],
                "tipo": user_input["tipo"]
            })

            if user_input.get("add_another"):
                return await self.async_step_add_sensor()

            return self.async_show_menu(
                step_id="post_add_menu",
                menu_options=["add_equipment", "finalizar"]
            )

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema({
                vol.Required("ha_entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False)
                ),
                vol.Required("tipo"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["temperatura", "energia", "tensao", "corrente", "umidade", "porta", "sirene", "status", "botao"],
                        translation_key="sensor_types",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("add_another", default=False): bool,
            }),
        )

    async def async_step_post_add_menu(self, user_input=None):
        if user_input == "add_equipment":
            return await self.async_step_add_equipment()
        return await self.async_step_finalizar()

    async def async_step_finalizar(self, user_input=None):
        self.data[CONF_EQUIPMENTS] = self.equipments
        title = f"Easy Smart ({self.data.get(CONF_API_HOST, 'Local')})"
        return self.async_create_entry(title=title, data=self.data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EasySmartOptionsFlowHandler(config_entry)


class EasySmartOptionsFlowHandler(config_entries.OptionsFlow):
    """Gerencia as opções e a edição de equipamentos."""

    def __init__(self, config_entry):
        # Deepcopy garante que self.updated_data seja independente até salvarmos
        self.updated_data = copy.deepcopy(dict(config_entry.data))
        self.selected_equip_uuid = None
        self.is_new_equipment = False

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "change_interval",
                "equipments_menu",
                "manage_sensors"
            ]
        )

    async def async_step_equipments_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="equipments_menu",
            menu_options=["add_more_equipment", "remove_equipment", "init"]
        )

    async def async_step_change_interval(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(CONF_UPDATE_INTERVAL) or \
                          self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                          
        return self.async_show_form(
            step_id="change_interval",
            data_schema=vol.Schema({
                vol.Optional(CONF_UPDATE_INTERVAL, default=current_interval):
                    vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }),
        )

    async def async_step_manage_sensors(self, user_input=None):
        """Gerencia sensores de equipamentos JÁ EXISTENTES."""
        if user_input is not None:
            self.selected_equip_uuid = user_input["equip_uuid"]
            self.is_new_equipment = False
            return await self.async_step_sensor_action()

        equips = {e["uuid"]: f"{e['nome']} ({e['local']})" for e in self.updated_data.get(CONF_EQUIPMENTS, [])}
        return self.async_show_form(
            step_id="manage_sensors",
            data_schema=vol.Schema({
                vol.Required("equip_uuid"): vol.In(equips),
            }),
        )

    async def async_step_sensor_action(self, user_input=None):
        return self.async_show_menu(
            step_id="sensor_action",
            menu_options=["add_sensor_to_equip", "remove_sensor_from_equip", "init"]
        )

    async def async_step_add_sensor_to_equip(self, user_input=None):
        """Adiciona sensor."""
        if user_input is not None:
            for equip in self.updated_data[CONF_EQUIPMENTS]:
                if equip["uuid"] == self.selected_equip_uuid:
                    equip["sensors"].append({
                        "uuid": str(uuid.uuid4()),
                        "ha_entity_id": user_input["ha_entity_id"],
                        "tipo": user_input["tipo"]
                    })
                    break

            self.hass.config_entries.async_update_entry(self.config_entry, data=self.updated_data)
            self.is_new_equipment = False

            return await self.async_step_sensor_action()

        return self.async_show_form(
            step_id="add_sensor_to_equip",
            data_schema=vol.Schema({
                vol.Required("ha_entity_id"): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False)
                ),
                vol.Required("tipo"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["temperatura", "energia", "tensao", "corrente", "umidade", "porta", "sirene", "status", "botao"],
                        translation_key="sensor_types",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_remove_sensor_from_equip(self, user_input=None):
        """Remove um sensor de um equipamento e do registro do HA."""
        if user_input is not None:
            target_sensor_uuid = user_input["sensor_uuid"]

            # 1. Limpeza do Registro de Entidades do HA
            ent_reg = er.async_get(self.hass)
            entries_to_remove = []

            # Procura entidades que pertencem a esta configuração e contêm o UUID do sensor
            entries = er.async_entries_for_config_entry(ent_reg, self.config_entry.entry_id)
            for entry in entries:
                if entry.unique_id and target_sensor_uuid in entry.unique_id:
                    entries_to_remove.append(entry.entity_id)

            # Remove efetivamente
            for entity_id in entries_to_remove:
                _LOGGER.info("Removendo entidade do registro: %s", entity_id)
                ent_reg.async_remove(entity_id)

            # 2. Atualização da Lista Interna (JSON)
            for equip in self.updated_data[CONF_EQUIPMENTS]:
                if equip["uuid"] == self.selected_equip_uuid:
                    equip["sensors"] = [s for s in equip["sensors"] if s["uuid"] != target_sensor_uuid]
                    break

            self.hass.config_entries.async_update_entry(self.config_entry, data=self.updated_data)
            return await self.async_step_sensor_action()

        # Prepara a lista para exibir no formulário
        current_sensors = {}
        for equip in self.updated_data.get(CONF_EQUIPMENTS, []):
            if equip["uuid"] == self.selected_equip_uuid:
                current_sensors = {s["uuid"]: f"{s['tipo']} ({s['ha_entity_id']})" for s in equip["sensors"]}
                break

        return self.async_show_form(
            step_id="remove_sensor_from_equip",
            data_schema=vol.Schema({
                vol.Required("sensor_uuid"): vol.In(current_sensors),
            }),
        )

    async def async_step_add_more_equipment(self, user_input=None):
        """Adiciona novo equipamento (ETAPA 1)."""
        if user_input is not None:
            new_equip = {
                "uuid": str(uuid.uuid4()),
                "nome": user_input["nome"],
                "local": user_input["local"],
                "ativo": DEFAULT_EQUIPAMENTO_ATIVO,
                "sirene_ativa": DEFAULT_SIRENE_ATIVA,
                "intervalo_coleta": DEFAULT_INTERVALO_COLETA,
                "tempo_porta": DEFAULT_TEMPO_PORTA_ABERTA,
                "sensors": []
            }
            if CONF_EQUIPMENTS not in self.updated_data:
                self.updated_data[CONF_EQUIPMENTS] = []

            self.updated_data[CONF_EQUIPMENTS].append(new_equip)
            self.selected_equip_uuid = new_equip["uuid"]
            self.is_new_equipment = True

            return await self.async_step_new_equip_decision()

        return self.async_show_form(
            step_id="add_more_equipment",
            data_schema=vol.Schema({
                vol.Required("nome"): str,
                vol.Required("local"): str,
            }),
        )

    async def async_step_new_equip_decision(self, user_input=None):
        """Decide se adiciona sensor ou salva direto."""
        return self.async_show_menu(
            step_id="new_equip_decision",
            menu_options=["add_sensor_to_equip", "save_new_equip"]
        )

    async def async_step_save_new_equip(self, user_input=None):
        """Salva o equipamento sem sensores."""
        self.hass.config_entries.async_update_entry(self.config_entry, data=self.updated_data)
        self.is_new_equipment = False
        return await self.async_step_equipments_menu()

    async def async_step_remove_equipment(self, user_input=None):
        """Remove equipamento inteiro e limpa o registro do HA."""
        if user_input is not None:
            equip_uuid = user_input["equip_uuid"]

            # 1. Limpeza do Registro de Dispositivos (Device Registry)
            dev_reg = dr.async_get(self.hass)

            # Busca o dispositivo pelos identificadores (DOMAIN, uuid)
            device = dev_reg.async_get_device(identifiers={(DOMAIN, equip_uuid)})
            if device:
                _LOGGER.info("Removendo dispositivo do registro: %s", device.name)
                # Ao remover o dispositivo, o HA remove automaticamente as entidades vinculadas a ele
                dev_reg.async_remove_device(device.id)
            else:
                _LOGGER.warning("Dispositivo %s não encontrado no registro para remoção.", equip_uuid)

            # 2. Atualização da Lista Interna (JSON)
            self.updated_data[CONF_EQUIPMENTS] = [
                e for e in self.updated_data[CONF_EQUIPMENTS]
                if e["uuid"] != equip_uuid
            ]

            self.hass.config_entries.async_update_entry(self.config_entry, data=self.updated_data)
            return await self.async_step_equipments_menu()

        equips = {e["uuid"]: e["nome"] for e in self.updated_data.get(CONF_EQUIPMENTS, [])}
        return self.async_show_form(
            step_id="remove_equipment",
            data_schema=vol.Schema({
                vol.Required("equip_uuid"): vol.In(equips),
            }),
        )