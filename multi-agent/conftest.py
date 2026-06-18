"""
Root conftest.py — fixes Python import path conflicts for the test suite.

Problem 1 — 'mas' resolves to production install
-------------------------------------------------
``pip install -e .`` registers a meta_path finder that resolves ``import mas``
to the production path (the original checkout without GENIE-1336 additions).
That production path lacks ``mas.blueprints.models.blueprint_version`` and
other GENIE-1336 modules, causing collection errors.

Fix: insert ``lib/`` at ``sys.path[0]``.  Python's standard ``PathFinder``
resolves ``import mas`` to local ``lib/mas/`` first, before the editable-install
finder, so all GENIE-1336 additions are visible to every importer.

Problem 2 — 'outbound' resolves to production install path (missing GENIE-1336)
---------------------------------------------------------------------------------
``bootstrap/container.py`` uses ``from outbound.mongo.* import ...``
(production style — verified by ``test_adapters_import_regression.py``).
In the test environment the editable install resolves ``outbound`` to the
production adapters path which lacks ``blueprint_version_repository.py``
(a GENIE-1336 addition).

Additionally, ``test_container_blueprint_wiring.py::test_ensure_indexes_called_during_build``
patches ``adapters.outbound.mongo.blueprint_version_repository``
``.MongoBlueprintVersionRepository.ensure_indexes``.  For that patch to land on
the class object that ``AppContainer._build()`` instantiates, both import paths
must resolve to the **same** module object.

Fix: pre-import the local ``adapters.outbound.*`` modules (which include the
GENIE-1336 files) and register them under the ``outbound.*`` keys in
``sys.modules``.  After this, ``from outbound.mongo.blueprint_version_repository
import MongoBlueprintVersionRepository`` returns the same class that is already
cached under ``adapters.outbound.mongo.blueprint_version_repository``, so
unittest.mock patches on either path hit the same class.

The regression test (``tests/regression/test_adapters_import_regression.py``)
runs the import check in a **subprocess** with its own ``PYTHONPATH``, so these
``sys.modules`` aliases are invisible to it.
"""

import os
import sys

# ── Fix 1: local lib/mas/ takes precedence over the editable-install's mas/ ──

_lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

# ── Fix 2: alias outbound.* → adapters.outbound.* in sys.modules ─────────────
#
# This is done at conftest load-time (before any test collection) so that every
# subsequent ``import outbound.*`` — including the one triggered when pytest
# first imports bootstrap.container — finds the local, GENIE-1336-aware modules.

try:
    import adapters.outbound  # noqa: E402
    import adapters.outbound.mongo  # noqa: E402
    import adapters.outbound.mongo.blueprint_repository  # noqa: E402
    import adapters.outbound.mongo.blueprint_version_repository  # noqa: E402

    sys.modules["outbound"] = sys.modules["adapters.outbound"]
    sys.modules["outbound.mongo"] = sys.modules["adapters.outbound.mongo"]
    sys.modules["outbound.mongo.blueprint_repository"] = sys.modules[
        "adapters.outbound.mongo.blueprint_repository"
    ]
    sys.modules["outbound.mongo.blueprint_version_repository"] = sys.modules[
        "adapters.outbound.mongo.blueprint_version_repository"
    ]
except ImportError:
    # Defensive: if adapters.outbound is not importable in some minimal
    # environment, skip the aliasing gracefully.  The container-wiring tests
    # will surface the underlying error themselves.
    pass
