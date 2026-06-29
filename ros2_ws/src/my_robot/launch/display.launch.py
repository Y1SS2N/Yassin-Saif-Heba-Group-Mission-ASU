import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, TimerAction

urdf_file = os.path.expanduser('~/ros2_ws/src/my_robot/urdf/my_robot.urdf')
world_file = os.path.expanduser('~/ros2_ws/src/my_robot/worlds/aruco_world.world')
with open(urdf_file, 'r') as f:
    robot_description = f.read()

def generate_launch_description():
    return LaunchDescription([

        # Robot State Publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}]
        ),

        # Joint State Publisher
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            parameters=[{'robot_description': robot_description}]
        ),

        # Gazebo with custom world
        ExecuteProcess(
            cmd=['ros2', 'launch', 'gazebo_ros', 'gazebo.launch.py', f'world:={world_file}'],
            output='screen'
        ),

        # Spawn robot after 5 seconds facing the front poles
        TimerAction(
            period=5.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        'ros2', 'run', 'gazebo_ros', 'spawn_entity.py',
                        '-file', os.path.expanduser('~/ros2_ws/src/my_robot/urdf/my_robot.urdf'),
                        '-entity', 'my_robot',
                        '-x', '0', '-y', '0', '-z', '0.1',
                        '-R', '0', '-P', '0', '-Y', '0'
                    ],
                    output='screen'
                )
            ]
        ),

    ])
