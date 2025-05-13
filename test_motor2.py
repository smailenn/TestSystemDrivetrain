import pigpio
import time
import threading
import math
import sys
import serial

pi = pigpio.pi()


def test_motor_constant_speed(step_pin, delay, steps):
    for _ in range(steps):
        pi.write(step_pin, 1)
        time.sleep(delay)
        pi.write(step_pin, 0)
        time.sleep(delay)

test_motor_constant_speed(STEP1, 0.001, 1000)  # Test with 1ms delay





# test_motor2.py
# from arduino_comm import ArduinoMotorController

# PULSES_PER_REV = 400 #Pulses per revolution, Motor 2, set on driver

# # Initialize the motor controller
# motor2 = ArduinoMotorController('/dev/ttyACM0')

# # Send the move command
# motor2.send_move_command(5, 30, 10, 1, 400)
