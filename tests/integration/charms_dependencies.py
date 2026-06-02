"""Dependency charms for integration tests."""

from charmed_kubeflow_chisme.testing import CharmSpec

ISTIO_BEACON_K8S = CharmSpec(charm="istio-beacon-k8s", channel="2/stable", trust=True)
ISTIO_K8S = CharmSpec(
    charm="istio-k8s",
    channel="2/stable",
    trust=True,
    config={"platform": ""},
)
KUBEFLOW_PROFILES = CharmSpec(charm="kubeflow-profiles", channel="latest/edge", trust=True)
