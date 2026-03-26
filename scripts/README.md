# Scripts

This directory contains thin orchestration wrappers.

Rules:

- keep scripts small and explicit
- prefer app-native tooling inside each app
- use scripts to preserve a clean root developer interface
- do not bury product logic in shell scripts

`scripts/api/` is the bridge between the root command contract and the Python API project.
`scripts/infra/` owns local infrastructure lifecycle wrappers.
