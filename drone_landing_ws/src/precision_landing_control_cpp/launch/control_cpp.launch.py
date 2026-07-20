import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    config_dir = os.path.join(get_package_share_directory('precision_landing_control_cpp'), 'config')
    pid_config = os.path.join(config_dir, 'pid.yaml')

    control_node = Node(
        package='precision_landing_control_cpp',
        executable='control_node',
        name='precision_landing_control_node',
        parameters=[pid_config],
        output='screen'
    )

    return LaunchDescription([
        control_node
    ])
