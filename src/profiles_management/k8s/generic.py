"""Generic helpers for manipulating K8s objects, via lightkube."""

from lightkube import Client
from lightkube.generic_resource import GenericGlobalResource, GenericNamespacedResource

client = Client(field_manager="profiles-automator-lightkube")


def get_name(res: GenericNamespacedResource | GenericGlobalResource) -> str:
    """Return the name from generic lightkube resource.

    Raises ValueError if the object doesn't have metadata or metadata.name
    """
    if not res.metadata:
        raise ValueError("Coldn't detect name, object has no metadata: %s" % res)

    if not res.metadata.name:
        raise ValueError("Couldn't detect name, object has no name field: %s" % res)

    return res.metadata.name


def get_namespace(res: GenericNamespacedResource) -> str:
    """Return the name from generic lightkube resource.

    Raises ValueError if the object doesn't have metadata or metadata.namespace
    """
    if not res.metadata:
        raise ValueError("Couldn't detect namespace, object has no metadata: %s" % res)

    if not res.metadata.namespace:
        raise ValueError("Couldn't detect namespace from metadata: %s" % res)

    return res.metadata.namespace
