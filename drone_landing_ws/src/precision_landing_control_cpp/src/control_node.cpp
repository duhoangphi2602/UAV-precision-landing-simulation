#include <chrono>
#include <memory>
#include <string>
#include <cmath>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
#include "precision_landing_interfaces/msg/target_observation.hpp"
#include "precision_landing_interfaces/msg/control_command.hpp"
#include "precision_landing_control_cpp/pid_controller.hpp"

using namespace std::chrono_literals;
using std::placeholders::_1;

namespace precision_landing_control_cpp
{

class ControlNode : public rclcpp::Node
{
public:
    ControlNode() : Node("control_node")
    {
        // Declare parameters
        this->declare_parameter("kp_x", 0.005);
        this->declare_parameter("ki_x", 0.0001);
        this->declare_parameter("kd_x", 0.001);

        this->declare_parameter("kp_y", 0.005);
        this->declare_parameter("ki_y", 0.0001);
        this->declare_parameter("kd_y", 0.001);

        this->declare_parameter("deadband", 5.0);
        this->declare_parameter("output_min", -1.0);
        this->declare_parameter("output_max", 1.0);
        this->declare_parameter("integral_min", -0.2);
        this->declare_parameter("integral_max", 0.2);
        this->declare_parameter("stale_timeout", 1.0); // seconds
        this->declare_parameter("swap_axes", false);
        this->declare_parameter("flip_x", false);
        this->declare_parameter("flip_y", false);
        this->declare_parameter("interface_mode", "typed");

        PIDConfig config_x, config_y;
        config_x.kp = this->get_parameter("kp_x").as_double();
        config_x.ki = this->get_parameter("ki_x").as_double();
        config_x.kd = this->get_parameter("kd_x").as_double();
        config_x.deadband = this->get_parameter("deadband").as_double();
        config_x.output_min = this->get_parameter("output_min").as_double();
        config_x.output_max = this->get_parameter("output_max").as_double();
        config_x.integral_min = this->get_parameter("integral_min").as_double();
        config_x.integral_max = this->get_parameter("integral_max").as_double();
        config_x.stale_timeout = this->get_parameter("stale_timeout").as_double();

        config_y = config_x;
        config_y.kp = this->get_parameter("kp_y").as_double();
        config_y.ki = this->get_parameter("ki_y").as_double();
        config_y.kd = this->get_parameter("kd_y").as_double();

        pid_x_ = std::make_shared<PIDController>(config_x);
        pid_y_ = std::make_shared<PIDController>(config_y);
        stale_timeout_ = config_x.stale_timeout;

        std::string interface_mode = this->get_parameter("interface_mode").as_string();
        if (interface_mode == "legacy") {
            error_sub_ = this->create_subscription<geometry_msgs::msg::Point>(
                "/aruco/center_error", 10, std::bind(&ControlNode::error_callback, this, _1));
        } else {
            obs_sub_ = this->create_subscription<precision_landing_interfaces::msg::TargetObservation>(
                "/precision_landing/target_observation", 10, std::bind(&ControlNode::obs_callback, this, _1));
        }

        cmd_pub_ = this->create_publisher<geometry_msgs::msg::Twist>("/precision_landing/cmd_vel", 10);
        ctrl_pub_ = this->create_publisher<precision_landing_interfaces::msg::ControlCommand>("/precision_landing/control_command", 10);
        debug_pub_ = this->create_publisher<std_msgs::msg::String>("/precision_landing/control_debug", 10);

        timer_ = this->create_wall_timer(
            50ms, std::bind(&ControlNode::timer_callback, this)); // 20Hz control loop

        last_obs_time_ = this->now();

        RCLCPP_INFO(this->get_logger(), "Precision Landing C++ Control Node Started.");
    }

private:
    void calculate_pid(double error_x, double error_y, double dt)
    {
        if (dt < 0.001) dt = 0.001;
        if (dt > 1.0) dt = 1.0;

        bool swap_axes = this->get_parameter("swap_axes").as_bool();
        bool flip_x = this->get_parameter("flip_x").as_bool();
        bool flip_y = this->get_parameter("flip_y").as_bool();

        double vx = 0.0, vy = 0.0;
        if (swap_axes) {
            vx = pid_x_->compute(error_x, dt);
            vy = pid_y_->compute(error_y, dt);
        } else {
            vy = pid_x_->compute(error_x, dt);
            vx = -pid_y_->compute(error_y, dt);
        }
        if (flip_x) vx = -vx;
        if (flip_y) vy = -vy;

        last_vx_ = vx;
        last_vy_ = vy;
    }

    void error_callback(const geometry_msgs::msg::Point::SharedPtr msg)
    {
        auto now = this->now();
        if (is_first_processed_) {
            is_first_processed_ = false;
            last_processed_stamp_ = now;
        } else {
            double dt = (now - last_processed_stamp_).seconds();
            last_processed_stamp_ = now;
            calculate_pid(msg->x, msg->y, dt);
        }
        last_obs_time_ = now;
        has_first_obs_ = true;
        valid_obs_ = true;
    }

    void obs_callback(const precision_landing_interfaces::msg::TargetObservation::SharedPtr msg)
    {
        auto now = this->now();
        rclcpp::Time stamp(msg->header.stamp);

        if (!msg->valid || !std::isfinite(msg->error_x) || !std::isfinite(msg->error_y)) {
            if (!std::isfinite(msg->error_x) || !std::isfinite(msg->error_y)) {
                valid_obs_ = false;
            }
            return; // Do not update PID
        }

        if (msg->sequence_id != last_processed_sequence_id_) {
            if (is_first_processed_) {
                is_first_processed_ = false;
                last_processed_stamp_ = stamp;
            } else {
                double dt = (stamp - last_processed_stamp_).seconds();
                last_processed_stamp_ = stamp;
                calculate_pid(msg->error_x, msg->error_y, dt);
            }
            last_processed_sequence_id_ = msg->sequence_id;
        }

        last_obs_time_ = now;
        has_first_obs_ = true;
        valid_obs_ = true;
    }

    void timer_callback()
    {
        auto now = this->now();
        geometry_msgs::msg::Twist cmd_msg;
        precision_landing_interfaces::msg::ControlCommand ctrl_msg;
        std_msgs::msg::String debug_msg;

        ctrl_msg.header.stamp = now;
        ctrl_msg.controller = "CPP PID";

        // Check for stale timeout
        if (!has_first_obs_ || !valid_obs_ || (now - last_obs_time_).seconds() > stale_timeout_) {
            pid_x_->reset();
            pid_y_->reset();
            cmd_msg.linear.x = 0.0;
            cmd_msg.linear.y = 0.0;
            cmd_msg.linear.z = 0.0;

            ctrl_msg.valid = false;
            ctrl_msg.stale = true;
            ctrl_msg.saturated = false;
            ctrl_msg.command = cmd_msg;

            debug_msg.data = "STALE_OBSERVATION";
            is_first_processed_ = true;
            last_vx_ = 0.0;
            last_vy_ = 0.0;
        } else {
            cmd_msg.linear.x = last_vx_;
            cmd_msg.linear.y = last_vy_;
            cmd_msg.linear.z = 0.0;

            ctrl_msg.valid = true;
            ctrl_msg.stale = false;
            ctrl_msg.saturated = false;
            ctrl_msg.command = cmd_msg;

            debug_msg.data = "ACTIVE: vx=" + std::to_string(last_vx_) + " vy=" + std::to_string(last_vy_);
        }

        cmd_pub_->publish(cmd_msg);
        ctrl_pub_->publish(ctrl_msg);
        debug_pub_->publish(debug_msg);
    }

    std::shared_ptr<PIDController> pid_x_;
    std::shared_ptr<PIDController> pid_y_;

    rclcpp::Subscription<geometry_msgs::msg::Point>::SharedPtr error_sub_;
    rclcpp::Subscription<precision_landing_interfaces::msg::TargetObservation>::SharedPtr obs_sub_;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_pub_;
    rclcpp::Publisher<precision_landing_interfaces::msg::ControlCommand>::SharedPtr ctrl_pub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr debug_pub_;
    rclcpp::TimerBase::SharedPtr timer_;

    rclcpp::Time last_obs_time_;
    bool has_first_obs_{false};
    bool valid_obs_{false};
    double stale_timeout_;

    uint32_t last_processed_sequence_id_{0};
    rclcpp::Time last_processed_stamp_;
    double last_vx_{0.0};
    double last_vy_{0.0};
    bool is_first_processed_{true};
};

} // namespace precision_landing_control_cpp

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<precision_landing_control_cpp::ControlNode>());
    rclcpp::shutdown();
    return 0;
}
