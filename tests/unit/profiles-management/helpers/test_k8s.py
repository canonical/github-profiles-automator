import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta

from profiles_management.helpers.k8s import get_annotations, to_rfc1123_compliant


def test_annotations():
    resource = GenericNamespacedResource(
        metadata=ObjectMeta(name="test", annotations={"test": "value"})
    )

    assert get_annotations(resource) == {"test": "value"}


def test_no_annotations():
    resource = GenericNamespacedResource(metadata=ObjectMeta(name="test"))

    assert get_annotations(resource) == {}


@pytest.mark.parametrize(
    "name,expected",
    [
        ("kimonas@canonical.com", "kimonas-canonical-com"),
        (
            "I-had-to-think-of-a-reeeally-long-string-to-use-for-the-test-which-was-tough",
            "i-had-to-think-of-a-reeeally-long-string-to-use-for-the-test-wh",
        ),
        ("-=shouldn't have trailing dashes!", "shouldn-t-have-trailing-dashes"),
        ("", ""),
        ("abcdefg", "abcdefg"),
        ("1234", "1234"),
        ("$%%@#", ""),
    ],
)
def test_rfc1123(name, expected):
    assert len(to_rfc1123_compliant(name)) < 64
    assert to_rfc1123_compliant(name) == expected
