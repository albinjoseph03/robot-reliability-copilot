"""Explicit root-only bootstrap for the Ubuntu 24.04 integration environment.

Configures the official signed ROS APT source and installs ROS/Nav2/Gazebo.
Not imported or run by the analyzer, tests, or normal package installation.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

BASE_PACKAGES = [
    "ros-jazzy-ros-base",
    "ros-jazzy-rosbag2-storage-mcap",
]
SIMULATION_PACKAGES = [
    "ros-jazzy-navigation2",
    "ros-jazzy-nav2-bringup",
    "ros-jazzy-nav2-minimal-tb3-sim",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install after printing APT plan")
    parser.add_argument("--profile", choices=["diagnostics", "navigation"], default="navigation")
    args = parser.parse_args()
    packages = BASE_PACKAGES + (SIMULATION_PACKAGES if args.profile == "navigation" else [])
    if os.geteuid() != 0:
        raise SystemExit("Run explicitly as root in the intended Ubuntu integration environment.")
    if "VERSION_CODENAME=noble" not in Path("/etc/os-release").read_text():
        raise SystemExit("This bootstrap requires Ubuntu 24.04 (noble).")
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    if subprocess.run(["dpkg-query", "-W", "ros2-apt-source"], capture_output=True).returncode:
        request = urllib.request.Request(
            "https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest",
            headers={"User-Agent": "robotcopilot-integration"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            release = json.load(response)
        asset = next(
            a
            for a in release["assets"]
            if a["name"].endswith(".noble_all.deb") and a["name"].startswith("ros2-apt-source_")
        )
        digest = asset.get("digest", "")
        if not digest.startswith("sha256:"):
            raise SystemExit(
                "Release asset has no SHA-256 digest; inspect upstream before continuing."
            )
        print(f"Official ROS APT source: {release['tag_name']} / {asset['name']}", flush=True)
        with tempfile.TemporaryDirectory(prefix="robotcopilot-ros-apt-") as folder:
            deb = Path(folder) / asset["name"]
            with urllib.request.urlopen(asset["browser_download_url"], timeout=120) as response:
                deb.write_bytes(response.read())
            if hashlib.sha256(deb.read_bytes()).hexdigest() != digest.removeprefix("sha256:"):
                raise SystemExit("ROS APT source asset digest mismatch.")
            subprocess.run(["dpkg", "-i", str(deb)], env=env, check=True)
    subprocess.run(["apt-get", "update"], env=env, check=True)
    subprocess.run(
        ["apt-get", "--simulate", "install", "--no-install-recommends", *packages],
        env=env,
        check=True,
    )
    if args.install:
        subprocess.run(
            ["apt-get", "install", "-y", "--no-install-recommends", *packages], env=env, check=True
        )
    else:
        print("APT source configured; package plan only. Use --install to install ROS packages.")


if __name__ == "__main__":
    main()
