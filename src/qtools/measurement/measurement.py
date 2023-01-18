"""
Measurement
"""
import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import MutableSequence
from contextlib import suppress
from datetime import datetime
from functools import wraps
from typing import Any, Union

import numpy as np
import qcodes as qc
from qcodes import Station
from qcodes.instrument import Parameter
from qcodes.instrument.parameter import _BaseParameter
from qcodes.utils.dataset.doNd import AbstractSweep, ActionsT, LinSweep
from qtools_metadata.measurement import MeasurementData
from qtools_metadata.measurement import MeasurementScript as DomainMeasurementScript
from qtools_metadata.measurement import MeasurementSettings
from qtools_metadata.metadata import Metadata

from qtools.instrument.buffers.buffer import is_bufferable
from qtools.utils.ramp_parameter import ramp_or_set_parameter
from qtools.utils.utils import flatten_array


def is_measurement_script(o):
    return inspect.isclass(o) and issubclass(o, MeasurementScript)


class QtoolsStation(Station):
    """Station object, inherits from qcodes Station."""


def create_hook(func, hook):
    """
    Decorator to hook a function onto an existing function.
    The hook function can use keyword-only arguments, which are omitted prior to execution of the main function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        hook(*args, **kwargs)
        # remove arguments used in hook from kwargs
        sig = inspect.signature(hook)
        varkw = next(
            filter(
                lambda p: p.kind is inspect.Parameter.VAR_KEYWORD,
                sig.parameters.values(),
            )
        ).name
        unused_kwargs = sig.bind(*args, **kwargs).arguments.get(varkw) or {}
        return func(*args, **unused_kwargs)

    return wrapper


class MeasurementScript(ABC):
    """
    Base class for measurement scripts.

    The abstract function "run" has to be implemented.
    """

    # TODO: Put list elsewhere! Remove names that were added as workarounds (e.g. aux_voltage) as soon as possible
    PARAMETER_NAMES: set[str] = {
        "voltage",
        "current",
        "current_x_component",
        "current_y_component",
        "current_compliance",
        "amplitude",
        "frequency",
        "output_enabled",
        "time_constant",
        "phase",
        "count",
        "aux_voltage_1",
        "aux_voltage_2",
    }

    def __new__(cls, *args, **kwargs):
        # reverse order, so insert metadata is run second
        cls.run = create_hook(cls.run, cls._insert_metadata_into_db)
        cls.run = create_hook(cls.run, cls._add_data_to_metadata)
        cls.run = create_hook(cls.run, cls._add_datetime_to_metadata_if_empty)
        return super().__new__(cls, *args, **kwargs)

    def __init__(self):
        self.properties: dict[Any, Any] = {}
        self.gate_parameters: dict[Any, Union[dict[Any, Union[Parameter, None]], Parameter, None]] = {}
        self._buffered_num_points: int | None = None

    def add_gate_parameter(self, parameter_name: str, gate_name: str = None, parameter: Parameter = None) -> None:
        """
        Adds a gate parameter to self.gate_parameters.

        Args:
            parameter_name (str): Name of the parameter. Has to be in MeasurementScript.PARAMETER_NAMES.
            gate_name (str): Name of the parameter's gate. Set this, if you want to define the parameter
                             under a specific gate. Defaults to None.
            parameter (Parameter): Custom parameter. Set this, if you want to set a custom parameter. Defaults to None.
        """
        if parameter_name not in MeasurementScript.PARAMETER_NAMES:
            raise NameError(f'parameter_name "{parameter_name}" not in MeasurementScript.PARAMETER_NAMES.')
        if not gate_name:
            self.gate_parameters[parameter_name] = parameter
        else:
            # Create gate dict if not existing
            gate = self.gate_parameters.setdefault(gate_name, {})
            # Raise Exception, if gate "gate_name" was populated with a parameter (or smth. else) before
            if isinstance(gate, dict):
                gate[parameter_name] = parameter
            else:
                raise Exception("Gate {gate_name} is not a dictionary.")

    def _set_buffered_num_points(self) -> None:
        """
        Calculates number of datapoints when buffered measurements are performed and sets
        the buffered_num_points accordingly. Required to define QCoDeS datastructure.

        Raises
        ------
        Exception
           Exception if number of points is overdefined.

        Returns
        -------
        None
        """
        if all(k in self.buffer_settings for k in ("sampling_rate", "burst_duration", "num_points")):
            raise Exception("You cannot define sampling_rate, burst_duration and num_points at the same time")
        elif self.buffer_settings.get("num_points", False):
            self.buffered_num_points = self.buffer_settings["num_points"]
        elif all(k in self.buffer_settings for k in ("sampling_rate", "burst_duration")):
            self.buffered_num_points = int(
                np.ceil(self.buffer_settings["sampling_rate"] * self.buffer_settings["burst_duration"])
            )

    def setup(
        self,
        parameters: dict,
        metadata: Metadata,
        *,
        add_script_to_metadata: bool = True,
        add_parameters_to_metadata: bool = True,
        buffer_settings: dict = {},
        **settings: dict,
    ) -> None:
        """
        Adds all gate_parameters that are defined in the parameters argument to
        the measurement. Allows to pass metadata to measurement and update the
        metadata with the script.

        Args:
            parameters (dict): Dictionary containing parameters and their settings
            metadata (dict): Dictionary containing metadata that should be
                            available for the measurement.
            add_script_to_metadata (bool): If True (default), adds this object's content
                                           to the metadata's measurement.script.
            add_parameters_to_metadata (bool): If True (default), add the parameters to
                                               the metadata's measurement.settings.
            settings (dict): Settings regarding the measurement script. Kwargs:
                ramp_rate: Defines how fast parameters are ramped during
                initialization and reset.
                setpoint_intervalle: Defines how smooth parameters are ramped
                during initialization and reset.
        """
        # TODO: Add settings to metadata
        self.metadata = metadata
        # TODO: Better place to put this?
        self.buffered = False
        cls = type(self)
        try:
            self.buffer_settings.update(buffer_settings)
        except:
            self.buffer_settings = buffer_settings
        self._set_buffered_num_points()

        try:
            self.settings.update(settings)
        except:
            self.settings = settings

        # Add script and parameters to metadata
        if add_script_to_metadata:
            try:
                if not metadata.measurement.script:
                    metadata.measurement.script = DomainMeasurementScript.create(cls.__name__)
                script = metadata.measurement.script

                script.language = "python"
                script.script = inspect.getsource(cls)
            except OSError as err:
                print(f"Source of MeasurementScript coud not be acquired: {err}")
            except Exception as e:
                print(f"Script could not be added to metadata: {e}")

        if add_parameters_to_metadata:
            try:
                if not metadata.measurement.settings:
                    metadata.measurement.settings = MeasurementSettings.create(f"{cls.__name__}Settings")
                settings = metadata.measurement.settings

                settings.settings = json.dumps(parameters)
            except Exception as e:
                print(f"Parameters could not be added to metadata: {e}")

        # Add gate parameters
        for gate, vals in parameters.items():
            self.properties[gate] = vals
            for parameter, properties in vals.items():
                self.add_gate_parameter(parameter, gate)

    def initialize(self) -> None:
        """
        Sets all static/sweepable parameters to their value/start value.
        If parameters are both, static and dynamic, they will be set to the "value" property
        and not to the "start" property.
        Parameters that are marked "dynamic" and "gettable" will not be added
        to the "self.gettable_parameters" as they are recorded anyway and will
        cause issues with dond functions.
        Provides gettable_parameters, static_parameters and dynamic parameters to
        measurement class and generates AbstractSweeps from the measurement
        properties. Sweeps form a list that can be found in "dynamic_sweeps"
        TODO: Is there a more elegant way?
        TODO: Put Sweep-Generation somewhere else?
        TODO: Allow setting ramp rate for setting the parameters manually
        """
        self.gettable_parameters: list[str] = []
        self.gettable_channels: list[str] = []
        self.break_conditions: list[str] = []
        self.static_parameters: list[str] = []
        self.dynamic_parameters: list[str] = []
        self.dynamic_channels: list[str] = []
        self.dynamic_sweeps: list[str] = []
        self.buffers: set = set()  # All buffers of gettable parameters

        ramp_rate = self.settings.get("ramp_rate", 0.3)
        ramp_time = self.settings.get("ramp_time", 5)
        setpoint_intervall = self.settings.get("setpoint_intervall", 0.1)
        for gate, parameters in self.gate_parameters.items():
            for parameter, channel in parameters.items():
                if self.properties[gate][parameter]["type"].find("static") >= 0:  # TODO: Handle strings
                    ramp_or_set_parameter(
                        channel,
                        self.properties[gate][parameter]["value"],
                        ramp_rate=ramp_rate,
                        ramp_time=ramp_time,
                        setpoint_intervall=setpoint_intervall,
                    )
                    ramp_or_set_parameter(
                        channel,
                        self.properties[gate][parameter]["value"],
                        ramp_rate=ramp_rate,
                        ramp_time=ramp_time,
                        setpoint_intervall=setpoint_intervall,
                    )
                    self.static_parameters.append({"gate": gate, "parameter": parameter})

                if self.properties[gate][parameter]["type"].find("gettable") >= 0:
                    self.gettable_parameters.append({"gate": gate, "parameter": parameter})
                    self.gettable_channels.append(channel)
                    with suppress(KeyError):
                        for condition in self.properties[gate][parameter]["break_conditions"]:
                            self.break_conditions.append({"channel": channel, "break_condition": condition})
                elif self.properties[gate][parameter]["type"].find("dynamic") >= 0:
                    # Handle different possibilities for starting points
                    try:
                        ramp_or_set_parameter(
                            channel,
                            self.properties[gate][parameter]["value"],
                            ramp_rate=ramp_rate,
                            ramp_time=ramp_time,
                            setpoint_intervall=setpoint_intervall,
                        )
                    except KeyError:
                        try:
                            ramp_or_set_parameter(
                                channel,
                                self.properties[gate][parameter]["start"],
                                ramp_rate=ramp_rate,
                                ramp_time=ramp_time,
                                setpoint_intervall=setpoint_intervall,
                            )
                        except KeyError:
                            ramp_or_set_parameter(
                                channel,
                                self.properties[gate][parameter]["setpoints"][0],
                                ramp_rate=ramp_rate,
                                ramp_time=ramp_time,
                                setpoint_intervall=setpoint_intervall,
                            )
                    self.dynamic_parameters.append({"gate": gate, "parameter": parameter})
                    self.dynamic_channels.append(channel)
                    # Generate sweeps from parameters
                    if self.buffered:
                        try:
                            self.dynamic_sweeps.append(
                                LinSweep(
                                    channel,
                                    self.properties[gate][parameter]["start"],
                                    self.properties[gate][parameter]["stop"],
                                    self.buffered_num_points,
                                    self.properties[gate][parameter]["delay"],
                                )
                            )
                        except KeyError:
                            self.dynamic_sweeps.append(
                                LinSweep(
                                    channel,
                                    self.properties[gate][parameter]["setpoints"][0],
                                    self.properties[gate][parameter]["setpoints"][-1],
                                    self.buffered_num_points,
                                    delay=self.properties[gate][parameter].setdefault("delay", 0),
                                )
                            )
                    else:
                        try:
                            self.dynamic_sweeps.append(
                                LinSweep(
                                    channel,
                                    self.properties[gate][parameter]["start"],
                                    self.properties[gate][parameter]["stop"],
                                    self.properties[gate][parameter]["num_points"],
                                    self.properties[gate][parameter]["delay"],
                                )
                            )
                        except KeyError:
                            self.dynamic_sweeps.append(
                                CustomSweep(
                                    channel,
                                    self.properties[gate][parameter]["setpoints"],
                                    delay=self.properties[gate][parameter].setdefault("delay", 0),
                                )
                            )
        if self.buffered:
            self.buffers = {
                channel.root_instrument._qtools_buffer for channel in self.gettable_channels if is_bufferable(channel)
            }
            for gettable_param in self.gettable_channels:
                if is_bufferable(gettable_param):
                    gettable_param.root_instrument._qtools_buffer.subscribe([gettable_param])
                else:
                    raise Exception(f"{gettable_param} is not bufferable.")
        self._relabel_instruments()

    @abstractmethod
    def run(self) -> list:
        """
        Runs the already setup measurement. you can call self.initialize in here.
        Abstract method.
        """
        return []

    def reset(self) -> None:
        """
        Resets all static/dynamic parameters to their value/start value.
        """
        ramp_rate = self.settings.get("ramp_rate", 0.3)
        setpoint_intervall = self.settings.get("setpoint_intervall", 0.1)
        for gate, parameters in self.gate_parameters.items():
            for parameter, channel in parameters.items():
                if self.properties[gate][parameter]["type"].find("static") >= 0:
                    ramp_or_set_parameter(
                        channel,
                        self.properties[gate][parameter]["value"],
                        ramp_rate=ramp_rate,
                        setpoint_intervall=setpoint_intervall,
                    )
                elif self.properties[gate][parameter]["type"].find("dynamic") >= 0:
                    try:
                        ramp_or_set_parameter(
                            channel,
                            self.properties[gate][parameter]["value"],
                            ramp_rate=ramp_rate,
                            setpoint_intervall=setpoint_intervall,
                        )
                    except KeyError:
                        try:
                            ramp_or_set_parameter(
                                channel,
                                self.properties[gate][parameter]["start"],
                                ramp_rate=ramp_rate,
                                setpoint_intervall=setpoint_intervall,
                            )
                        except KeyError:
                            ramp_or_set_parameter(
                                channel,
                                self.properties[gate][parameter]["setpoints"][0],
                                ramp_rate=ramp_rate,
                                setpoint_intervall=setpoint_intervall,
                            )

    def ready_buffers(self, **kwargs) -> None:
        """
        Setup all buffers registered in the measurement and start them

        Parameters
        ----------
        **kwargs : None so far...

        Returns
        -------
        None
        """
        for buffer in self.buffers:
            buffer.setup_buffer(settings=self.buffer_settings)
            buffer.start()

    def readout_buffers(self, **kwargs) -> dict:
        """
        Readout all buffer and return the results as list of tuples
        (parameters, values) as required by qcodes measurement context manager.

        Parameters
        ----------
        **kwargs :
            timestamps: Set True if timestamp data is to be included in the
                    results. Not implemented yet.
        Returns
        -------
        dict
            Results, list with one tuple for each subscribed parameter. Tuple
            contains (parameter, measurement_data).

        #TODO: Handle multiple bursts etc.
        """
        data = {}
        results = []
        for buffer in self.buffers:
            buffer.stop()
            data[buffer] = buffer.read()
            for param in buffer._subscribed_parameters:
                results.append((param, flatten_array(data[buffer][param.name])))
                if kwargs.get("timestamps", False):
                    # TODO: Add option to include timestamps here.
                    pass
        return results

    def _relabel_instruments(self) -> None:
        """
        Changes the labels of all instrument channels to the
        corresponding name defined in the measurement script.
        Has to be done after mapping!
        """
        for gate, parameters in self.gate_parameters.items():
            for key, parameter in parameters.items():
                parameter.label = f"{gate} {key}"

    def _add_datetime_to_metadata_if_empty(self, *args, add_datetime_to_metadata: bool = True, **kwargs):
        if add_datetime_to_metadata:
            try:
                metadata = self.metadata
                if not metadata.measurement.datetime:
                    metadata.measurement.datetime = datetime.now()
            except Exception as ex:
                print(f"Datetime could not be added to metadata: {ex}")

    def _add_data_to_metadata(self, *args, add_data_to_metadata: bool = True, **kwargs):
        # Add script and parameters to metadata
        if add_data_to_metadata:
            try:
                metadata = self.metadata
                cls = type(self)
                if not metadata.measurement.data:
                    metadata.measurement.data = []
                datalist = metadata.measurement.data
                db_location = qc.config.core.db_location
                data = MeasurementData.create(f"{cls.__name__}Data", "sqlite3", db_location)
                datalist.append(data)
            except Exception as e:
                print(f"Data could not be added to metadata: {e}")

    def _insert_metadata_into_db(self, *args, insert_metadata_into_db: bool = True, **kwargs):
        if insert_metadata_into_db:
            try:
                metadata = self.metadata
                metadata.save_to_db()
            except Exception as e:
                print(f"Metadata could not inserted into database: {e}")


class VirtualGate:
    """Virtual Gate"""

    def __init__(self):
        self._functions = []

    @property
    def functions(self):
        """List of equipment Functions, the virtual gate shall have."""
        return self._functions

    @functions.setter
    def functions(self, functions: MutableSequence):
        self._functions = functions


class CustomSweep(AbstractSweep):
    """
    Custom sweep from array of setpoints.

    Args:
        param: Qcodes parameter to sweep.
        setpoints: Array of setpoints.
        delay: Time in seconds between two consequtive sweep points
    """

    def __init__(
        self,
        param: _BaseParameter,
        setpoints: np.ndarray,
        delay: float = 0,
        post_actions: ActionsT = (),
    ):
        self._param = param
        self._setpoints = setpoints
        self._num_points = len(setpoints)
        self._delay = delay
        self._post_actions = post_actions

    def get_setpoints(self) -> np.ndarray:
        """
        1D array of setpoints
        """
        return self._setpoints

    @property
    def param(self) -> _BaseParameter:
        return self._param

    @property
    def delay(self) -> float:
        return self._delay

    @property
    def num_points(self) -> int:
        return self._num_points

    @property
    def post_actions(self) -> ActionsT:
        return self._post_actions