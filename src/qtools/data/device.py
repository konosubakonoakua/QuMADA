#!/usr/bin/env python3
"""
Representations of domain objects (Devices).
"""

from dataclasses import dataclass, field
from typing import Any

from qtools.data.domain import DomainObject
from qtools.data.db import (get_factory_by_id, save_or_update_factory,
                            get_wafer_by_id, save_or_update_wafer,
                            get_sample_by_id, save_or_update_sample,
                            get_design_by_id, save_or_update_design,
                            get_device_by_id, save_or_update_device)


@dataclass
class Factory(DomainObject):
    """Represents the database entry of a factory."""
    description: str

    @classmethod
    def create(cls, name: str, description: str, **kwargs):
        kwargs.update({
            "name": name,
            "description": description,
        })
        return super(cls, cls)._create(**kwargs)

    @classmethod
    def load_from_db(cls, pid: str):
        data = get_factory_by_id(pid)
        return cls(**data)

    def save_to_db(self):
        response = save_or_update_factory(self.description,
                                          self.name,
                                          self.pid)
        self._handle_db_response(response)


@dataclass
class Wafer(DomainObject):
    """Represents the database entry of a wafer."""
    description: str
    productionDate: str

    @classmethod
    def create(cls, name: str, description: str, productionDate: str, **kwargs):
        kwargs.update({
            "name": name,
            "description": description,
            "productionDate": productionDate,
        })
        return super(cls, cls)._create(**kwargs)

    @classmethod
    def load_from_db(cls, pid: str):
        data = get_wafer_by_id(pid)
        return cls(**data)

    def save_to_db(self):
        response = save_or_update_wafer(self.description,
                                        self.name,
                                        self.productionDate,
                                        self.pid)
        self._handle_db_response(response)


@dataclass
class Sample(DomainObject):
    """Represents the database entry of a sample."""
    description: str
    wafer: Wafer

    @classmethod
    def create(cls, name: str, description: str, wafer: Wafer, **kwargs):
        kwargs.update({
            "name": name,
            "description": description,
            "wafer": wafer,
        })
        return super(cls, cls)._create(**kwargs)

    @classmethod
    def load_from_db(cls, pid: str):
        data = get_sample_by_id(pid)
        return cls(**data)

    def save_to_db(self):
        response = save_or_update_sample(self.description,
                                         self.name,
                                         self.wafer.name,
                                         self.pid)
        self._handle_db_response(response)


@dataclass
class Design(DomainObject):
    """Represents the database entry of a design."""
    wafer: Wafer
    factory: Factory
    sample: Sample
    mask: str
    creator: str
    allowedForMeasurementTypes: list[Any] = field(default_factory=list)
    # TODO: MeasurementTypes

    @classmethod
    def create(cls,
               name: str,
               wafer: Wafer,
               factory: Factory,
               sample: Sample,
               mask: str,
               creator: str,
               allowedForMeasurementTypes: list[Any],
               **kwargs):
        kwargs.update({
            "name": name,
            "wafer": wafer,
            "factory": factory,
            "sample": sample,
            "mask": mask,
            "creator": creator,
            "allowedForMeasurementTypes": allowedForMeasurementTypes,
        })
        return super(cls, cls)._create(**kwargs)

    @classmethod
    def load_from_db(cls, pid: str):
        data = get_design_by_id(pid)
        return cls(**data)

    def save_to_db(self):
        response = save_or_update_design(",".join(self.allowedForMeasurementTypes),
                                         self.creator,
                                         self.factory.name,
                                         self.mask,
                                         self.name,
                                         self.sample.name,
                                         self.wafer.name,
                                         self.pid)
        self._handle_db_response(response)


@dataclass
class Device(DomainObject):
    """Represents the database entry of a device."""
    design: Design
    sample: Sample

    @classmethod
    def create(cls, name: str, design: Design, sample: Sample, **kwargs):
        kwargs.update({
            "name": name,
            "design": design,
            "sample": sample,
        })
        return super(cls, cls)._create(**kwargs)

    @classmethod
    def load_from_db(cls, pid: str):
        data = get_device_by_id(pid)
        return cls(**data)

    def save_to_db(self):
        response = save_or_update_device(self.name,
                                         self.design.name,
                                         self.sample.name)
        self._handle_db_response(response)
