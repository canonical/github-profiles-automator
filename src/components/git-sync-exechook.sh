#!/bin/sh
# This script will be called by `git-sync` whenever it receives new information
# from the repository.
# See https://github.com/kubernetes/git-sync/blob/69eb59185a073d4a08362d07bbe6459311027746/_test_tools/exechook_command_with_sleep.sh
/charm/bin/pebble notify github-profiles-automator.com/sync
