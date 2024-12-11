# Profiles Management Library

This module aims to be a standalone python module focused around:
1. Exposing the ProfileManagementRepresentation (PMR) classes
2. Functions that manipulate the cluster, based on a PMR

## Overview

The PMR consists of a list of classes for defining the Profiles and their
Contributors in an agnostic way. With this representation it's then possible
to write functions that manipulate a Kubeflow cluster based on a PMR.

The structure of the PMR, in YAML can be seen in the following section:
```yaml
profiles:
- name: ml-engineers
  owner:
    kind: User
    name: admin@canonical.com
  resources:
    hard:
      limits.cpu = "1"
  contributors:
  - name: kimonas@canonical.com
    role: admin
  - name: michal@canonical.com
    role: edit
  - name: andreea@canonical.com
    role: view
- name: data-engineers
  owner:
    kind: User
    name: admin@canonical.com
  contributors:
  - name: daniela@canonical.com
    role: edit
  - name: bart@canonical.com
    role: edit
  resources: {}
```

## Consume from Charms

This library is meant to be used by other Charms that will construct
a PMR and run the functions of this module to update the cluster's state.

Here's is some psudo-code that can show how a potential charm could
interact with the code of this library:
```python
from profiles_management.pmr import classes
from profiles_management import create_or_update_profiles


class ConsumerCharm(ops.CharmBase):

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.framework.observe(self.on.update_status, self.reconcile)

    def reconcile():
        # create a PMR and call the library's functions
        pmr = classes.ProfilesManagementRepresentation()

        for profile_name in ["ml-engineers"]:
            # create the contributors of the Profile
            contributors = []
            for user, role in [("kimonas@canonical.com", classes.ContributorRole.EDIT)]:
                contributors.append(classes.Contributor(
                    name=user,
                    role=self.pmr_role_from_oidc_role(role)
                ))

            # resource quota
            quota = classes.ResourceQuotaSpecModel.model_validate({"hard": {"limits.cpu": "1"}})

            # owner
            owner = classes.Owner(name="admin@canonical.com"
                                  kind=classes.UserKind.USER)
            # create the Profile
            profile = classes.Profile(
                name=group_name,
                resources=quota,
                contributors=ontributors,
                owner=owner
            )

            # add Profile to PMR
            pmr.add_profile(profile)


        create_or_update_profiles(pmr)
```
