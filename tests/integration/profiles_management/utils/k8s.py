import logging
from pathlib import Path
from typing import List

import pytest
import tenacity
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import GenericGlobalResource, GenericNamespacedResource
from lightkube.resources.core_v1 import Namespace

# silence default INFO logs of httpx, to avoid seeing
# a log line for every request that happens with that module
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


# For errors when a Namespace exists while it shouldn't
class ObjectStillExistsError(Exception):
    """Exception for when a K8s object exists, while it should have been removed."""

    pass


def get_name(res: GenericNamespacedResource | GenericGlobalResource) -> str:
    """Return the name from a generic lightkube resource.

    Args:
        res: The resource to get its name from metadata.name

    Raises:
        ValueError: if the object doesn't have metadata or metadata.name

    Returns:
        The name of the object from its metadata.
    """
    if not res.metadata:
        pytest.xfail("Couldn't detect name, object has no metadata: %s" % res)

    if not res.metadata.name:
        pytest.xfail("Couldn't detect name, object has no name field: %s" % res)

    return res.metadata.name


def load_namespaced_objects_from_file(
    file_path: str, context: dict = {}
) -> List[codecs.AnyResource]:
    """Load only namespaced objects from a YAML file.

    Args:
        file_path: The yaml file to load K8s resources from.
        context: jinja context to substitute when loading from yaml file.

    Returns:
        List of namespaced resource objects that were loaded.
    """
    resources: List[codecs.AnyResource] = []

    for resource in codecs.load_all_yaml(Path(file_path).read_text(), context):
        if resource.metadata is None:
            pytest.xfail("Resource doesn't have any metadata: %s" % resource)

        if not resource.metadata.namespace:
            continue

        resources.append(resource)

    return resources


@tenacity.retry(stop=tenacity.stop_after_delay(60), wait=tenacity.wait_fixed(2), reraise=True)
def ensure_namespace_exists(ns: str, client: Client):
    """Check if the name exists with retries.

    The retries will catch the 404 errors if the namespace doesn't exist.

    Args:
        ns: The namespace to be checked if it exists.
        client: The lightkube client to use for talking to K8s.

    Raises:
        ApiError: From lightkube, if there was an error aside from 404.
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


@tenacity.retry(stop=tenacity.stop_after_delay(300), wait=tenacity.wait_fixed(5), reraise=True)
def ensure_namespace_is_deleted(ns: str, client: Client):
    """Check if the name doesn't exist with retries.

    The function will keep retrying until the namespace is deleted, and handle the
    404 error once it gets deleted.

    Args:
        ns: The namespace to be checked if it is deleted.
        client: The lightkube client to use for talking to K8s.

    Raises:
        ApiError: From lightkube, if there was an error aside from 404.
        ObjectStillExistsError: If the Profile's namespace was not deleted after retries.
    """
    log.info("Checking if namespace exists: %s", ns)
    try:
        client.get(Namespace, name=ns)
        log.info('Namespace "%s" exists, retrying...', ns)
        raise ObjectStillExistsError("Namespace %s is not deleted.")
    except ApiError as e:
        if e.status.code == 404:
            log.info('Namespace "%s" doesn\'t exist!', ns)
            return
        else:
            # Raise any other error
            raise
