from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from pyvisa import VisaIOError
from qcodes.instrument.base import Instrument
from qcodes.instrument.parameter import ManualParameter, Parameter
from qcodes.instrument_drivers.stanford_research.SR830 import SR830

from qtools.instrument.custom_drivers.ZI.MFLI import MFLI


def is_bufferable(instrument: Instrument):
    """Checks if the instrument is bufferable using the qtools Buffer definition."""
    return hasattr(instrument, "_qtools_buffer") and isinstance(
        instrument._qtools_buffer, Buffer
    )


class BufferException(Exception):
    """General Buffer Exception"""


class Buffer(ABC):
    """Base class for a general buffer interface for an instrument."""

    SETTING_NAMES: set[str] = {
        "trigger",
        "trigger_type",
        "trigger_threshold",
        "delay",
        "num_points",
        "channel",
        "sample_rate",
    }

    @abstractmethod
    def setup_buffer(self, settings: dict) -> None:
        """Sets instrument related settings for the buffer."""

    @property  # type: ignore
    @abstractmethod
    def trigger(self) -> Parameter | None:
        """
        The parameter, that triggers the instruments buffer.
        Set the trigger parameter using a qcodes parameter.
        """

    @trigger.setter  # type: ignore
    @abstractmethod
    def trigger(self, parameter: Parameter | None) -> None:
        ...

    @abstractmethod
    def read(self) -> dict:
        """
        Read the buffer

        Output is a dict with the following structure:

        {
            timestamps: list[float],
            param1: list[float],
            param2: list[float],
            ...
        }"""

    @abstractmethod
    def read_raw(self) -> Any:
        "Read the buffer and return raw output."

    @abstractmethod
    def subscribe(self, parameters: list[Parameter]) -> None:
        """Measure provided parameters with the buffer."""

    @abstractmethod
    def unsubscribe(self, parameters: list[Parameter]) -> None:
        """Unsubscribe provided parameters, if they were subscribed."""

    @abstractmethod
    def is_subscribed(self, parameter: Parameter) -> bool:
        """True, if the parameter is subscribed and saved in buffer."""

    @abstractmethod
    def start(self) -> None:
        """Start the buffer. This is not the trigger."""

    def stop(self) -> None:
        """Stop the buffer."""

    def is_ready(self) -> bool:
        """True, if buffer is correctly initialized and ready to measure."""


# class SoftwareTrigger(Parameter):
#     def __init__(self, **kwargs):
#         self._triggers = []
#         super().__init__(**kwargs)

#     def add_trigger(self, callable: Callable):
#         self._triggers.append(callable)


class SR830Buffer(Buffer):
    """Buffer for Stanford SR830"""

    class ExternalTrigger(ManualParameter):
        """
        Dummy parameter for setting the external trigger.

        SR830 does only provide a single external trigger.
        To set it, call `buffer.trigger = SR830Buffer.ExternalTrigger()`
        """

    ch1_names = ["X", "R", "X Noise", "aux_in1", "aux_in2"]
    ch2_names = ["Y", "Phase", "Y Noise", "aux_in3", "aux_in4"]

    def __init__(self, device: SR830):
        self._device = device
        self._trigger: Parameter | None = None
        self._subscribed_parameters: set[Parameter] = set()

    def setup_buffer(self, settings: dict | None = None) -> None:
        """Sets instrument related settings for the buffer."""
        # TODO: sample_rate mit delay und num_points abgleichen
        # TODO: Trigger und SR abgleichen
        if not settings:
            settings = {}

        self._device.buffer_SR(settings.setdefault("sample_rate", 512))
        self._device.buffer_trig_mode("OFF")

    @property
    def trigger(self) -> Parameter | None:
        return self._trigger

    @trigger.setter
    def trigger(self, parameter: Parameter | None) -> None:
        if parameter is None:
            # TODO: standard value for Sample Rate
            self._device.buffer_SR(512)
            self._device.buffer_trig_mode("Off")
        elif isinstance(parameter, SR830Buffer.ExternalTrigger):
            self._device.buffer_SR("Trigger")
            self._device.buffer_trig_mode("On")
            self._trigger = parameter
        else:
            raise BufferException(
                "SR830 does not support setting custom trigger inputs. Use SR830Buffer.ExternalTrigger and the input on the back of the unit."
            )

    def read(self) -> dict:
        # TODO: Handle stopping buffer or not
        data = {}
        try:
            for parameter in self._subscribed_parameters:
                if parameter.name in self.ch1_names:
                    ch = "ch1"
                elif parameter.name in self.ch2_names:
                    ch = "ch2"

                # TODO: what structure has the data? do we get timestamps?
                data[parameter.name] = self._device.__getattr__(f"{ch}_datatrace").get()
        except VisaIOError as ex:
            raise BufferException(
                "Could not read the buffer. Buffer has to be stopped before readout."
            ) from ex
        return data

    def subscribe(self, parameters: list[Parameter]) -> None:
        for parameter in parameters:
            name = parameter.name
            if name in self.ch1_names:
                self._device.ch1_display(name)
                param_to_remove = {
                    param
                    for param in self._subscribed_parameters
                    if param.name in self.ch1_names
                }
                self._subscribed_parameters.difference_update(
                    param_to_remove
                )  # remove previously subscribed parameter from ch1
                self._subscribed_parameters.add(parameter)
            elif name in self.ch2_names:
                self._device.ch2_display(name)
                param_to_remove = {
                    param
                    for param in self._subscribed_parameters
                    if param.name in self.ch2_names
                }
                self._subscribed_parameters.difference_update(
                    param_to_remove
                )  # remove previously subscribed parameter from ch2
                self._subscribed_parameters.add(parameter)
            else:
                raise Exception(f"Parameter {parameter.name} can not be buffered.")

    def unsubscribe(self, parameters: list[Parameter]) -> None:
        for parameter in parameters:
            name = parameter.name
            if name in ["X", "R", "X Noise", "aux_in1", "aux_in2"]:
                self._subscribed_parameters.remove(parameter)
            elif name in ["Y", "Phase", "Y Noise", "aux_in3", "aux_in4"]:
                self._subscribed_parameters.remove(parameter)
            else:
                raise Exception(f"Parameter {parameter.name} can not be buffered.")

    def is_subscribed(self, parameter: Parameter) -> bool:
        return parameter in self._subscribed_parameters

    def start(self) -> None:
        self._device.buffer_reset()
        self._device.buffer_start()

    def stop(self) -> None:
        self._device.buffer_pause()

    def is_ready(self) -> bool:
        ...


class MFLIBuffer(Buffer):
    """Buffer for ZurichInstruments MFLI"""

    def __init__(self, mfli: MFLI):
        self._session = mfli.session
        self._device = mfli.instr
        self._daq = self._session.modules.daq
        self._sample_nodes: list = []
        self._subscribed_parameters: list[Parameter] = []
        self._trigger: Parameter | None = None
        self._channel = 0

    def setup_buffer(self, settings: dict | None = None) -> None:
        if not settings:
            settings = {}

        device = self._device
        self._daq.device(device)

        if "channel" in settings:
            self._channel = settings["channel"]

        device.demods[self._channel].enable(True)

        self._daq.type(settings.setdefault("trigger_type", 0))

        self._daq.grid.mode(2)

        if "trigger_threshold" in settings:
            # TODO: better way to distinguish, which trigger level to set
            self._daq.level(settings["trigger_threshold"])
            self._device.triggers.in_[0].level(settings["trigger_threshold"])
            self._device.triggers.in_[1].level(settings["trigger_threshold"])

        if all(k in settings for k in ("sample_rate", "burst_duration", "duration")):
            num_cols = int(
                np.ceil(settings["sample_rate"] * settings["burst_duration"])
            )
            num_bursts = int(np.ceil(settings["duration"] / settings["burst_duration"]))
            self._daq.count(num_bursts)
            self._daq.duration(settings["burst_duration"])
            self._daq.grid.cols(num_cols)

    @property
    def trigger(self):
        return super().trigger

    @trigger.setter
    def trigger(self, parameter: Parameter) -> None:
        if parameter.name == "demod0_aux_in_1":
            self._daq.triggernode("/dev4039/demods/0/sample.AuxIn0")
            if self._daq.type() not in (1, 3):
                self._daq.type(1)
        elif parameter.name == "demod0_trig_in":
            self._daq.triggernode("/dev4039/demods/0/sample.TrigIn1")
            self._daq.type(6)
        self._trigger = parameter

    def read(self) -> dict:
        data = self.read_raw()
        result_dict = {}
        for parameter in self._subscribed_parameters:
            node = self._get_node_from_parameter(parameter)
            key = next(key for key in data.keys() if str(key) == str(node))
            result_dict[parameter.name] = data[key][0].value
            if "timestamps" not in result_dict:
                result_dict["timestamps"] = data[key][0].time
        return result_dict

    def read_raw(self) -> dict:
        return self._daq.read()

    def subscribe(self, parameters: list[Parameter]) -> None:
        for parameter in parameters:
            node = self._get_node_from_parameter(parameter)
            if node not in self._sample_nodes:
                self._subscribed_parameters.append(parameter)
                self._sample_nodes.append(node)
                self._daq.subscribe(node)

    def unsubscribe(self, parameters: list[Parameter]) -> None:
        for parameter in parameters:
            node = self._get_node_from_parameter(parameter)
            if node in self._sample_nodes:
                self._sample_nodes.remove(node)
                self._subscribed_parameters.remove(parameter)
                self._daq.unsubscribe(node)

    def is_subscribed(self, parameter: Parameter) -> bool:
        return parameter in self._subscribed_parameters

    def start(self) -> None:
        self._daq.execute()

    def stop(self) -> None:
        self._daq.raw_module.finish()

    def is_ready(self) -> bool:
        ...

    def _get_node_from_parameter(self, parameter: Parameter):
        return self._device.demods[self._channel].sample.__getattr__(parameter.label)
