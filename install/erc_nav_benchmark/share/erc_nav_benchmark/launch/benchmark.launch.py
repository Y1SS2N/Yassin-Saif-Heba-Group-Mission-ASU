"""
============================================================
ERC NAV BENCHMARK - Master Launch File
============================================================
Starts everything with one command:
  ros2 launch erc_nav_benchmark benchmark.launch.py level:=1

Launches:
  1. Gazebo simulation (with chosen level world)
  2. Robot spawner (ERC rover)
  3. Waypoint publisher
  4. Judging engine
  5. Teleop node (optional, disable with teleop:=false)
  6. RViz visualizer (optional, disable with rviz:=false)
============================================================
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    pkg_share = get_package_share_directory('erc_nav_benchmark')

    # ── Declare launch arguments ─────────────────────────────────────────────
    level_arg = DeclareLaunchArgument(
        'level',
        default_value='1',
        description='Difficulty level: 1 (easy) | 2 (medium) | 3 (hard)'
    )

    teleop_arg = DeclareLaunchArgument(
        'teleop',
        default_value='true',
        description='Launch keyboard teleop node (true/false)'
    )

    rviz_arg = DeclareLaunchArgument(
        'rviz',
        default_value='false',
        description='Launch RViz visualizer (true/false)'
    )

    headless_arg = DeclareLaunchArgument(
        'headless',
        default_value='false',
        description='Run Gazebo without GUI (true/false)'
    )

    level    = LaunchConfiguration('level')
    teleop   = LaunchConfiguration('teleop')
    rviz     = LaunchConfiguration('rviz')
    headless = LaunchConfiguration('headless')

    config_path = os.path.join(pkg_share, 'config', 'waypoints.yaml')

    # ── World file path (computed from level arg) ────────────────────────────
    # We build the path in Python since substitutions can't do f-strings easily
    world_1 = os.path.join(pkg_share, 'worlds', 'level_1.world')
    world_2 = os.path.join(pkg_share, 'worlds', 'level_2.world')
    world_3 = os.path.join(pkg_share, 'worlds', 'level_3.world')

    # ── Rover SDF path ───────────────────────────────────────────────────────
    rover_sdf = os.path.join(pkg_share, 'models', 'erc_rover', 'model.sdf')

    # ── Gazebo environment ───────────────────────────────────────────────────
    model_path = os.path.join(pkg_share, 'models')
    env = {
        'GAZEBO_MODEL_PATH': model_path + ':' + os.environ.get('GAZEBO_MODEL_PATH', ''),
    }

    # ── 1. Gazebo (Level 1) ──────────────────────────────────────────────────
    gazebo_l1 = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_1,
             '-s', 'libgazebo_ros_factory.so',
             '-s', 'libgazebo_ros_init.so'],
        output='screen',
        additional_env=env,
        condition=IfCondition(PythonExpression(['"', level, '" == "1"'])),
    )

    # ── 1. Gazebo (Level 2) ──────────────────────────────────────────────────
    gazebo_l2 = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_2,
             '-s', 'libgazebo_ros_factory.so',
             '-s', 'libgazebo_ros_init.so'],
        output='screen',
        additional_env=env,
        condition=IfCondition(PythonExpression(['"', level, '" == "2"'])),
    )

    # ── 1. Gazebo (Level 3) ──────────────────────────────────────────────────
    gazebo_l3 = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_3,
             '-s', 'libgazebo_ros_factory.so',
             '-s', 'libgazebo_ros_init.so'],
        output='screen',
        additional_env=env,
        condition=IfCondition(PythonExpression(['"', level, '" == "3"'])),
    )

    # ── 2. Robot spawner (delayed 3s to let Gazebo start) ────────────────────
    spawn_rover = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='gazebo_ros',
                executable='spawn_entity.py',
                name='spawn_rover',
                arguments=[
                    '-entity', 'erc_rover',
                    '-file', rover_sdf,
                    '-x', '-9.0',
                    '-y', '-9.0',
                    '-z', '0.2',
                    '-Y', '0.785',    # 45 degrees yaw
                ],
                output='screen',
            )
        ]
    )

    # ── 3. Waypoint Publisher (delayed 4s) ───────────────────────────────────
    waypoint_publisher = TimerAction(
        period=4.0,
        actions=[
            Node(
                package='erc_nav_benchmark',
                executable='waypoint_publisher.py',
                name='waypoint_publisher',
                parameters=[
                    {'level': level},
                    {'config_path': config_path},
                ],
                output='screen',
            )
        ]
    )

    # ── 4. Judging Engine (delayed 5s) ───────────────────────────────────────
    judging_engine = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='erc_nav_benchmark',
                executable='judging_engine.py',
                name='judging_engine',
                parameters=[
                    {'level': level},
                    {'config_path': config_path},
                ],
                output='screen',
            )
        ]
    )

    # ── 5. Teleop Node (delayed 6s, optional) ────────────────────────────────
    teleop_node = TimerAction(
        period=6.0,
        actions=[
            Node(
                package='erc_nav_benchmark',
                executable='teleop_node.py',
                name='teleop_node',
                output='screen',
                prefix='xterm -e',   # opens in separate terminal window
                condition=IfCondition(teleop),
            )
        ]
    )

    # ── 6. RViz (optional) ───────────────────────────────────────────────────
    rviz_node = TimerAction(
        period=4.0,
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='log',
                condition=IfCondition(rviz),
            )
        ]
    )

    # ── Startup log ──────────────────────────────────────────────────────────
    start_log = LogInfo(msg=[
        '\n\n'
        '============================================================\n'
        '          ERC NAV BENCHMARK — STARTING                     \n'
        '============================================================\n'
        '  Level    : ', level, '\n'
        '  Teleop   : ', teleop, '\n'
        '  RViz     : ', rviz, '\n'
        '  World    : level_', level, '.world\n'
        '============================================================\n'
        '  Sequence: Gazebo → Spawn → Waypoints → Judge → Teleop\n'
        '============================================================\n'
    ])

    return LaunchDescription([
        level_arg,
        teleop_arg,
        rviz_arg,
        headless_arg,
        start_log,
        gazebo_l1,
        gazebo_l2,
        gazebo_l3,
        spawn_rover,
        waypoint_publisher,
        judging_engine,
        teleop_node,
        rviz_node,
    ])
