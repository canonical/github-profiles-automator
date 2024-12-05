"""Generic helpers for manipulating K8s objects, via lightkube."""

import logging

import tenacity
from lightkube import Client
from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import GenericGlobalResource, GenericNamespacedResource
from lightkube.resources.core_v1 import Namespace

log = logging.getLogger(__name__)


client = Client(field_manager="profiles-automator-lightkube")


def get_name(res: GenericNamespacedResource | GenericGlobalResource) -> str:
    """Return the name from generic lightkube resource.

    Args:
        res: The resource to get it's name from metadata.name

    Raises:
        ValueError: if the object doesn't have metadata or metadata.name

    Returns:
        The name of the object from its metadata.
    """
    if not res.metadata:
        raise ValueError("Coldn't detect name, object has no metadata: %s" % res)

    if not res.metadata.name:
        raise ValueError("Couldn't detect name, object has no name field: %s" % res)

    return res.metadata.name


def get_namespace(res: GenericNamespacedResource) -> str:
    """Return the name from generic lightkube resource.

    Args:
        res: The namespaced resource to get the namespace of

    Raises:
        ValueError: if the object doesn't have metadata or metadata.namespace

    Returns:
        The namespace of the resource from its metadata.
    """
    if not res.metadata:
        raise ValueError("Couldn't detect namespace, object has no metadata: %s" % res)

    if not res.metadata.namespace:
        raise ValueError("Couldn't detect namespace from metadata: %s" % res)

    return res.metadata.namespace


@tenacity.retry(stop=tenacity.stop_after_delay(60), wait=tenacity.wait_fixed(2), reraise=True)
def ensure_namespace_exists(ns: str, client: Client):
    """Check if the name exists with retries.

    The retries will catch the 404 errors if the namespace doesn't exist.
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
