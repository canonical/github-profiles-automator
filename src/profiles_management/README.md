# Profiles Management Library

This module aims to be a standalone python module focused around:
1. Exposing the ProfileManagementRepresentation (PMR) classes
2. Functions that manipulate the cluster, based on a PMR

## Consume from Charms

This library is meant to be used by other Charms that will construct
a PMR and run the functions of this module to update the cluster's state.

Here's is some psudo-code that can show how a potential charm could
interact with the code of this library:
```python
from profiles_management.pmr import classes
from profiles_management import create_or_update_profiles


class TestCharm(ops.CharmBase):

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.framework.observe(self.on.install, self.reconcile)

    def reconcile():
        # create a PMR and call the library's functions
        pmr = classes.ProfilesManagementRepresentation()

        for group_name in self.read_groups_identity_provider():
            # create the contributors of the Profile
            contributors = []
            for user, role in self.read_users_from_group(group_name):
                contributors.append(classes.Contributor(
                    name=user,
                    role=self.pmr_role_from_oidc_role(role)
                ))

            # resource quota
            quota = self.read_resource_quota_from_group_metadata(group_name)

            # owner
            owner = classes.Owner(name="admin@example.com"
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
