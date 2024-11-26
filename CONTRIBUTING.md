# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can create an environment for development with `tox`:

```shell
tox devenv -e integration
source venv/bin/activate
```

## Common Module

The charm also hosts the `profile_management` package which aims to be abstracted to its own PyPi module in the
future. The code for this should be able to be tested (unit/integration) in separate from the rest of the charm.

For this reason we have developed the following poetry and tox environments:
```bash
# unit tests
poetry install --with unit-library --no-root
tox -e unit-library
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox run -e format        # update your code according to linting rules
tox run -e lint          # code style
tox run -e static        # static type checking
tox run -e unit          # unit tests
tox run -e integration   # integration tests
tox                      # runs 'format', 'lint', 'static', and 'unit' environments
```

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

## Python versions

The charm requires Python 3.12 to run/pack. If your system is using a different version of Python
by default, you can do the following:
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
<!-- You may want to include any contribution/style guidelines in this document>
