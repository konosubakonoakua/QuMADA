"""
Created on Thu Jan  5 16:27:28 2023

@author: till3
"""

# most of the drivers only need a couple of these... moved all up here for clarity below
from __future__ import annotations

import threading
from time import sleep

import numpy as np
from qcodes.instrument import Instrument
from qcodes.validators import validators as vals

#%%


class DummyDac(Instrument):
    def __init__(self, name, trigger_event=threading.Event(), **kwargs):
        super().__init__(name, **kwargs)

        self._is_triggered = trigger_event

        self.add_parameter("voltage", unit="V", set_cmd=None, vals=vals.Numbers(-10, 10))
        self.voltage.set(0)

        self.add_function("force_trigger", call_cmd=self._is_triggered.set)

    def _run_ramp(self, start, stop, duration, stepsize=0.01):
        num_points = int((stop - start) / stepsize)
        for setpoint in np.linspace(start, stop, num_points):
            self.voltage(setpoint)
            sleep(duration / num_points)

    def ramp(self, start, stop, duration, stepsize=0.01):
        self.thread = threading.Thread(
            target=self._run_ramp,
            args=(self, start, stop, duration, stepsize),
            daemon=True,
        )
        self.thread.start()

    def _run_triggered_ramp(self, start, stop, duration, stepsize=0.01):
        _is_triggered = self._is_triggered.wait()
        num_points = int((stop - start) / stepsize)
        for setpoint in np.linspace(start, stop, num_points):
            self.voltage(setpoint)
            sleep(duration / num_points)

    def _triggered_ramp(self, start, stop, duration, stepsize=0.01):
        self.thread = threading.Thread(
            target=self._run_triggered_ramp,
            args=(start, stop, duration, stepsize),
            daemon=True,
        )
        self.thread.start()
