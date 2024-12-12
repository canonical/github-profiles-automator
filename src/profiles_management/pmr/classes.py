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
from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, TypeAdapter

log = logging.getLogger(__name__)


# Classes for ResourceQuotaSpec
class Operator(StrEnum):
    """Pydantic class for the Operator in MetchExpression of ResourceQuotaSpec."""

    In = "In"
    NotIn = "NotIn"
    Exists = "Exists"
    DoesNotExist = "DoesNotExist"


class ScopedResourceSelectorRequirement(BaseModel, extra="forbid"):
    """Pydantic class for objects of matchExpressions of ResourceQuotaSpec.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    operator: Operator
    scope_name: str
    values: Optional[List[str]] = None


class ScopeSelector(BaseModel, extra="forbid"):
    """Pydantic class for ScopeSelector of ResourceQuotaSpec.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    match_expressions: List[ScopedResourceSelectorRequirement]


class ResourceQuotaSpecModel(BaseModel, extra="forbid"):
    """Pydantic class for ResourceQuotaSpec.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    hard: Optional[Dict[str, Any]] = None
    scope_selector: Optional[ScopeSelector] = None
    scopes: Optional[List[str]] = None


# Classes for rest of the PMR
class UserKind(StrEnum):
    """Class representing the kind of the user as a Profile owner."""

    USER = "user"
    SERVICE_ACCOUNT = "service-account"


class ContributorRole(StrEnum):
    """Class representing the role of the user as a contributor."""

    ADMIN = "admin"
    EDIT = "edit"
    VIEW = "view"


class Contributor(BaseModel):
    """Class representing what kind of access a user should have in a Profile.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    name: str
    role: ContributorRole


class Owner(BaseModel):
    """Class representing the owner of a Profile.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    name: str
    kind: UserKind


class Profile(BaseModel):
    """Class representing a Profile and its Contributors.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    name: str
    owner: Owner
    resources: Optional[ResourceQuotaSpecModel] = None
    contributors: Optional[List[Contributor]] = []


class ProfilesManagementRepresentation:
    """A class representing the Profiles and Contributors.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    profiles: dict[str, Profile] = {}

    def __init__(self, profiles_list: List[Profile] = []):
        """Initialise based on a list of Profiles.

        If a list of Profiles is given, then the internal dict will be initialised
        based on this list.

        Args:
            profiles_list: List of Profiles to initialise PMR with.

        Raises:
            ValidationError: From pydantic if the validation failed.
        """
        # validate the input type
        TypeAdapter(List[Profile]).validate_python(profiles_list)

        self.profiles = {}
        for profile in profiles_list:
            self.add_profile(profile)

    def has_profile(self, name: str) -> bool:
        """Check if given Profile name is part of the PMR.

        Args:
            name: The name of the Profile to check if it exists in PMR.

        Returns:
            True / False depending if the Profile was found.
        """
        return name in self.profiles

    def add_profile(self, profile: Profile) -> None:
        """Add a Profile to internal dict of Profiles.

        Args:
            profile: The PMR Profile to add to the PMR.
        """
        self.profiles[profile.name] = profile

    def remove_profile(self, name: str):
        """Remove Prorifle from PMR, if it exists.

        Args:
            name: The name of the Profile to remove from PMR.
        """
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
