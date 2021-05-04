#!/usr/bin/env python3
"""
Example template measurement script
"""

from typing import Any, Sequence

from qcodes.utils.dataset.doNd import do1d

from qtools.measurement.measurement import VirtualGate
from qtools.data.measurement import FunctionType as ft


properties: dict[Any, Any] = {
    "sample_name": "s20210434",
    "device_name": "d01",
    "volt_start": 0,
    "volt_end": 2,
    "volt_step": .1,
    "volt_delay": .05,
    "repetitions": 1,
    "backsweep": True,
    "source_drain": {
        "frequency": 173,
        "amplitude": 1,
        "voltage_divider": 1e-4,
        "sensitivity": "",
        "reserve": "",
        "time_constant": 1e-3
    },
    "topgate": {
        "current_range": "auto",
    },
    "barriers": {
        "voltage": 2,
        "wait": 2
    },
    "safety_limit_leakage": 1e-8,
    "safety_limit_curr": 1e-6
}


def setup():
    """
    Setup your virtual gates here. Create the gate objects and
    add functions to them.

    FunctionType is available at qtools.data.measurement.FunctionType

    Returns:
        [dict]: Virtual Gates with their respective names
    """
    # initialize gates and their functions
    source_drain = VirtualGate()
    source_drain.functions.append(ft.VOLTAGE_SOURCE_AC)
    source_drain.functions.append(ft.CURRENT_SENSE)

    topgate = VirtualGate()
    topgate.functions.append(ft.VOLTAGE_SOURCE)
    topgate.functions.append(ft.CURRENT_SENSE)

    barriers = [VirtualGate() for i in range(2)]
    for barrier in barriers:
        barrier.functions.append(ft.VOLTAGE_SOURCE)

    # TODO: Parameter scaling

    return {"source_drain": source_drain, "topgate": topgate, "barriers": barriers}


def run(topgate: VirtualGate,
        source_drain: VirtualGate,
        barriers: Sequence[VirtualGate]):
    """
    Run the measurements. Use your created virtual gates as parameters.
    """
    volt_start = float(properties["volt_start"])
    volt_end = float(properties["volt_end"])
    volt_step = float(properties["volt_step"])
    volt_delay = float(properties["volt_delay"])
    num_points = int((volt_end - volt_start)/volt_step)

    repetitions = properties["repetitions"]

    for i in range(repetitions):
        data_up = do1d(topgate.volt, volt_start, volt_end, num_points,
                       volt_delay, source_drain.current)
        print(data_up)

        data_down = do1d(topgate.volt, volt_end, volt_start, num_points,
                         volt_delay, source_drain.current)
        print(data_down)


def break_condition(topgate: VirtualGate,
                    source_drain: VirtualGate,
                    barriers: Sequence[VirtualGate]) -> bool:
    """
    Break condition for the measurement. Use your created virtual gates as parameters.

    Returns:
        bool: True, if break condition is met, False otherwise.
    """
    return False
