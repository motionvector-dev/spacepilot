#!/usr/bin/env bash
# Point git at the hooks this repo ships.
#
# Hooks live in .githooks/ so they are versioned and reviewed like everything
# else; .git/hooks is per-clone and invisible to a diff. core.hooksPath is
# stored in the shared config, so one run covers every worktree of this repo.
#
#     tools/install_hooks.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "core.hooksPath = .githooks"
ls -1 .githooks | sed 's/^/  /'
