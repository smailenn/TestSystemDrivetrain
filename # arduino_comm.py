# arduino_comm.py
import serial
import time

class ArduinoMotorController:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200, timeout=2):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Wait for Arduino to reset

    def send_pulses_per_rev(self, pulses):
        self.ser.write(f"PPR:{pulses}\n".encode())

    def send_move_command(self, start_rpm, target_rpm, run_time, direction, ramp_steps=None):
        cmd = f"MOVE:{start_rpm},{target_rpm},{run_time},{direction}"
        if ramp_steps is not None:
            cmd += f",{ramp_steps}"
        self.ser.write((cmd + "\n").encode())

    def close(self):
        self.ser.close()
