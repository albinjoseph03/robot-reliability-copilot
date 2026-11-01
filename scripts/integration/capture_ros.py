"""Capture real ROS DDS/rosbag2 evidence in an isolated, disposable test domain.

Run with Ubuntu's system Python after sourcing /opt/ros/jazzy/setup.bash.
The Nav2 mode launches the packaged headless TurtleBot3/Gazebo simulation.
All generated recordings and ground-truth manifests stay in --output.
"""

import argparse
import json
import math
import os
import platform
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

DIAGNOSTIC_TOPIC = "/robotcopilot_test/diagnostics"
NAVIGATION_TOPIC = "/navigate_to_pose/_action/status"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


@contextmanager
def process(command, log, env):
    """Own only this subprocess group, including child ROS/Gazebo processes."""
    with log.open("x", encoding="utf-8") as stream:
        child = subprocess.Popen(
            command,
            stdout=stream,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
        )
        write_json(log.with_suffix(".process.json"), {"pid": child.pid, "command": command})
        try:
            yield child
        finally:
            # The launch parent may exit before a Gazebo child; always address our group.
            for sig, timeout in ((signal.SIGINT, 20), (signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                try:
                    os.killpg(child.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    continue
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    break


def wait_for(node, predicate, timeout, description, children=()):
    import rclpy

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for child in children:
            if child.poll() is not None:
                raise RuntimeError(f"Process exited with {child.returncode} while {description}")
        rclpy.spin_once(node, timeout_sec=0.05)
        if predicate():
            return
    raise TimeoutError(f"Timed out after {timeout}s: {description}")


def spin_for(node, seconds):
    import rclpy

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)


def versions():
    from rclpy.utilities import get_rmw_implementation_identifier

    packages = subprocess.run(
        [
            "dpkg-query",
            "-W",
            "-f=${Package}\t${Version}\n",
            "ros-jazzy-rclpy",
            "ros-jazzy-diagnostic-msgs",
            "ros-jazzy-action-msgs",
            "ros-jazzy-rosbag2*",
            "ros-jazzy-nav2*",
            "ros-jazzy-ros-gz*",
            "ros-jazzy-gz-*",
            "gz-sim*",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "ros_distro": os.environ.get("ROS_DISTRO"),
        "rmw_implementation": get_rmw_implementation_identifier(),
        "packages": packages.stdout.splitlines(),
    }


def recording_metadata(folder):
    import yaml

    data = yaml.safe_load((folder / "metadata.yaml").read_text())
    meta = data["rosbag2_bagfile_information"]
    info = subprocess.run(
        ["ros2", "bag", "info", str(folder)], capture_output=True, text=True, check=True
    )
    (folder.parent / f"{folder.name}-bag-info.txt").write_text(info.stdout, encoding="utf-8")
    return {
        "relative_file_paths": meta["relative_file_paths"],
        "message_count": meta["message_count"],
        "topics_with_message_count": meta["topics_with_message_count"],
    }


def record_command(folder, *topics):
    return [
        "ros2",
        "bag",
        "record",
        "-s",
        "mcap",
        "-o",
        str(folder),
        "--disable-keyboard-controls",
        "--include-hidden-topics",
        "--topics",
        *topics,
    ]


@contextmanager
def status_recording(folder):
    """Use the native writer's installed-schema lookup with the equivalent ROS type alias.

    Jazzy rosbag2 0.26.11 incorrectly treats the canonical GoalStatusArray name
    as an unsupported generated action type. The two-part name takes its normal
    MSG lookup path. No payload or installed schema is patched or synthesized.
    """
    import rosbag2_py

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(uri=str(folder), storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    writer.create_topic(
        rosbag2_py.TopicMetadata(
            id=0,
            name=NAVIGATION_TOPIC,
            type="action_msgs/GoalStatusArray",
            serialization_format="cdr",
        )
    )
    try:
        yield writer
    finally:
        writer.close()


def capture_diagnostics(output, env):
    import rclpy
    from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

    rclpy.init()
    node = rclpy.create_node("robotcopilot_diagnostic_fixture")
    publisher = node.create_publisher(DiagnosticArray, DIAGNOSTIC_TOPIC, 10)
    sent = []
    try:
        folder = output / "diagnostics"
        with process(
            record_command(folder, DIAGNOSTIC_TOPIC), output / "recorder.log", env
        ) as recorder:
            wait_for(
                node,
                lambda: publisher.get_subscription_count() > 0,
                30,
                "waiting for rosbag2 diagnostic subscription",
                [recorder],
            )
            spin_for(node, 1)
            for index, level in enumerate((0, 1, 1, 2, 2, 0)):
                message = DiagnosticArray()
                message.header.stamp = node.get_clock().now().to_msg()
                message.status = [
                    DiagnosticStatus(
                        level=bytes([level]),
                        name="integration_motor",
                        hardware_id="synthetic_ros_motor_01",
                        message={
                            0: "nominal",
                            1: "injected warning",
                            2: "injected diagnostic error",
                        }[level],
                        values=[KeyValue(key="fixture_index", value=str(index))],
                    )
                ]
                publisher.publish(message)
                sent.append(
                    {
                        "index": index,
                        "level": level,
                        "header_time_ns": message.header.stamp.sec * 10**9
                        + message.header.stamp.nanosec,
                    }
                )
                spin_for(node, 0.4)
            spin_for(node, 1)
        return {
            "kind": "rosbag2_diagnostics",
            "topic": DIAGNOSTIC_TOPIC,
            "source": "Original synthetic values published through real ROS 2 DDS",
            "sent": sent,
            "bag": "diagnostics",
            "metadata": recording_metadata(folder),
        }
    finally:
        node.destroy_node()
        rclpy.shutdown()


def capture_navigation(output, env):
    import rclpy
    from action_msgs.msg import GoalStatusArray
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav2_msgs.action import NavigateToPose
    from rclpy.action import ActionClient
    from rclpy.parameter import Parameter
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from rclpy.serialization import deserialize_message
    from tf2_ros import Buffer, TransformListener

    rclpy.init()
    node = rclpy.create_node("robotcopilot_nav2_fixture")
    node.set_parameters([Parameter("use_sim_time", value=True)])
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    initial_pose = node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
    client = ActionClient(node, NavigateToPose, "/navigate_to_pose")
    statuses = []
    writer = None

    def collect(payload, message_info):
        message = deserialize_message(payload, GoalStatusArray)
        statuses.extend(
            {"goal_id": bytes(s.goal_info.goal_id.uuid).hex(), "status": s.status}
            for s in message.status_list
        )
        if writer is not None:
            writer.write(
                NAVIGATION_TOPIC,
                payload,
                message_info["received_timestamp"] or time.time_ns(),
                message_info["source_timestamp"],
            )

    status_qos = QoSProfile(
        depth=20,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    subscription = node.create_subscription(
        GoalStatusArray,
        NAVIGATION_TOPIC,
        collect,
        status_qos,
        raw=True,
    )
    goals = []

    def send_goal(label, x, y, behavior_tree="", cancel=False, timeout=90):
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = node.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
        goal.pose.pose.orientation.w = 1.0
        goal.behavior_tree = behavior_tree
        pending = client.send_goal_async(goal)
        wait_for(node, pending.done, 15, "waiting for goal acceptance")
        handle = pending.result()
        entry = {
            "scenario": label,
            "goal_id": bytes(handle.goal_id.uuid).hex(),
            "accepted": handle.accepted,
            "goal": {"x": x, "y": y, "behavior_tree": behavior_tree},
        }
        goals.append(entry)
        write_json(output / f"goal-{label}-sent.json", entry)
        if not handle.accepted:
            raise RuntimeError(f"{label}: rejected goal is not an abort fixture")
        result_future = handle.get_result_async()
        if cancel:
            # Require evidence of execution before issuing cancellation.
            wait_for(
                node,
                lambda: any(
                    s["goal_id"] == entry["goal_id"] and s["status"] == 2 for s in statuses
                ),
                15,
                "waiting for executing goal",
            )
            cancellation = handle.cancel_goal_async()
            wait_for(node, cancellation.done, 15, "waiting for cancel acknowledgement")
            entry["cancel_accepted"] = bool(cancellation.result().goals_canceling)
        wait_for(node, result_future.done, timeout, f"waiting for {label} result")
        result = result_future.result()
        entry.update(
            status=result.status,
            error_code=getattr(result.result, "error_code", None),
            error_msg=getattr(result.result, "error_msg", None),
        )
        write_json(output / f"goal-{label}-result.json", entry)
        spin_for(node, 1)
        return entry

    try:
        launch = [
            "ros2",
            "launch",
            "nav2_bringup",
            "tb3_simulation_launch.py",
            "headless:=True",
            "use_rviz:=False",
            "use_composition:=False",
        ]
        with process(launch, output / "nav2-gazebo.log", env) as simulation:
            wait_for(
                node, client.server_is_ready, 180, "waiting for Nav2 action server", [simulation]
            )
            wait_for(
                node,
                lambda: initial_pose.get_subscription_count() > 0,
                60,
                "waiting for AMCL initialpose subscription",
                [simulation],
            )
            for _ in range(5):
                pose = PoseWithCovarianceStamped()
                pose.header.frame_id = "map"
                pose.header.stamp = node.get_clock().now().to_msg()
                pose.pose.pose.position.x, pose.pose.pose.position.y = -2.0, -0.5
                pose.pose.pose.orientation.w = 1.0
                pose.pose.covariance[0] = pose.pose.covariance[7] = 0.25
                pose.pose.covariance[35] = math.radians(15) ** 2
                initial_pose.publish(pose)
                spin_for(node, 1)
            from rclpy.time import Time

            wait_for(
                node,
                lambda: buffer.can_transform("map", "base_link", Time()),
                90,
                "waiting for localized map/base_link transform",
                [simulation],
            )
            folder = output / "navigation"
            embedded_folder = output / "navigation_embedded"
            spin_for(node, 2)
            baseline_subscribers = node.count_subscribers(NAVIGATION_TOPIC)
            with (
                status_recording(embedded_folder) as writer,
                process(
                    record_command(folder, NAVIGATION_TOPIC), output / "recorder.log", env
                ) as recorder,
            ):
                wait_for(
                    node,
                    lambda: node.count_subscribers(NAVIGATION_TOPIC) > baseline_subscribers,
                    30,
                    "waiting for status recorder and fixture subscriptions",
                    [recorder],
                )
                spin_for(node, 2)
                transform = buffer.lookup_transform("map", "base_link", Time())
                x, y = transform.transform.translation.x, transform.transform.translation.y
                success = send_goal("success", x, y)
                if success["status"] != 4:
                    raise RuntimeError(f"Success control did not succeed: {success}")
                # Failure injection is software configuration, not a physical failure label.
                missing = str((output / "intentionally-missing-bt.xml").resolve())
                failure = send_goal("missing_behavior_tree", x, y, missing)
                if failure["status"] != 6:
                    raise RuntimeError(f"Missing BT did not yield ABORTED: {failure}")
                cancellation = send_goal("cancellation", x + 1.0, y, cancel=True)
                if cancellation["status"] != 5 or not cancellation["cancel_accepted"]:
                    raise RuntimeError(f"Cancellation control did not cancel: {cancellation}")
                spin_for(node, 2)
            writer = None
            write_json(output / "observed-statuses.json", statuses)
            return {
                "kind": "nav2_gazebo",
                "topic": NAVIGATION_TOPIC,
                "bag": "navigation_embedded",
                "source": "Original controlled goals in packaged headless Nav2/Gazebo simulation",
                "launch_command": launch,
                "goals": goals,
                "metadata": recording_metadata(embedded_folder),
                "raw_cli_metadata": recording_metadata(folder),
                "schema_workaround": (
                    "Native rosbag2_py writer uses equivalent action_msgs/GoalStatusArray alias "
                    "to embed installed definitions; unmodified CLI recording "
                    "retained in navigation/."
                ),
            }
    finally:
        # Keep listener/subscription alive until capture completes.
        del listener, subscription
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["diagnostics", "navigation"])
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--domain-id", type=int, default=73)
    args = parser.parse_args()
    if os.environ.get("ROS_DISTRO") != "jazzy":
        raise SystemExit("Source /opt/ros/jazzy/setup.bash first.")
    if not 0 <= args.domain_id <= 200:
        raise SystemExit("Use a test domain ID between 0 and 200.")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.update(
        ROS_DOMAIN_ID=str(args.domain_id),
        ROS_AUTOMATIC_DISCOVERY_RANGE="LOCALHOST",
        GZ_PARTITION=f"robotcopilot-{args.domain_id}-{os.getpid()}",
        ROS_LOG_DIR=str(args.output / "ros-logs"),
    )
    env = dict(os.environ)
    environment = versions()
    write_json(args.output / "environment.json", environment)
    scenario = capture_diagnostics if args.scenario == "diagnostics" else capture_navigation
    manifest = scenario(args.output, env)
    manifest["environment"] = environment
    manifest["domain_id"] = args.domain_id
    write_json(args.output / "ground-truth.json", manifest)
    print(f"Captured {args.scenario}: {args.output}")


if __name__ == "__main__":
    main()
