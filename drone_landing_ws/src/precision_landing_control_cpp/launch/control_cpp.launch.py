import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    config_dir = os.path.join(get_package_share_directory('precision_landing_control_cpp'), 'config')
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

    import launch.conditions
    pid_moving_config = os.path.join(config_dir, 'pid_moving.yaml')

    # We will just pass the params using Python substitution, but LaunchConfiguration doesn't directly do conditionals for parameter files well.
    # We can just define the node using a OpaqueFunction or simpler:

    def launch_setup(context, *args, **kwargs):
        mission_mode = LaunchConfiguration('mission_mode').perform(context)
        selected_pid_config = pid_moving_config if mission_mode == 'moving' else pid_config

        control_node = Node(
            package='precision_landing_control_cpp',
            executable='control_node',
            name='precision_landing_control_node',
            parameters=[selected_pid_config, {'interface_mode': LaunchConfiguration('interface_mode')}],
            output='screen'
        )
        return [control_node]

    return LaunchDescription([
        interface_mode_arg,
        mission_mode_arg,
        launch.actions.OpaqueFunction(function=launch_setup)
    ])
