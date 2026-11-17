#pragma once
// Sélection du pilote moteur selon MOTOR_DRIVER (voir motor_config.h).
#include "motor_config.h"
#if MOTOR_DRIVER == MOTOR_DRIVER_PWM
#include "motor_pwm.h"
using MotorDriver=MotorPWM;
#elif MOTOR_DRIVER == MOTOR_DRIVER_I2C
#include "motor_i2c.h"
using MotorDriver=MotorI2C;
#else
#error "MOTOR_DRIVER doit valoir MOTOR_DRIVER_PWM ou MOTOR_DRIVER_I2C (motor_config.h)"
#endif
