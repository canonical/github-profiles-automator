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
from enum import Enum
from pathlib import Path
from typing import List

import jsonschema
import yaml

from profiles_management.pmr.schema import PMR_SCHEMA

log = logging.getLogger(__name__)


class UserKind(Enum):
    """Class representing the kind of the user."""

    USER = 1
    SERVICE_ACCOUNT = 2


class ContributorRole(Enum):
    """Class representing the role of the user."""

    ADMIN = "admin"
    EDIT = "edit"
    VIEW = "view"


class Contributor:
    """Class representing which users should have access to a Profile."""

    name: str
    role: ContributorRole

    def __init__(self, contributor: dict = {}):
        self.name = contributor["name"]

        role = contributor["role"]
        if role == ContributorRole.ADMIN.value:
            self.role = ContributorRole.ADMIN
        elif role == ContributorRole.EDIT.value:
            self.role = ContributorRole.EDIT
        elif role == ContributorRole.VIEW.value:
            self.role = ContributorRole.VIEW


class Owner:
    """Class representing the owner field of a Profile."""

    name: str
    kind: UserKind

    def __init__(self, owner: dict = {}):
        self.name = owner["name"]
        self.kind = owner["kind"]


class Profile:
    """Class representing a Profile and its Contributors."""

    name = ""
    owner: Owner
    resources = {}
    contributors: List[Contributor] = []

    def __init__(self, profile: dict = {}):
        """Initialise a Profile based on a dict representation."""
        self.name = profile["name"]
        self.owner = Owner(profile["owner"])
        self.resources = profile.get("resources", {})
        self.contributors = [Contributor(c) for c in profile["contributors"]]

    def has_contributor(self, name: str, role: ContributorRole) -> bool:
        """Check if the Profile has a contributor with specific role."""
        for contributor in self.contributors:
            if contributor.name != name:
                continue

            if contributor.role != role:
                continue

            log.info("Profile %s has contributor (%s, %s)", self.name, name, role.value)
            return True

        log.info("Profile %s doesn't have contributor (%s, %s)", self.name, name, role.value)
        return False


class ProfilesManagementRepresentation:
    """A class representing the Profiles and Contributors."""

    profiles: dict[str, Profile] = {}

    def __init__(self, pmr: dict = {}, pmr_path=""):
        """Initialise based on a PMR dict.

        If a PMR file path is given, then the contents of that file
        will be used to construct the PMR class instance.
        """
        log.info("Creataing ProfilesManagementRepresentation object")
        self.profiles = {}

        # If a pth is given, then use this
        if pmr_path:
            log.info("Will try to load YAML contents from: %s", pmr_path)
            pmr = yaml.safe_load(Path(pmr_path).read_text())

        if not pmr:
            raise ValueError("No PMR dict or file path was given.")

        # Ensure the PMR is valid before doing any parsing. Afterwards
        # all functions should expect the PMR will have the required
        # fields and with correct types.
        self._validate_pmr(pmr)

        for profile in pmr["profiles"]:
            self.profiles[profile["name"]] = Profile(profile)

    def _validate_pmr(self, pmr: dict):
        """Validate if the PMR aligns with the schema."""
        log.info("Validating if the PMR aligns with the schema")
        jsonschema.validate(pmr, PMR_SCHEMA)
        log.info("PMR dict is valid.")

    def has_profile(self, name: str | None) -> bool:
        """Check if given Profile name is part of the PMR."""
        # naive iteration over all profiles
        return name in self.profiles

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
