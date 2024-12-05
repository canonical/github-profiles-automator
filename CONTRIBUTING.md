# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can create an environment for development with `tox`:

```shell
tox devenv -e integration
source venv/bin/activate
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
tox -e static        # static type checking
tox -e unit          # unit tests
tox -e integration   # integration tests
tox                  # runs 'fmt', 'lint', 'static', and 'unit' environments
```

## Integration Tests

When running/developing integration tests there will be times that the tests will fail. During teardown
of the integration tests the following things happen:
1. The juju model that the Profiles Controller charm was deployed gets deleted
2. The Profile CRs created during tests will still be there

Deleting then a Profile will result in the Profile to never be deleted. This is because:
1. The created Profile has a finalizer
2. The Profile Controller that should be responsible for removing the finaliser is not deployed
3. K8s waits indefinitely until the finaliser is removed, to remove the Profile object

While developing tests locally there are two approaches to go about this

#### Have Profiles Controller always deployed

In this case you'll need to ensure the Profiles controller is always running. This could be achieved by:
1. installing the `kubeflow-profiles` charm in a separate model
2. commenting out the `await deploy_profiles_controller` command

The above will be the fastest way to run the integration tests a lot of times, as you both save time
from re-deploying the Profiles Controller as well as the Profiles can now be deleted as expected with
`kubectl`.

You can install the Profiles Controller with the following command:
```bash
juju deploy kubeflow-profiles --channel 1.9/stable --trust
```

#### Remove finaliser from Profile

If you don't want to mess with your cluster and just get the Profile deleted, then you can
remove the `metadata.finalizers` field in the Profile and K8s will remove the Profile, and garbage
collect the created namespace.

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

## Python versions

Python 3.12 is required for locally running the unit tests and interact with the poetry groups.
If your system is using a different version of Python by default, you can do the following:
```bash
# install Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv -y

# Create venv with 3.12 and install tox. This is needed because tox will use the python
# version of the Virtual Environment to create the final environment when we do "tox -e ..."
python3.12 -m venv venv
source dev-venv/bin/activate
pip install tox
```

## Common Module

The charm also hosts the `profile_management` package which aims to be abstracted to its own PyPi module in the
future. The code for this should be able to be tested (unit/integration) in separate from the rest of the charm.

For this reason we have developed dedicated poetry groups, and tox environments:
```bash
# unit tests
tox -e unit-library
```
