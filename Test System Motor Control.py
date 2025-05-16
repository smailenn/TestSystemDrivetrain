# Test System Drivetrain Motor control
# Look at test system drivetrain.xlsx in Engineering\Equipment\Drivetrain Tester Project folder for more information including motion analysis and variables
# Using VSC to ssh shell into Raspberry Pi 4 B headless to interact and run code
# ssh 192.168.1.134 ip of Raspberry Pi
# typical is mailman@SeanPi.local
# Password currently:  MRP! 

import pigpio
import time
import threading
import math
import sys
import serial
import queue
import atexit
import tkinter as tk
import serial
import threading
import time
import re

PORT = '/dev/ttyACM0' # on Linux/Mac
BAUD = 115200
ser = serial.Serial(PORT, BAUD, timeout=1)

pi = pigpio.pi()


class SerialMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Motor RPM Monitor")

        self.rpm_label = tk.Label(root, text="RPM: --", font=("Helvetica", 32))
        self.rpm_label.pack(padx=20, pady=20)

        self.running = True
        self.thread = threading.Thread(target=self.read_serial)
        self.thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def read_serial(self):
        rpm_pattern = re.compile(r"RPM[:\s]+(\d+(\.\d+)?)")
        while self.running:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                match = rpm_pattern.search(line)
                if match:
                    rpm = match.group(1)
                    self.update_rpm(rpm)
            time.sleep(0.05)

    def update_rpm(self, rpm):
        self.rpm_label.config(text=f"RPM: {rpm}")

    def close(self):
        self.running = False
        self.thread.join()
        ser.close()
        self.root.destroy()

# if __name__ == '__main__':
#     root = tk.Tk()
#     app = SerialMonitor(root)
#     root.mainloop()

class ArduinoMotorController:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200, timeout=0.1):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Wait for Arduino to reset

    def send_pulses_per_rev(self, pulses):
        self.ser.write(f"PPR:{pulses}\n".encode())

    def send_move_batch(self, commands):
        parts = []
        for c in commands:
            cmd_parts = list(map(str, c[:4]))
            if len(c) > 4 and c[4] is not None:
                cmd_parts.append(str(c[4]))
            parts.append(",".join(cmd_parts))

        batch_cmd = "BATCH:\n" + "\n".join(parts)
        print(f"Sending batch command to Arduino:\n{batch_cmd}")
        # self.ser.write(batch_cmd.encode())  # REMOVE the extra + "\n"
        self.ser.write((batch_cmd + "\n").encode())  # <- Add the newline here if Arduino expects it
        self.ser.flush()

    def send_reset(self):
        try:
            self.ser.write(b"RESET\n")
            print("Sent RESET command to Arduino")
        except Exception as e:
            print(f"Failed to send RESET to Arduino: {e}")

    def close(self):
        self.ser.close()

def read_arduino_serial(controller, q):
    while True:
        if controller.ser.in_waiting > 0:
            try:
                line = controller.ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    q.put(line)
                    print(f"[Arduino] {line}")
            except Exception as e:
                print(f"[Serial Read Error] {e}")
        time.sleep(0.05)


# check if 
#if os.environ.get('DISPLAY','') == '':
#    print('no display found. Using :0.0')
#    os.environ.__setitem__('DISPLAY', ':0.0')

# Pin configuration for motor 1 - Drivetrain
DIR1 = 27   # Direction pin for motor 1
STEP1 = 22  # Step pin for motor 1

# Pin configuration for motor 2 - Oscillation
# Only used if motor directly connected to Raspberry Pi GPIO pins
# If using Arduino, use ArduinoMotorController class
DIR2 = 24   # Direction pin for motor 2
STEP2 = 23  # Step pin for motor 2

pi.set_mode(STEP1, pigpio.OUTPUT)
pi.set_mode(DIR1, pigpio.OUTPUT)
pi.set_mode(STEP2, pigpio.OUTPUT)
pi.set_mode(DIR2, pigpio.OUTPUT)

# Set initial pin states (optional but good practice)
pi.write(STEP1, 0)
pi.write(DIR1, 0)
pi.write(STEP2, 0)
pi.write(DIR2, 0)

# Motor parameters
# Nema 34, 1.8 deg (200 steps), 12 Nm, 6 A
# DM860T Stepper Driver
# Settings:  7.2A Peak, 6A Ref / 400 Pulse/Rev 
Pulses_rev = 400 #Pulses per revolution, Motor 1 (Drivetrain), set on driver
PULSES_PER_REV = 400 #Pulses per revolution, Motor 2 (Shaker), set on driver

if not pi.connected:
    print("Failed to connect to pigpio daemon. Make sure it's running.")
    sys.exit(1)

#Global flag for stopping motors
run_flag = True

motor2 = ArduinoMotorController('/dev/ttyACM0')
motor2.send_reset()  # Reset Arduino state at start
motor2.send_pulses_per_rev(PULSES_PER_REV)

# Start serial reader thread for debug output
serial_queue = queue.Queue()
serial_thread = threading.Thread(target=read_arduino_serial, args=(motor2, serial_queue), daemon=True)
serial_thread.start()


# Function for motor movement with slow ramp for motor control
def interpolate_delay_sine(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * math.sin(progress * (math.pi / 2))

# Function for motor movement with linear ramp  
def interpolate_delay_linear(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * progress

# Create pigpio step waveform
def generate_steps_with_pigpio(step_pin, delays):
    """
    Generate step pulses on a given GPIO pin using pigpio, in chunks to avoid crashing pigpiod.
    """
    try:
        for i in range(0, len(delays), 1000):  # Chunk size for handling large lists
            delay_chunk = delays[i:i + 1000]
            
            if len(delay_chunk) == 0:
                print("Warning: No delays in this chunk, skipping...")
                continue  # Skip empty chunks
            
            pi.wave_clear()
            pulses = []

            for delay in delay_chunk:
                if delay <= 0:
                    print(f"Skipping invalid delay: {delay}")
                    continue  # Skip invalid delays

                micros = int(delay * 1_000_000)  # Convert seconds to microseconds
                #print(f"Creating pulse with delay {micros} micros")
                pulses.append(pigpio.pulse(1 << step_pin, 0, micros))  # High
                pulses.append(pigpio.pulse(0, 1 << step_pin, micros))  # Low

            if not pulses:
                print("Warning: No pulses generated, skipping wave creation.")
                continue  # Skip empty pulse lists

            #print(f"Generated {len(pulses)} pulses.")
            pi.wave_add_generic(pulses)
            wave_id = pi.wave_create()
            if wave_id < 0:
                print("Failed to create waveform")
                return
            #else:
                #print(f"Created waveform with ID {wave_id}")

            #print(f"Sending waveform with ID {wave_id}")
            
            #if wave_id == 0:
                #print("Warning: Wave ID is 0, which may indicate an issue with waveform creation.")

            pi.wave_send_once(wave_id)

            while pi.wave_tx_busy():
                time.sleep(0.001)

            pi.wave_delete(wave_id)

    except Exception as e:
        print(f"Error while sending wave: {e}")


# Function for motor movement
# Combined ramp-up, cruise, and ramp-down
def move_motor_with_ramp(direction_pin, step_pin, start_RPM, target_RPM, run_time, direction, ramp_steps=100):
    global run_flag
    pi.write(direction_pin, direction)
    Motor_ID = "Motor 1" if direction_pin == DIR1 else "Motor 2"

    start_delay = 60 / (2 * Pulses_rev * start_RPM)
    target_delay = 60 / (2 * Pulses_rev * target_RPM)
    total_steps = int(Pulses_rev * target_RPM / 60 * run_time)

    if ramp_steps * 2 > total_steps:
        ramp_steps = total_steps // 2

    cruise_steps = total_steps - 2 * ramp_steps
    MIN_DELAY = 0.00001
    
    #print(f"{Motor_ID}: {start_RPM}->{target_RPM} RPM, {run_time}s, {total_steps} steps")

    delays = []

    # Ramp-up
    for i in range(ramp_steps):
        if not run_flag: return
        p = i / ramp_steps
        d = interpolate_delay_sine(p, start_delay, target_delay)
        delays.append(max(d, MIN_DELAY))

    # Cruise
    for _ in range(cruise_steps):
        if not run_flag: return
        delays.append(max(target_delay, MIN_DELAY))

    # Ramp-down
    for i in range(ramp_steps):
        if not run_flag: return
        p = i / ramp_steps
        d = interpolate_delay_sine(p, target_delay, start_delay)
        delays.append(max(d, MIN_DELAY))

    #print("Generated delays:", delays)
    generate_steps_with_pigpio(step_pin, delays)

def test_motor_constant_speed(step_pin, delay, steps):
    for _ in range(steps):
        pi.write(step_pin, 1)
        time.sleep(delay)
        pi.write(step_pin, 0)
        time.sleep(delay)


# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    print("Starting Motor 1 sequence...")
    time.sleep(25)
    print("Drivetrain Cycle 1")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 2")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 3")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 4")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 5")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 6")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 7")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 8")
    Drivetrain_Cycle()
    time.sleep(2)
    print("Drivetrain Cycle 9")
    Drivetrain_Cycle()
    print("Testing Completed.  The Chain Survived!")

def Drivetrain_Cycle():
    # Currently 23 run time
    print("Starting Drivetrain Cycle with ramp...")
    move_motor_with_ramp(DIR1, STEP1, 5, 80, 6, False)
    move_motor_with_ramp(DIR1, STEP1, 80, 140, 2, False)
    time.sleep(0.5)
    #print("Part 2")
    move_motor_with_ramp(DIR1, STEP1, 80, 80, 1, True)
    move_motor_with_ramp(DIR1, STEP1, 100, 100, 1, True)
    time.sleep(0.5)
    #print("Part 3")
    move_motor_with_ramp(DIR1, STEP1, 80, 110, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 100, 140, 2, True)
    move_motor_with_ramp(DIR1, STEP1, 60, 80, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 85, 85, 1, True)
    time.sleep(0.5)
    #print("Part 4")
    move_motor_with_ramp(DIR1, STEP1, 85, 70, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 130, 150, 1, True)
    move_motor_with_ramp(DIR1, STEP1, 85, 70, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 130, 150, 1, True)
    move_motor_with_ramp(DIR1, STEP1, 85, 70, 0.5, False)
    move_motor_with_ramp(DIR1, STEP1, 130, 150, 0.5, True)
    #print("Abusive")
    move_motor_with_ramp(DIR1, STEP1, 85, 85, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 140, 140, 1, True)
    move_motor_with_ramp(DIR1, STEP1, 85, 85, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 140, 140, 1, True)
    move_motor_with_ramp(DIR1, STEP1, 85, 85, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 140, 140, 1, True)
    time.sleep(0.5)
    #print("Part 5")
    move_motor_with_ramp(DIR1, STEP1, 100, 100, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 100, 80, 2, True)   # Motor 1 Backward
    print("Drivetrain Cycle complete")

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    print("Starting Motor 2 sequence with ramp...")
    # Motor moves are sent below in a batch
    # Initially get up to speed for first ramp, 20 seconds total
    # Step 1:  100 rpm for 25 seconds
    # Ramp up again to speed for 10 seconds
    # Step 2-9: ramp up 4 rpm per step  
    commands = [
        (5, 80, 10, 0, 1000),
        (80, 100, 10, 0, 8000),
        (100, 108, 36, 0, 10000),   #1
        (108, 112, 36, 0, 10000),   #2
        (112, 116, 36, 0, 10000),   #3
        (116, 120, 36, 0, 10000),   #4
        (120, 122, 36, 0, 10000),   #5
        (122, 124, 36, 0, 10000),   #6
        (124, 126, 36, 0, 10000),   #7
        (126, 128, 36, 0, 10000),   #8
        (128, 130, 36, 0, 10000),   #9
        #(100, 5, 20, 0, 500),
    ]

    motor2.send_move_batch(commands)
    
    # Listen for completion or interrupt
    start_time = time.time()
    while run_flag:
        try:
            line = serial_queue.get(timeout=0.1)
            if line == "DONE":
                print("Motor 2 batch complete")
                break
            else:
                print(f"[Arduino-M2] {line}")
        except queue.Empty:
            pass  # No message, continue checking

    if not run_flag:
        print("Motor 2 sequence interrupted")
    
    
#####################################################
def start_motors():
    global run_flag
    run_flag = True #Enable motor movement
    print("Get Ready!  Moving motors in sequence...")
    print("Press Ctrl+C to stop!!!")
    for i in range(3, 0, -1):
        print(f"Moving in {i} . . .")
        time.sleep(1)
    print("Motors GO!")

    motor1_thread = threading.Thread(target=Motor1_sequence)
    motor2_thread = threading.Thread(target=Motor2_sequence)

    # Start motors
    motor1_thread.start()
    motor2_thread.start()

    # Synchronize both motors' start
    #start_event.set()

    # Wait for both threads to finish
    try:
        motor1_thread.join()
        motor2_thread.join()
        print("Testing has concluded / Stopping Motors . . . ")  
        print("///////")
        print("///////")
        print("///////")
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected!  Stopping motors . . . ")
    stop_motors()

def stop_motors():
    global run_flag
    run_flag = False
    print("Stopping Motors . . . ")  
    try:
        motor2.ser.write(b"STOP\n")
    except Exception as e:
        print(f"Failed to send STOP to Arduino: {e}")

if __name__ == "__main__":
    try:
        start_motors()
    except KeyboardInterrupt:
        stop_motors()
        print('\nTesting has concluded')
        atexit.register(stop_motors)
