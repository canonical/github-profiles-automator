"""Generic helpers for manipulating K8s objects, via lightkube."""

from lightkube.generic_resource import GenericGlobalResource, GenericNamespacedResource


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
        raise ValueError("Couldn't detect name, object has no metadata: %s" % res)

    if not res.metadata.name:
        raise ValueError("Couldn't detect name, object has no name field: %s" % res)

    return res.metadata.name
