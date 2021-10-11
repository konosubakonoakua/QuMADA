#!/usr/bin/env python3
"""
Representations of domain objects (Measurements).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from qtools.data.apiclasses import get_all, get_by_id, save
from qtools.data.device import Device
from qtools.data.domain import DomainObject


@get_by_id
@get_all
@save(fn_name="saveOrUpdateTemplateParameter")
@dataclass
class TemplateParameter(DomainObject):
    """Represents the database entry of a template parameter."""
    type: str

    @classmethod
    def create(cls,
               name: str,
               type: str,
               **kwargs):
        """Creates a TemplateParameter object."""
        kwargs.update({
            "name": name,
            "type": type,
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all
@save(fn_name="saveOrUpdateMeasurementSettingScript")
@dataclass
class MeasurementSettingScript(DomainObject):
    """Represents the database entry of a measurement setting script."""
    script: str
    language: str
    allowedParameters: list[TemplateParameter] = field(default_factory=list)
    # TODO: allowedParameters

    @classmethod
    def create(cls,
               name: str,
               script: str,
               language: str,
               allowedParameters: list[TemplateParameter],
               **kwargs):
        """Creates a MeasurementSettingScript object."""
        kwargs.update({
            "name": name,
            "script": script,
            "language": language,
            "allowedParameters": allowedParameters,
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all(fn_name="measurementSettings")
@save(fn_name="saveOrUpdateMeasurementSettings")
@dataclass
class MeasurementSettings(DomainObject):
    """Represents the database entry of the measurement settings."""
    script: MeasurementSettingScript

    @classmethod
    def create(cls,
               name: str,
               script: MeasurementSettingScript,
               **kwargs):
        """Creates a MeasurementSettings object."""
        kwargs.update({
            "name": name,
            "script": script,
        })
        return super(cls, cls)._create(**kwargs)


class FunctionType(Enum):
    """Possible equipment functions"""
    VOLTAGE_SOURCE = 0
    VOLTAGE_SOURCE_AC = 1
    VOLTAGE_SENSE = 2
    CURRENT_SOURCE = 3
    CURRENT_SENSE = 4
    CURRENT_SENSE_AC = 5


@get_by_id
@get_all
@save(fn_name="saveOrUpdateEquipmentFunction")
@dataclass
class EquipmentFunction(DomainObject):
    """Represents the database entry of a equipment function."""
    functionType: FunctionType

    @classmethod
    def create(cls,
               name: str,
               functionType: FunctionType,
               **kwargs):
        """Creates an EquipmentFunction object."""
        kwargs.update({
            "name": name,
            "functionType": functionType,
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all
@save(fn_name="saveOrUpdateEquipment")
@dataclass
class Equipment(DomainObject):
    """Represents the database entry of an equipment."""
    description: str
    parameters: str
    functions: list[EquipmentFunction]
    # TODO: functions

    @classmethod
    def create(cls,
               name: str,
               description: str,
               parameters: str,
               functions: list[EquipmentFunction],
               **kwargs):
        """Creates an Equipment object."""
        kwargs.update({
            "name": name,
            "description": description,
            "parameters": parameters,
            "functions": functions,
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all
@save(fn_name="saveOrUpdateEquipmentInstance")
@dataclass
class EquipmentInstance(DomainObject):
    """Represents the database entry of an equipment instance."""
    type: Equipment
    parameter: str

    @classmethod
    def create(cls,
               name: str,
               type: Equipment,
               parameter: str,
               **kwargs):
        """Creates an EquipmentInstance object."""
        kwargs.update({
            "name": name,
            "type": type,
            "parameter": parameter,
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all(fn_name="measurementTypes")
@save(fn_name="saveOrUpdateMeasurementType")
@dataclass
class MeasurementType(DomainObject):
    """Represents the database entry of a measurement type."""
    model: str
    scriptTemplate: MeasurementSettingScript
    extractableParameters: str
    mapping: str
    equipments: list[Equipment] = field(default_factory=list)
    # TODO: equipments

    @classmethod
    def create(cls,
               name: str,
               model: str,
               scriptTemplate: MeasurementSettingScript,
               exctractableParameters: str,
               mapping: str,
               equipments: list[Equipment],
               **kwargs):
        """Creates a MeasurementType object."""
        kwargs.update({
            "name": name,
            "model": model,
            "scriptTemplate": scriptTemplate,
            "exctractableParameters": exctractableParameters,
            "mapping": mapping,
            "equipments": equipments
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all
@save(fn_name="saveOrUpdateExperiment")
@dataclass
class Experiment(DomainObject):
    """Represents the database entry of an experiment."""
    description: str
    user: str
    group: str
    measurementType: MeasurementType
    softwareNoiseFilters: str
    equipmentInstances: list[EquipmentInstance] = field(default_factory=list)
    # TODO: equipmentInstances

    @classmethod
    def create(cls,
               name: str,
               description: str,
               user: str,
               group: str,
               measurementType: MeasurementType,
               softwareNoiseFilters: str | None = None,
               equipmentInstances: list[EquipmentInstance] | None = None,
               **kwargs):
        """Creates an Experiment object."""
        kwargs.update({
            "name": name,
            "description": description,
            "user": user,
            "group": group,
            "softwareNoiseFilters": softwareNoiseFilters,
            "measurementType": measurementType,
            "equipmentInstances": equipmentInstances
        })
        return super(cls, cls)._create(**kwargs)


@get_by_id
@get_all
@save(fn_name="saveOrUpdateMeasurement")
@dataclass
class Measurement(DomainObject):
    """Represents the database entry of a measurement."""
    device: Device
    experiment: Experiment
    settings: MeasurementSettings
    measurementParameters: str

    @classmethod
    def create(cls,
               name: str,
               device: Device,
               experiment: Experiment,
               settings: MeasurementSettings,
               measurementParameters: str,
               **kwargs):
        """Creates a Measurement object."""
        kwargs.update({
            "name": name,
            "device": device,
            "experiment": experiment,
            "settings": settings,
            "measurementParameters": measurementParameters,
        })
        return super(cls, cls)._create(**kwargs)
