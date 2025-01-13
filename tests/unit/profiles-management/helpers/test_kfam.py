import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta

from profiles_management.helpers.kfam import has_kfam_annotations, resource_is_for_profile_owner


def test_kfam_resource():
    resource = GenericNamespacedResource(
        metadata=ObjectMeta(name="test", annotations={"role": "admin", "user": "test"})
    )

    assert has_kfam_annotations(resource)


def test_non_kfam_resource():
    resource = GenericNamespacedResource(metadata=ObjectMeta(name="test"))

    assert not has_kfam_annotations(resource)


@pytest.mark.parametrize(
    "resource",
    [
        GenericNamespacedResource(metadata=ObjectMeta(name="namespaceAdmin")),
        GenericNamespacedResource(metadata=ObjectMeta(name="ns-owner-access-istio")),
    ],
)
def test_profile_owner_resource(resource):
    assert resource_is_for_profile_owner(resource)


def test_non_profile_owner_resource():
    resource = GenericNamespacedResource(metadata=ObjectMeta(name="random"))

    assert not resource_is_for_profile_owner(resource)
