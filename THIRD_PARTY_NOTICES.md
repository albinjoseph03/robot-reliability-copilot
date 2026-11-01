# Dependency and fixture notices

Review date: 2026-10-31. Project code is Apache-2.0. Runtime dependencies are
installed separately, not vendored. Their licenses remain applicable and must
be retained when redistributing dependencies, wheels, containers or bundles.
This inventory is based on the installed versions' metadata/license files and
the upstream ROS/MCAP sources; it is not a license for external recordings.

## Runtime dependency inventory

| Packages (tested versions) | Declared/reviewed license |
| --- | --- |
| mcap 1.6.0; mcap-ros2-support 0.6.0 | MIT; [upstream license](https://github.com/foxglove/mcap/blob/main/LICENSE) |
| pydantic 2.14.2; pydantic-core 2.50.2; annotated-types 0.8.0; typing-inspection 0.4.4 | MIT |
| typer 0.27.3; annotated-doc 0.0.5 | MIT; Typer also contains Click's BSD-3-Clause notice |
| shellingham 1.5.4 | ISC |
| colorama 0.4.6 (Windows) | BSD-3-Clause |
| rich 15.0.0; markdown-it-py 4.2.0; mdurl 0.1.2 | MIT; preserve markdown-it's upstream notice too |
| Pygments 2.21.0 | BSD-2-Clause |
| typing-extensions 4.16.0 | PSF-2.0 |
| lz4 4.4.5; zstandard 0.25.0 | BSD-3-Clause Python bindings; bundled native library notices also apply |

The lz4 binding identifies copyright (c) 2012–2013 Steeve Morin; the
zstandard binding identifies copyright (c) 2016 Gregory Szorc. Native
compression distributions can include additional BSD/GPL dual-license and
bundled-code notices: preserve the upstream wheel/sdist license materials and
review them again before a bundled binary release. MCAP Python wheels in this
environment declare MIT but omit a license file; use the upstream license when
bundling them.

Development tools: pytest, Ruff, build, iniconfig, pluggy and pyproject-hooks
declare MIT; packaging declares Apache-2.0 OR BSD-2-Clause. The build backend
Hatchling and its dependencies must retain their own notices if redistributed.
Inspect the resolved `uv.lock` when changing dependencies; this table describes
the reviewed environment, not all future resolutions.

## Embedded ROS message layouts

`src/robotcopilot/sample.py` includes standard field layouts from:

- [ros2/common_interfaces](https://github.com/ros2/common_interfaces/tree/jazzy):
  DiagnosticArray, DiagnosticStatus, KeyValue, Header (Apache-2.0).
- [ros2/rcl_interfaces](https://github.com/ros2/rcl_interfaces/tree/jazzy):
  Time, GoalStatusArray, GoalStatus, GoalInfo (Apache-2.0).
- [ros2/unique_identifier_msgs](https://github.com/ros2/unique_identifier_msgs):
  UUID (BSD-3-Clause; [retained upstream notice](licenses/UUID-BSD-3-Clause.txt),
  copyright (C) 2012 Jack O'Quin).

These layouts were transcribed into combined MCAP schema strings; comments
were removed, dependencies qualified, and the action-status constants omitted
from the fixture schema. The wire fields are preserved. ROS interface authors
and contributors retain their rights. See the upstream package.xml licenses
and [rcl_interfaces license](https://github.com/ros2/rcl_interfaces/blob/jazzy/LICENSE).
The Apache-2.0 terms are included in this repository's LICENSE. UUID retains
its upstream BSD-3-Clause terms; it is not relicensed by the project.

Diagnostic values, component names, goal IDs, timestamps and scenario labels
are original synthetic project fixtures, distributed under Apache-2.0. Tests
generate them locally. No real-world data, labeled external failure dataset,
robot map or Gazebo model is included. Future external data needs provenance,
explicit redistribution permission, privacy review and a retained license
before inclusion; a public download link alone is not permission.
