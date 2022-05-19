from __future__ import annotations

import logging
from modulefinder import LOAD_CONST

import requests
import websockets
import asyncio
import json



import voluptuous as vol
from .const import (
    DOMAIN,
)

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import (ATTR_POSITION, PLATFORM_SCHEMA,
                                            CoverEntity)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

async def hello(covers, hass, host, apikey):
    ip = host
    async with websockets.connect("ws://"+ip+"/api", extra_headers={'authorization':'Bearer ' + apikey}, ping_timeout=None) as ws:
        while True:
            result =  await ws.recv()
            _LOGGER.info("Received '%s'" % result)
            data = json.loads(result)     
            for l in covers:
                if l.unique_id == "cover-"+str(data["load"]["id"]):
                    _LOGGER.info("found entity to update")
                    l.updateExternal(data["load"]["state"]["level"], data["load"]["state"]["moving"])
        ws.close()


def updatedata(host, apikey):
    #ip = "192.168.0.18"
    ip = host
    key = apikey
    return requests.get("http://"+ip+"/api/loads", headers= {'authorization':'Bearer ' + key})

async def async_setup_entry(hass, entry, async_add_entities):
    host = entry.data['host']
    apikey = entry.data['apikey']

    _LOGGER.info("---------------------------------------------- %s %s", host, apikey)

    response = await hass.async_add_executor_job(updatedata, host, apikey)

    loads = response.json()

    covers= []
    for value in loads["data"]:
        if value["type"] == "motor":
            covers.append(FellerCover(value, host, apikey))

    asyncio.get_event_loop().create_task(hello(covers, hass, host, apikey))
    async_add_entities(covers, True)


class FellerCover(CoverEntity):

    def __init__(self, data, host, apikey) -> None:
        self._data = data
        self._name = data["name"]
        self._id = str(data["id"])
        self._is_opening = False
        self._is_closing = False
        self._is_closed = False
        self._position = None
        self._host = host
        self._apikey = apikey

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self):
        return "cover-" + self._id

    @property
    def current_cover_position(self):
        return self._position

    @property
    def is_opening(self) -> bool | None:
        return self._is_opening

    @property
    def is_closing(self) -> bool | None:
        return self._is_closing

    @property
    def is_closed(self) -> bool | None:
        return self._is_closed
    
    @property
    def should_poll(self) -> bool | None:
        return False

    def open_cover(self, **kwargs: Any) -> None:
        self._position = kwargs.get(ATTR_POSITION, 100)
        ip = self._host
        response = requests.put("http://"+ip+"/api/loads/"+self._id+"/target_state", headers= {'authorization':'Bearer ' + self._apikey}, json={'level': 0})
        _LOGGER.info(response.json())
        self._state = True
        self._position = response.json()["data"]["target_state"]["level"]/100

    def close_cover(self, **kwargs: Any) -> None:
        self._position = kwargs.get(ATTR_POSITION, 100)
        ip = self._host
        response = requests.put("http://"+ip+"/api/loads/"+self._id+"/target_state", headers= {'authorization':'Bearer ' + self._apikey}, json={'level': 10000})
        _LOGGER.info(response.json())
        self._state = True
        self._position = response.json()["data"]["target_state"]["level"]/100

    def set_cover_position(self, **kwargs: Any) -> None:
        self._position = kwargs.get(ATTR_POSITION, 100)
        ip = self._host
        response = requests.put("http://"+ip+"/api/loads/"+self._id+"/target_state", headers= {'authorization':'Bearer ' + self._apikey}, json={'level': self._position*100})
        _LOGGER.info(response.json())
        self._state = True
        self._position = response.json()["data"]["target_state"]["level"]/100

    def stop_cover(self, **kwargs: Any) -> None:
        _LOGGER.info("stop not implemented")

    def updatestate(self):
        ip = self._host
        # _LOGGER.info("requesting http://"+ip+"/api/loads/"+self._id)
        return requests.get("http://"+ip+"/api/loads/"+self._id, headers= {'authorization':'Bearer ' + self._apikey})


    def update(self) -> None:
        response = self.updatestate()
        load = response.json()
        _LOGGER.info(load)

        self._position = load["data"]["state"]["level"]/100

        if load["data"]["state"]["moving"] == "stop":
            self._is_closing = False
            self._is_opening = False
        if load["data"]["state"]["moving"]  == "up":
            self._is_closing = False
            self._is_opening = True
        if load["data"]["state"]["moving"] == "down":
            self._is_closing = True
            self._is_opening = False

        if self._position > 0:
            self._is_closed = True
        else:
            self._is_closed = False
    
    def updateExternal(self, position, moving):
        self._position = position/100

        if moving == "stop":
            self._is_closing = False
            self._is_opening = False
        if moving == "up":
            self._is_closing = False
            self._is_opening = True
        if moving == "down":
            self._is_closing = True
            self._is_opening = False

        if self._position > 0:
            self._is_closed = True
        else:
            self._is_closed = False

        self.schedule_update_ha_state()