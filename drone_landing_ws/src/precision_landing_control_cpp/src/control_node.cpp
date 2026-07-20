#include <chrono>
#include <memory>
#include <string>
#include <cmath>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/string.hpp"
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

        error_sub_ = this->create_subscription<geometry_msgs::msg::Point>(
            "/aruco/center_error", 10, std::bind(&ControlNode::error_callback, this, _1));
            
        cmd_pub_ = this->create_publisher<geometry_msgs::msg::Twist>("/precision_landing/cmd_vel", 10);
        debug_pub_ = this->create_publisher<std_msgs::msg::String>("/precision_landing/control_debug", 10);

        timer_ = this->create_wall_timer(
            50ms, std::bind(&ControlNode::timer_callback, this)); // 20Hz control loop

        last_obs_time_ = this->now();
        last_calc_time_ = this->now();
        has_first_obs_ = false;
        
        RCLCPP_INFO(this->get_logger(), "Precision Landing C++ Control Node Started.");
    }

private:
    void error_callback(const geometry_msgs::msg::Point::SharedPtr msg)
    {
        latest_error_ = *msg;
        last_obs_time_ = this->now();
        has_first_obs_ = true;
    }

    void timer_callback()
    {
        auto now = this->now();
        double dt = (now - last_calc_time_).seconds();
        last_calc_time_ = now;

        geometry_msgs::msg::Twist cmd_msg;
        std_msgs::msg::String debug_msg;

        // Check for stale timeout
        if (!has_first_obs_ || (now - last_obs_time_).seconds() > stale_timeout_) {
            // Target lost or no observation
            pid_x_->reset();
            pid_y_->reset();
            
            cmd_msg.linear.x = 0.0;
            cmd_msg.linear.y = 0.0;
            cmd_msg.linear.z = 0.0;
            
            debug_msg.data = "STALE_OBSERVATION";
        } else {
            // Valid observation
            // The coordinate system:
            // x error -> pitch -> y velocity (in some setups), but let's assume direct mapping for now,
            // or x error -> x velocity. Wait, usually x error is horizontal on image. 
            // In px4_vision_autonomy Python code, let's see how they do it.
            // But here we'll just compute generic output from x and y error.
            double vx = pid_x_->compute(latest_error_.x, dt);
            double vy = pid_y_->compute(latest_error_.y, dt);
            
            cmd_msg.linear.x = vx;
            cmd_msg.linear.y = vy;
            cmd_msg.linear.z = 0.0; // Descent is usually managed by mission commander or we can add it here.
            
            debug_msg.data = "ACTIVE: vx=" + std::to_string(vx) + " vy=" + std::to_string(vy);
        }

        cmd_pub_->publish(cmd_msg);
        debug_pub_->publish(debug_msg);
    }

    std::shared_ptr<PIDController> pid_x_;
    std::shared_ptr<PIDController> pid_y_;
    
    rclcpp::Subscription<geometry_msgs::msg::Point>::SharedPtr error_sub_;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_pub_;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr debug_pub_;
    rclcpp::TimerBase::SharedPtr timer_;

    geometry_msgs::msg::Point latest_error_;
    rclcpp::Time last_obs_time_;
    rclcpp::Time last_calc_time_;
    bool has_first_obs_;
    double stale_timeout_;
};

} // namespace precision_landing_control_cpp

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<precision_landing_control_cpp::ControlNode>());
    rclcpp::shutdown();
    return 0;
}
