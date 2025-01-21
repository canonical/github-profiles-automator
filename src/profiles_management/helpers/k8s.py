"""Generic helpers for manipulating K8s objects, via lightkube."""

import logging
import re

import tenacity
from lightkube import Client
from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import GenericGlobalResource, GenericNamespacedResource
from lightkube.resources.core_v1 import Namespace
from lightkube.resources.rbac_authorization_v1 import RoleBinding

log = logging.getLogger(__name__)


# For errors when a Namespace exists while it shouldn't
class ObjectStillExistsError(Exception):
    """Exception for when a K8s object exists, while it should have been removed."""

    pass


def get_name(res: GenericNamespacedResource | GenericGlobalResource | RoleBinding) -> str:
    """Return the name from generic lightkube resource.

    Args:
        res: The resource to get it's name from metadata.name

    Raises:
        ValueError: if the object doesn't have metadata or metadata.name

    Returns:
        The name of the object from its metadata.
    """
    if not res.metadata:
        raise ValueError("Couldn't detect name, object has no metadata: %s" % res)

    if not res.metadata.name:
        raise ValueError("Couldn't detect name, object has no name field: %s" % res)

    return res.metadata.name


def get_annotations(res: GenericNamespacedResource | RoleBinding) -> dict[str, str]:
    """Return annotations of a RoleBinding or AuthorizationPolicy, or an empty dict.

    Args:
        res: The resource to return its annotations.

    Returns:
        A dictionary with the annotations, or empty dictionary if no annotations exist.
    """
    if res.metadata and res.metadata.annotations:
        return res.metadata.annotations

    return {}


def to_rfc1123_compliant(name: str) -> str:
    """Transform a given string into an RFC 1123-compliant string.

    The resulting string will:
    1. Contain at most 63 characters.
    2. Contain only lowercase alphanumeric characters or '-'.

    Args:
        name: The input string to transform.

    Returns:
        The RFC 1123-compliant string.
    """
    if len(name) == 0:
        raise ValueError("Can't convert to valid RFC1123 an empty string.")

    compliant_str = name.lower()
    compliant_str = re.sub(r"[^a-z0-9-]", "-", compliant_str)

    compliant_str = compliant_str.lstrip("-").rstrip("-")

    return compliant_str[:63]


@tenacity.retry(stop=tenacity.stop_after_delay(300), wait=tenacity.wait_fixed(5), reraise=True)
def ensure_namespace_is_deleted(namespace: str, client: Client):
    """Check if the name doesn't exist with retries.

    The function will keep retrying until the namespace is deleted, and handle the
    404 error once it gets deleted.

    Args:
        namespace: The namespace to be checked if it is deleted.
        client: The lightkube client to use for talking to K8s.

    Raises:
        ApiError: From lightkube, if there was an error aside from 404.
        ObjectStillExistsError: If the Profile's namespace was not deleted after retries.
    """
    log.info("Checking if namespace exists: %s", namespace)
    try:
        client.get(Namespace, name=namespace)
        log.info('Namespace "%s" exists, retrying...', namespace)
        raise ObjectStillExistsError("Namespace %s is not deleted.")
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist!', namespace)
            return
        else:
            # Raise any other error
            raise


@tenacity.retry(stop=tenacity.stop_after_delay(60), wait=tenacity.wait_fixed(2), reraise=True)
def ensure_namespace_exists(ns: str, client: Client):
    """Check if the namespace exists with retries.

    The retries will catch the 404 errors if the namespace doesn't exist.

    Args:
        ns: The namespace to ensure exists.
        client: The lightkube client to use.

    Raises:
        ApiError: API errors that might occur while trying to fetch the Namespace.
    """
    log.info("Checking if namespace exists: %s", ns)
    try:
        client.get(Namespace, name=ns)
        log.info('Namespace "%s" exists!', ns)
        return ns
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist, retrying... ', ns)
            raise
        else:
            # Raise any other error
            raise
