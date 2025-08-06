# Unreleased

## Maintenance tasks

* [#71](https://github.com/osgeosuomi/pytest-qgis/pull/71) Add Qt6 and QGIS>=4 support for the plugin

# Version 2.1.0 (14-06-2024)

## New Features

* Add `clean_qgis_layer` decorator back alongside with automatic cleaning [#64](https://github.com/GispoCoding/pytest-qgis/pull/64)

## Fixes

* [#53](https://github.com/GispoCoding/pytest-qgis/pull/53) Allow using MagicMocks to mock layers without problems
* [#60](https://github.com/GispoCoding/pytest-qgis/pull/60) Allows using CRS properly again
* [#62](https://github.com/GispoCoding/pytest-qgis/pull/62) Map does no longer zoom to the first added layer upon processing the events when using `qgis_show_map` marker

# Version 2.0.0 (29-11-2023)

## New Features

* [#45](https://github.com/GispoCoding/pytest-qgis/pull/45) Clean map layers automatically.
* [#48](https://github.com/GispoCoding/pytest-qgis/pull/48) Add possibility to raise errors if there are warnings or errors in attribute form when adding feature.

## Fixes

* [#45](https://github.com/GispoCoding/pytest-qgis/pull/45) Ensure that the projection is set when replacing layers with projected ones.

## Maintenance tasks

* [#51](https://github.com/GispoCoding/pytest-qgis/pull/51) Change linting to use Ruff.
* [#50](https://github.com/GispoCoding/pytest-qgis/pull/50) Migrate to pyproject.toml and upgrade development dependencies.

## API Breaks

* [#47](https://github.com/GispoCoding/pytest-qgis/pull/48) Remove deprecated functionality:
  * `new_project()` fixture
  * `module_qgis_bot()` fixture
  * `clean_qgis_layer()` function
* [#46](https://github.com/GispoCoding/pytest-qgis/pull/46) Use session scope in qgis_bot fixture
* [#48](https://github.com/GispoCoding/pytest-qgis/pull/48) The `create_feature_with_attribute_dialog()` function now, by default, raises a ValueError when a created feature violates enforced attribute constraints.

# Version 1.3.5 (30-06-2023)
* [#34](https://github.com/GispoCoding/pytest-qgis/pull/34) Use tempfile instead of protected TempPathFactory in QGIS config path creation
* [#39](https://github.com/GispoCoding/pytest-qgis/pull/39) Improve code style and CI
* [#40](https://github.com/GispoCoding/pytest-qgis/pull/40) Improve showing map
* [#42](https://github.com/GispoCoding/pytest-qgis/pull/42) Suppress errors when deleting temp dir

# Version: 1.3.4 (31-05-2023)

* [#34](https://github.com/GispoCoding/pytest-qgis/pull/34): Use tempfile instead of protected TempPathFactory in QGIS config path creation

# Version: 1.3.3 (31-05-2023)

* [#29](https://github.com/GispoCoding/pytest-qgis/pull/29): Release map canvas properly

# Version: 1.3.2 (26-06-2022)

* [#23](https://github.com/GispoCoding/pytest-qgis/pull/23): Support QToolBar as an arg in iface.addToolBar

# Version: 1.3.1 (17-03-2022)

* [#21](https://github.com/GispoCoding/pytest-qgis/pull/21): Add a newProjectCreated signal to QgisInterface mock class


# Version: 1.3.0 (18-01-2022)

* [#17](https://github.com/GispoCoding/pytest-qgis/pull/17): Add QgisBot to make it easier to access utility functions
* [#14](https://github.com/GispoCoding/pytest-qgis/pull/14): Use QMainWindow with parent and store toolbars with iface.addToolBar

# Version: 1.2.0 (17-01-2022)

* [#10](https://github.com/GispoCoding/pytest-qgis/pull/10): Allow showing attribute dialog
* [#9](https://github.com/GispoCoding/pytest-qgis/pull/9): Use QgsLayerTreeMapCanvasBridge to keep the layer order correct


# Version: 1.1.2 (12-16-2021)

* [#8](https://github.com/GispoCoding/pytest-qgis/pull/8): Add stub iface.activeLayer logic

# Version: 1.1.1 (12-07-2021)

* Reduce test time by getting basemap only when needed

# Version: 1.1.0 (11-25-2021)

* [#5](https://github.com/GispoCoding/pytest-qgis/pull/5): Add configurable options
* [#5](https://github.com/GispoCoding/pytest-qgis/pull/5): Add clean_qgis_layer decorator
* [#5](https://github.com/GispoCoding/pytest-qgis/pull/5): Deprecate new_project in favour of qgis_new_project
* [#5](https://github.com/GispoCoding/pytest-qgis/pull/5): Add qgis_show_map marker and functionality

# Version: 1.0.3 (11-22-2021)

* [#4](https://github.com/GispoCoding/pytest-qgis/pull/4): Use hook to patch the imported iface

# Version: 1.0.2 (10-08-2021)

* Check if canvas is deleted before setting layers

# Version: 1.0.1 (10-07-2021)

* Include py.typed

# Version: 1.0.0 (10-07-2021)

* [#1](https://github.com/GispoCoding/pytest-qgis/pull/1) Add processing framework initialization fixture and test
* [#3](https://github.com/GispoCoding/pytest-qgis/pull/3): Add type hints
* [#10](https://github.com/GispoCoding/pytest-qgis/pull/2): Use empty configuration path in tests

# Version: 0.1.0

* Initial plugin
