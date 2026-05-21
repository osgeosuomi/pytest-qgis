# pytest-qgis

[![PyPI version](https://badge.fury.io/py/pytest-qgis.svg)](https://badge.fury.io/py/pytest-qgis)
[![Downloads](https://img.shields.io/pypi/dm/pytest-qgis.svg)](https://pypistats.org/packages/pytest-qgis)
![CI](https://github.com/osgeosuomi/pytest-qgis/workflows/CI/badge.svg)
[![Code on Github](https://img.shields.io/badge/Code-GitHub-brightgreen)](https://github.com/osgeosuomi/pytest-qgis)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![codecov.io](https://codecov.io/github/osgeosuomi/pytest-qgis/coverage.svg?branch=main)](https://codecov.io/github/osgeosuomi/pytest-qgis?branch=main)

A [pytest](https://docs.pytest.org) plugin for testing QGIS python plugins.

## Features

This plugin makes it easier to write QGIS plugin tests with the help of some fixtures and hooks:

### Fixtures

* `qgis_app` returns and eventually exits fully
  configured [`QgsApplication`](https://qgis.org/pyqgis/master/core/QgsApplication.html). This fixture is called
  automatically on the start of pytest session.
* `qgis_bot` returns a [`QgisBot`](#qgisbot), which holds common utility methods for interacting with QGIS.
* `qgis_canvas` returns [`QgsMapCanvas`](https://qgis.org/pyqgis/master/gui/QgsMapCanvas.html).
* `qgis_parent` returns the QWidget used as parent of the `qgis_canvas`
* `qgis_iface` returns stubbed [`QgsInterface`](https://qgis.org/pyqgis/master/gui/QgisInterface.html). All the methods that are not implemented return a MagickMock that can be used for testing the calls.
* `qgis_new_project` makes sure that all the map layers and configurations are removed. This should be used with tests
  that add stuff to [`QgsProject`](https://qgis.org/pyqgis/master/core/QgsProject.html). Fixture returns the `QgsProject` instance.
* `qgis_processing` initializes the processing framework. This can be used when testing code that
  calls `processing.run(...)`.
* `qgis_version` returns QGIS version number as integer.
* `qgis_world_map_geopackage` returns Path to the world_map.gpkg that ships with QGIS
* `qgis_countries_layer` returns Natural Earth countries layer from world.map.gpkg as QgsVectorLayer
* `qgis_message_log` captures every `QgsMessageLog.logMessage` call during the
  test.  Yields a `MessageLogCapture` whose `.entries`,
  `.infos` / `.warnings` / `.errors`, and `find(text, level=...)` helpers
  make it easy to assert on plugin log output:

  ```python
  from qgis.core import Qgis, QgsMessageLog

  def test_plugin_warns_on_empty_data(qgis_message_log):
      my_plugin.process_empty()
      assert qgis_message_log.find('No data', level=Qgis.Warning) is not None
      assert len(qgis_message_log.errors) == 0
  ```

### Utility helpers

These live under `pytest_qgis.utils` and can be imported directly:

* `run_task(task, *, timeout_ms=30_000)` — run a `QgsTask` subclass
  synchronously for unit tests (no task manager needed).  Returns
  the task's `run()` result:

  ```python
  from pytest_qgis.utils import run_task

  def test_my_task(qgis_app):
      task = MyTask("desc")
      assert run_task(task) is True
      assert task.result_value == 42
  ```

* `wait_signal(signal, *, timeout_ms=1_000, check=None)` — context
  manager that blocks until a PyQt signal fires, optionally filtered
  by a predicate.  Useful for async Qt flows:

  ```python
  from pytest_qgis.utils import wait_signal

  def test_async_task(qgis_app):
      task = SlowTask()
      with wait_signal(task.finished, timeout_ms=500) as w:
          QgsApplication.taskManager().addTask(task)
      assert w.triggered, 'task did not finish within 500 ms'
  ```

* `make_memory_layer(features, *, fields=None, crs='EPSG:4326', name='memory')`
  — one-line memory-layer builder.  Pass a list of WKT strings or
  `(wkt, attrs)` tuples and get back a valid `QgsVectorLayer`.  The
  geometry kind is inferred from the first WKT's prefix and field
  schemas are inferred from the first attribute dict:

  ```python
  from pytest_qgis.utils import make_memory_layer

  layer = make_memory_layer([
      ('POINT(14 55)', {'name': 'harbour', 'depth': 7.5}),
      ('POINT(15 56)', {'name': 'wreck',   'depth': 18.0}),
  ], crs='EPSG:4326')
  assert layer.featureCount() == 2
  ```

### Markers

* `qgis_show_map` lets developer inspect the QGIS map visually during the test and also at the teardown of the test. Full signature of the marker
  is:
  ```python
  @pytest.mark.qgis_show_map(timeout: int = 30, add_basemap: bool = False, zoom_to_common_extent: bool = True, extent: QgsRectangle = None)
  ```
    * `timeout` is the time in seconds until the map is closed. If timeout is zero, the map will be closed in teardown.
    * `add_basemap` when set to True, adds Natural Earth countries layer as the basemap for the map.
    * `zoom_to_common_extent` when set to True, centers the map around all layers in the project.
    * `extent` is alternative to `zoom_to_common_extent` and lets user specify the extent
      as [`QgsRectangle`](https://qgis.org/pyqgis/master/core/QgsRectangle.html)

Check the marker api [documentation](https://docs.pytest.org/en/latest/mark.html)
and [examples](https://docs.pytest.org/en/latest/example/markers.html#marking-whole-classes-or-modules) for the ways
markers can be used.

### Hooks

* `pytest_configure` hook is used to initialize and
  configure [`QgsApplication`](https://qgis.org/pyqgis/master/core/QgsApplication.html). It is also
  used to patch `qgis.utils.iface` with `qgis_iface` automatically.

  > Be careful not to import modules importing `qgis.utils.iface` in the root of conftest, because the `pytest_configure` hook has not yet patched `iface` in that point. See [this issue](https://github.com/osgeosuomi/pytest-qgis/issues/35) for details.

* `pytest_runtest_teardown` hook is used to ensure that all layer fixtures of any scope are cleaned properly without causing segmentation faults. The layer fixtures that are cleaned automatically must have some of the following keywords in their name: "layer", "lyr", "raster", "rast", "tif".


### Utility tools

* `clean_qgis_layer` decorator found in `pytest_qgis.utils` can be used with `QgsMapLayer` fixtures to ensure that they
  are cleaned properly if they are used but not added to the `QgsProject`. This is only needed with layers with other than memory provider.

  This decorator works only with fixtures that **return** QgsMapLayer instances.
  There is no support for fixtures that use yield.

  This decorator is an alternative way of cleaning the layers, since `pytest_runtest_teardown` hook cleans layer fixtures automatically by the keyword.

  ```python
  # conftest.py or start of a test file
  import pytest
  from pytest_qgis.utils import clean_qgis_layer
  from qgis.core import QgsVectorLayer

  @pytest.fixture()
  @clean_qgis_layer
  def geojson() -> QgsVectorLayer:
      return QgsVectorLayer("layer_file.geojson", "some layer")

  # This will be cleaned automatically since it contains the keyword "layer" in its name
  @pytest.fixture()
  def geojson_layer() -> QgsVectorLayer:
      return QgsVectorLayer("layer_file2.geojson", "some layer")
  ```


### Command line options

* `--qgis_disable_gui` can be used to disable graphical user interface in tests. This speeds up the tests that use Qt
  widgets of the plugin.
* `--qgis_disable_init` can be used to prevent QGIS (QgsApplication) from initializing. Mainly used in internal testing.
* `--qgis_disable_exit` can be used to prevent QGIS (QgsApplication) from exiting in teardown. This might be useful if C++ errors occur.

### ini-options

* `qgis_gui_enabled` whether the QUI will be visible or not. Defaults to `True`. Command line
  option `--qgis_disable_gui` will override this.
* `qgis_canvas_width` width of the QGIS canvas in pixels. Defaults to 600.
* `qgis_canvas_height` height of the QGIS canvas in pixels. Defaults to 600.
* `qgis_server` support qgis server only plugin testing. This prevent initializing qgis interface and allow instanciating QgsServer() safely.
* `qgis_disable_exit` whether to disable QGIS (QgsApplication) from exiting in teardown. This might be useful if C++ errors occur.

### Custom QGIS settings

When running tests, a directory named `.qgis-settings` will be created
containings all QGIS default profile as well as QGIS settings.
Most of the time you can ignore this repository, but it may be useful for inspecting created default settings.

You may define custom settings to be loaded at startup: in your
root tests directory, create a file `qgis_settings.ini` containing all your default QGIS3 settings: this file will be used as the default settings for
the QGIS tests session.



## QgisBot

Class to hold common utility methods for interacting with QGIS. Check [test_qgis_bot.py](tests%2Ftest_qgis_bot.py) for usage examples.  Here are some of the methods:

* `create_feature_with_attribute_dialog` method can be used to create a feature with default values using QgsAttributeDialog. This
  ensures that all the default values are honored and for example boolean fields are either true or false, not null.
* `get_qgs_attribute_dialog_widgets_by_name` function can be used to get dictionary of the `QgsAttributeDialog` widgets.
  Check the test [test_qgis_ui.py::test_attribute_dialog_change](./tests/visual/test_qgis_ui.py) for a usage example.

## Requirements

This pytest plugin requires QGIS >= 3.34 to work though versions up until pytest-qgis<=2.1.0 should work with QGIS >= 3.16.

## Installation

Install with `pip`:

```bash
pip install pytest-qgis
```

## Development environment

This project uses [uv](https://docs.astral.sh/uv/getting-started/installation/)
to manage python packages. Make sure to have it installed first.

- Create a venv that is aware of system QGIS libraries: `uv venv --system-site-packages`. Make sure to use same Python executable as QGIS.
    - On Windows, maybe use a tool like [qgis-venv-creator](ttps://github.com/GispoCoding/qgis-venv-creator).

```shell
# Activate the virtual environment
$ source .venv/bin/activate
# Install dependencies
$ uv sync
# Install pre-commit hooks
$ pre-commit install
```

### Updating dependencies

`uv lock --upgrade`

## Contributing

Contributions are very welcome. Get started by reading OSGeo
Suomi [CONTRIBUTING guidelines](https://github.com/osgeosuomi/.github/blob/main/CONTRIBUTING.md).


## License

Distributed under the terms of the `GNU GPL v2.0` license, "pytest-qgis" is free and open source software.
