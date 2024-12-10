"""This package provides classes for validating and defining a PMR.

The goal of these classes is to represent the PMR in a more
Pythonic way, rather than a dict of vavlues.

The classes should also provide some common helper methods for
traversing the information of the PMR, but not functions for
directly affecting the K8s cluster based on the PMR.

This is similar to how the K8s python clients have classes
for representing the objects and different methods for doing operations
with them.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Dict, List

import jsonschema

from profiles_management.pmr.schema import RESOURCE_QUOTA_SCHEMA

log = logging.getLogger(__name__)


class UserKind(StrEnum):
    """Class representing the kind of the user."""

    USER = "user"
    SERVICE_ACCOUNT = "service-account"


class ContributorRole(StrEnum):
    """Class representing the role of the user."""

    ADMIN = "admin"
    EDIT = "edit"
    VIEW = "view"


@dataclass
class Contributor:
    """Class representing which users should have access to a Profile."""

    name: str
    role: ContributorRole


@dataclass
class Owner:
    """Class representing the owner field of a Profile."""

    name: str
    kind: UserKind


@dataclass
class Profile:
    """Class representing a Profile and its Contributors."""

    name: str
    owner: Owner
    resources: Dict[str, Any]
    contributors: List[Contributor]

    # https://docs.python.org/3/library/dataclasses.html#post-init-processing
    def __post_init__(self):
        """Validate resourceQuota after values have been initialised."""
        log.info("Validating ResourceQuota for Profile: %s", self.name)
        jsonschema.validate(self.resources, RESOURCE_QUOTA_SCHEMA)
        log.info("ResourceQuota is valid.")


class ProfilesManagementRepresentation:
    """A class representing the Profiles and Contributors."""

    profiles: dict[str, Profile] = {}

    def __init__(self, profiles: List[Profile] = []):
        """Initialise based on a list of Profiles.

        If a list of Profiles is given, then the internal dict will be initialised
        based on this list.
        """
        for profile in profiles:
            self.add_profile(profile)

    def has_profile(self, name: str | None) -> bool:
        """Check if given Profile name is part of the PMR."""
        return name in self.profiles

    def add_profile(self, profile: Profile):
        """Add a Profile to internal dict of Profiles."""
        self.profiles[profile.name] = profile

    def remove_profile(self, name: str | None):
        """Remove Prorifle from PMR, if it exists."""
        if name not in self.profiles:
            log.info("Profile %s not in PMR.", name)
            return

        del self.profiles[name]

    def __str__(self) -> str:
        """Print PMR in human friendly way."""
        repr = "Profiles:\n"
        for _, profile in self.profiles.items():
            repr += f"-  {profile.name}: "
            for c in profile.contributors:
                repr += f"({c.name}, {c.role.value}) "
            repr += "\n"

        return repr

    def __repr__(self) -> str:
        """Print PMR in human friendly way."""
        return self.__str__()
