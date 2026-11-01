#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/python3 "$script_dir/capture_ros.py" "$@"
