import pytest
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta

from profiles_management.helpers.k8s import get_annotations, to_rfc1123_compliant


@pytest.mark.parametrize(
    "resource,expected_annotations",
    [
        (
            GenericNamespacedResource(
                metadata=ObjectMeta(name="test", annotations={"test": "value"})
            ),
            {"test": "value"},
        ),
        (GenericNamespacedResource(metadata=ObjectMeta(name="test")), {}),
    ],
)
def test_annotations(resource, expected_annotations):
    assert get_annotations(resource) == expected_annotations


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
