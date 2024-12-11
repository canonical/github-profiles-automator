# GitHub Profiles Automator

[![CI](https://github.com/canonical/github-profiles-automator/actions/workflows/integrate.yaml/badge.svg)](https://github.com/canonical/github-profiles-automator/actions/workflows/integrate.yaml)
[![On Pull Request](https://github.com/canonical/github-profiles-automator/actions/workflows/on_pull_request.yaml/badge.svg)](https://github.com/canonical/github-profiles-automator/actions/workflows/on_pull_request.yaml)
[![On Push](https://github.com/canonical/github-profiles-automator/actions/workflows/on_push.yaml/badge.svg)](https://github.com/canonical/github-profiles-automator/actions/workflows/on_push.yaml)
[![Publish](https://github.com/canonical/github-profiles-automator/actions/workflows/publish.yaml/badge.svg)](https://github.com/canonical/github-profiles-automator/actions/workflows/publish.yaml)
[![Release charm to other tracks and channels](https://github.com/canonical/github-profiles-automator/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/github-profiles-automator/actions/workflows/release.yaml)

Github Profiles Automator charm is focused on updating Profiles and
RoleBindings / AuthorizationPolicies for contributors in a Kubeflow
cluster based on a central source of truth, a ProfileManagementRepresentation
(PMR) defined in a file in a GitHub repo.

## Profiles Management Representation

This repository also contains the code for defining Profiles and Contributors in a source-agnostic
way, please refer to the [README.md](src/profiles_management/README.md) for more information.
