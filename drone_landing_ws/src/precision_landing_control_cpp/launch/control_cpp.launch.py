# Copyright 2026 User
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config_dir = os.path.join(
        get_package_share_directory('precision_landing_control_cpp'),
        'config',
    )
    pid_config = os.path.join(config_dir, 'pid.yaml')

    interface_mode_arg = DeclareLaunchArgument(
        'interface_mode',
        default_value='legacy',
        description='Interface mode: typed or legacy'
    )

    mission_mode_arg = DeclareLaunchArgument(
        'mission_mode',
        default_value='fixed',
        description='Mission mode: fixed or moving'
    )

    pid_moving_config = os.path.join(config_dir, 'pid_moving.yaml')

    def launch_setup(context, *args, **kwargs):
        mission_mode = LaunchConfiguration('mission_mode').perform(context)
        selected_pid_config = (
            pid_moving_config if mission_mode == 'moving' else pid_config
        )

        control_node = Node(
            package='precision_landing_control_cpp',
            executable='control_node',
            name='precision_landing_control_node',
            parameters=[
                selected_pid_config,
                {'interface_mode': LaunchConfiguration('interface_mode')},
            ],
            output='screen'
        )
        return [control_node]

    return LaunchDescription([
        interface_mode_arg,
        mission_mode_arg,
        OpaqueFunction(function=launch_setup)
    ])
