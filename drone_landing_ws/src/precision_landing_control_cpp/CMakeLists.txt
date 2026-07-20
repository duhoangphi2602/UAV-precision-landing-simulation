cmake_minimum_required(VERSION 3.8)
project(precision_landing_control_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

# Include directories
include_directories(include)

# PID Library
add_library(pid_controller src/pid_controller.cpp)
target_include_directories(pid_controller PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)

# Control Node
add_executable(control_node src/control_node.cpp)
target_link_libraries(control_node pid_controller)
ament_target_dependencies(control_node rclcpp geometry_msgs std_msgs)

# Install
install(TARGETS
  pid_controller
  control_node
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

# Tests
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
  
  find_package(ament_cmake_gtest REQUIRED)
  
  ament_add_gtest(test_pid_controller test/test_pid_controller.cpp)
  target_link_libraries(test_pid_controller pid_controller)
endif()

ament_package()
