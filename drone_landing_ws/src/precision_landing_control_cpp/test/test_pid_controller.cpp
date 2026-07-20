#include <gtest/gtest.h>
#include "precision_landing_control_cpp/pid_controller.hpp"

using namespace precision_landing_control_cpp;

TEST(PIDControllerTest, ZeroError) {
    PIDConfig config;
    config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(0.0, 0.1), 0.0);
}

TEST(PIDControllerTest, PositiveError) {
    PIDConfig config;
    config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
    config.output_max = 5.0;
    config.output_min = -5.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(2.0, 0.1), 2.0);
}

TEST(PIDControllerTest, NegativeError) {
    PIDConfig config;
    config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
    config.output_max = 5.0;
    config.output_min = -5.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(-2.0, 0.1), -2.0);
}

TEST(PIDControllerTest, Deadband) {
    PIDConfig config;
    config.kp = 1.0; config.ki = 0.0; config.kd = 0.0;
    config.deadband = 1.0;
    config.output_max = 5.0;
    config.output_min = -5.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(0.5, 0.1), 0.0);
    EXPECT_DOUBLE_EQ(pid.compute(2.0, 0.1), 2.0); // Wait, depending on implementation it might be 2.0 or 1.0. My impl returns kp*error so 2.0
}

TEST(PIDControllerTest, Saturation) {
    PIDConfig config;
    config.kp = 10.0;
    config.output_max = 5.0;
    config.output_min = -5.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(1.0, 0.1), 5.0); // 10.0 -> clamped to 5.0
    EXPECT_DOUBLE_EQ(pid.compute(-1.0, 0.1), -5.0);
}

TEST(PIDControllerTest, IntegralLimit) {
    PIDConfig config;
    config.kp = 0.0; config.ki = 10.0; config.kd = 0.0;
    config.integral_max = 1.0;
    config.integral_min = -1.0;
    config.output_max = 100.0;
    config.output_min = -100.0;
    PIDController pid(config);
    // integrate +10 for dt=1 -> integral = 10, clamped to 1. Output = ki*1 = 10
    EXPECT_DOUBLE_EQ(pid.compute(10.0, 1.0), 10.0);
}

TEST(PIDControllerTest, Reset) {
    PIDConfig config;
    config.kp = 0.0; config.ki = 1.0; config.kd = 0.0;
    config.output_max = 10.0;
    config.output_min = -10.0;
    config.integral_max = 10.0;
    config.integral_min = -10.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(1.0, 1.0), 1.0);
    pid.reset();
    EXPECT_DOUBLE_EQ(pid.compute(0.0, 1.0), 0.0); // should be 0 because integral is reset
}

TEST(PIDControllerTest, DerivativeFirstSample) {
    PIDConfig config;
    config.kp = 0.0; config.ki = 0.0; config.kd = 1.0;
    config.output_max = 10.0;
    config.output_min = -10.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(1.0, 1.0), 0.0); // First sample, derivative is 0
    EXPECT_DOUBLE_EQ(pid.compute(2.0, 1.0), 1.0); // Second sample, derivative is (2-1)/1 = 1
}

TEST(PIDControllerTest, InvalidDt) {
    PIDConfig config;
    config.kp = 1.0; config.ki = 1.0; config.kd = 1.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(1.0, -1.0), 0.0);
    EXPECT_DOUBLE_EQ(pid.compute(1.0, 0.0), 0.0);
}

TEST(PIDControllerTest, FiniteOutput) {
    PIDConfig config;
    config.kp = 1.0;
    PIDController pid(config);
    EXPECT_DOUBLE_EQ(pid.compute(std::nan(""), 0.1), 0.0);
    EXPECT_DOUBLE_EQ(pid.compute(std::numeric_limits<double>::infinity(), 0.1), 0.0);
}

int main(int argc, char **argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
