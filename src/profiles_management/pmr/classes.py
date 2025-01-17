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

from pydantic import BaseModel, ConfigDict, TypeAdapter
from pydantic.alias_generators import to_camel

log = logging.getLogger(__name__)


# Classes for ResourceQuotaSpec
class Operator(StrEnum):
    """Class for the Operator in MetchExpression of ResourceQuotaSpec."""

    In = "In"
    NotIn = "NotIn"
    Exists = "Exists"
    DoesNotExist = "DoesNotExist"


class ScopedResourceSelectorRequirement(BaseModel):
    """Class for objects of matchExpressions of ResourceQuotaSpec.

    Args:
        operator: Represents a scope's relationship to a set of values.
        scope_name: The name of the scope that the selector applies to.
        values: An array of string values. If the operator is In or NotIn, the values array must be
                non-empty

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    operator: Operator
    scope_name: str
    values: Optional[List[str]] = None


class ScopeSelector(BaseModel):
    """Class for ScopeSelector of ResourceQuotaSpec.

    Args:
        match_expressions: A list of scope selector requirements by scope of the resources

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    match_expressions: List[ScopedResourceSelectorRequirement]


class ResourceQuotaSpecModel(BaseModel):
    """Class for K8s ResourceQuotaSpec.

    Args:
        hard: is the set of desired hard limits for each named resource.
        scope_selector: collection of filters like scopes that must match each object tracked by a
                        quota.
        scopes: A collection of filters that must match each object tracked by a quota

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    hard: Optional[Dict[str, Any]] = None
    scope_selector: Optional[ScopeSelector] = None
    scopes: Optional[List[str]] = None


# Classes for rest of the PMR
class UserKind(StrEnum):
    """Class representing the kind of the user as a Profile owner."""

    USER = "user"
    SERVICE_ACCOUNT = "service-account"


class ContributorRole(StrEnum):
    """Class representing the role of the user as a Contributor."""

    ADMIN = "admin"
    EDIT = "edit"
    VIEW = "view"


class Contributor(BaseModel):
    """Class representing what kind of access a user should have in a Profile.

    Args:
        name: The name of the Contributor. Will be used in RoleBinding and
              AuthorizationPolicy created for the Contributor.
        role: The Contributor's role. Matches what KFAM expects as annotations
              in RoleBindings.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    name: str
    role: ContributorRole


class Owner(BaseModel):
    """Class representing the owner of a Profile.

    Args:
        name: The name of the owner. Will be used in RoleBinding and
              AuthorizationPolicy created for the owner by the Profiles Controller.
        kind: The kind of the owner, to distinguish between users and ServiceAccounts.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    name: str
    kind: UserKind


class Profile(BaseModel):
    """Class representing a Profile and its Contributors.

    Args:
        name: The name of the Profile, and namespace that will be created.
        owner: The owner of the Profile.
        resources: The ResourceQuotaSpec that should be applied in the Profile.
        contributors: The Contributors that should have access in the Profile.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    name: str
    owner: Owner
    resources: Optional[ResourceQuotaSpecModel] = None
    contributors: Optional[List[Contributor]] = []

    _contributors_dict: dict[str, List[ContributorRole]]

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # Group contributors based on user name for more efficient retrieval
        self._contributors_dict = {}
        if self.contributors is None:
            return

        for contributor in self.contributors:
            self._contributors_dict[contributor.name] = self._contributors_dict.get(
                contributor.name, []
            ) + [contributor.role]


class ProfilesManagementRepresentation:
    """A class representing the Profiles and Contributors.

    Args:
        profiles_list: List of Profiles that should exist in the PMR.

    Raises:
        ValidationError: From pydantic if the validation failed.
    """

    def __init__(self, profiles_list: List[Profile] = []):
        """Initialise based on a list of Profiles.

        If a list of Profiles is given, then the internal dict will be initialised
        based on this list.

        Args:
            profiles_list: List of Profiles to initialise PMR with.

        Raises:
            ValidationError: From pydantic if the validation failed.
        """
        TypeAdapter(List[Profile]).validate_python(profiles_list)
        self._profiles = {}
        self._profiles_list = profiles_list

    @property
    def profiles(self) -> Dict[str, Profile]:
        """Map of Profiles with the names as keys."""
        profiles_dict = {}

        if not self._profiles:
            for profile in self._profiles_list or []:
                profiles_dict[profile.name] = profile

            self._profiles = profiles_dict

        return self._profiles

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

            if profile.contributors is None:
                continue

            for c in profile.contributors:
                repr += f"({c.name}, {c.role.value}) "
            repr += "\n"

        return repr

    def __repr__(self) -> str:
        """Print PMR in human friendly way."""
        return self.__str__()
