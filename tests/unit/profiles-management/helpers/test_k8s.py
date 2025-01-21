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


def test_rfc1123_non_alphanum_to_hyphen():
    name = "kimonas@canonical.com"

    assert to_rfc1123_compliant(name) == "kimonas-canonical-com"


def test_rfc1123_more_than_63_char_name():
    name = "I-had-to-think-of-a-reeeally-long-string-to-use-for-the-test-which-was-tough"

    assert len(name) > 63
    assert len(to_rfc1123_compliant(name)) == 63


def test_rfc1123_strip_starting_and_trailing_dashes():
    name = "-=shouldn't have trailing dashes!"

    assert to_rfc1123_compliant(name) == "shouldn-t-have-trailing-dashes"
