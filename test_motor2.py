import serial
import time

ser = serial.Serial('/dev/ttyACM0', 115200)
time.sleep(2)  # Wait for the Arduino to reset

ser.write(b'Hello from Pi\n')
print("Message sent.")









# test_motor2.py
# from arduino_comm import ArduinoMotorController

# PULSES_PER_REV = 400 #Pulses per revolution, Motor 2, set on driver

# # Initialize the motor controller
# motor2 = ArduinoMotorController('/dev/ttyACM0')

# # Send the move command
# motor2.send_move_command(5, 30, 10, 1, 400)
