# Why this exists

`spacepilot` on PyPI was claimed with this package, not with the real one.

At the time the real distribution could not publish at all: `pyproject.toml`
still named it `pluto` (taken on PyPI since long before us), the console script
pointed at `src.cli:main` which setuptools did not ship, and the build claimed
sixteen generic top-level import names — `cli`, `engines`, `web_api` — on the
global namespace of every environment it landed in.

So the name was parked with something small and honest instead. It installs,
prints what it is, and claims exactly one import name. That matters: PEP 541
defines squatting as a package that "has no functionality or is empty", and an
empty stub is the thing the policy names. This one does something, however
little.

It is kept here rather than thrown away so that what was published is
reproducible and readable later.

    cd packaging/placeholder
    python -m build
    doppler run -- python -m twine upload dist/*

Superseded by the real package at version 2.8.0. Nothing here should ever be
published again.
