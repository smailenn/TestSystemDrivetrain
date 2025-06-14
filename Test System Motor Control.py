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
import re
import logging

PORT = '/dev/ttyACM0' # on Linux/Mac
BAUD = 115200

pi = pigpio.pi()

file_name = "TRP_M8050_32_Backwards_Clutch_Test3" # Change this to the name of your log file
Test_setup = "17T Cog, SLX RD using clutch, TRP Chain, 1st gear, Pivot Rear, bumper, and 19 lbs/in spring" # Change with setup changes

# Basic config for logging to a file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f"Drivetrain_Shaker_{file_name}.log"),
        logging.StreamHandler()  # This still lets you see output live in your SSH terminal
    ]
)

class SerialMonitor:
    def __init__(self, root, serial_obj):
        self.root = root
        self.ser = serial_obj
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
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
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
        self.ser.close()
        self.root.destroy()



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

        # Join all commands with semicolons, send as a single line after BATCH:
        batch_cmd = "BATCH:" + ";".join(parts) + "\n"
        logging.info(f"Sending batch command to Arduino:\n{batch_cmd}")
        self.ser.write(batch_cmd.encode())
        self.ser.flush()

    def send_reset(self):
        try:
            self.ser.write(b"RESET\n")
            logging.info("Sent RESET command to Arduino")
        except Exception as e:
            logging.info(f"Failed to send RESET to Arduino: {e}")

    def close(self):
        self.ser.close()

def read_arduino_serial(controller, q):
    while True:
        if controller.ser.in_waiting > 0:
            try:
                line = controller.ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    q.put(line)
                    #logging.info(f"[Arduino] {line}")
            except Exception as e:
                logging.info(f"[Serial Read Error] {e}")
        time.sleep(0.05)


# --- Tracking variables ---
motor1_total_pulses = 0
motor1_total_revolutions = 0.0
motor1_total_run_time = 0.0  # seconds
current_drivetrain_cycle = "Idle"

motor1_running = False
motor1_run_start_time = None

# check if 
#if os.environ.get('DISPLAY','') == '':
#    logging.info('no display found. Using :0.0')
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
    logging.error("Failed to connect to pigpio daemon. Make sure it's running.")
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
                logging.error("Warning: No delays in this chunk, skipping...")
                continue  # Skip empty chunks
            
            pi.wave_clear()
            pulses = []

            for delay in delay_chunk:
                if delay <= 0:
                    logging.error(f"Skipping invalid delay: {delay}")
                    continue  # Skip invalid delays

                micros = int(delay * 1_000_000)  # Convert seconds to microseconds
                #logging.info(f"Creating pulse with delay {micros} micros")
                pulses.append(pigpio.pulse(1 << step_pin, 0, micros))  # High
                pulses.append(pigpio.pulse(0, 1 << step_pin, micros))  # Low

            if not pulses:
                logging.debug("Warning: No pulses generated, skipping wave creation.")
                continue  # Skip empty pulse lists

            #logging.info(f"Generated {len(pulses)} pulses.")
            pi.wave_add_generic(pulses)
            wave_id = pi.wave_create()
            if wave_id < 0:
                logging.error("Failed to create waveform")
                return
            #else:
                #logging.info(f"Created waveform with ID {wave_id}")

            #logging.info(f"Sending waveform with ID {wave_id}")
            
            #if wave_id == 0:
                #logging.info("Warning: Wave ID is 0, which may indicate an issue with waveform creation.")

            pi.wave_send_once(wave_id)

            while pi.wave_tx_busy():
                time.sleep(0.001)

            pi.wave_delete(wave_id)

    except Exception as e:
        logging.error(f"Error while sending wave: {e}")


# Function for motor movement

def move_motor(direction_pin, step_pin, RPM, Run_time, direction):
    global motor1_total_pulses, motor1_total_revolutions, motor1_total_run_time
    pi.write(direction_pin, direction)
    STEP_DELAY = 60 / (2 * Pulses_rev * RPM)
    steps = int(2 * 200 * RPM / 60 * Run_time)
    move_start_time = time.time()
    pulses_sent = 0

    for _ in range(steps):
        pi.write(step_pin, 1)
        time.sleep(STEP_DELAY)
        pi.write(step_pin, 0)
        time.sleep(STEP_DELAY)
        pulses_sent += 1

    elapsed = time.time() - move_start_time

    # Track totals for Motor 1 only
    if step_pin == STEP1:
        motor1_total_pulses += pulses_sent
        motor1_total_revolutions += pulses_sent / Pulses_rev
        motor1_total_run_time += Run_time

    #logging.info(f"Run Time: {motor1_total_run_time}")

# Combined ramp-up, cruise, and ramp-down
def move_motor_with_ramp(direction_pin, step_pin, start_RPM, target_RPM, run_time, direction, ramp_steps=None):
    global run_flag
    global motor1_total_pulses, motor1_total_revolutions, motor1_total_run_time
    global motor1_running, motor1_run_start_time

    move_start_time = time.time()
    pulses_sent = 0

    pi.write(direction_pin, direction)
    
    # --- Identify motor by step pin ---
    if step_pin == STEP1:
        pulses_per_rev = Pulses_rev  # Motor 1 drivetrain
        motor_id = "Motor 1"
    elif step_pin == STEP2:
        pulses_per_rev = PULSES_PER_REV  # Motor 2 (only if running directly on Pi)
        motor_id = "Motor 2"
    else:
        logging.error("Unknown step pin, cannot determine motor")
        return
    
    start_delay = 60 / (2 * pulses_per_rev * start_RPM)
    target_delay = 60 / (2 * pulses_per_rev * target_RPM)
    total_steps = int(pulses_per_rev * target_RPM / 60 * run_time)

    # Only auto-calculate ramp_steps if not specified
    if ramp_steps is None:
        rpm_diff = abs(target_RPM - start_RPM)
        base_ramp_steps = 200  # A safe default
        ramp_steps = int(base_ramp_steps * (rpm_diff / 20))  # Scale with RPM delta
        ramp_steps = min(ramp_steps, total_steps // 2)
        #logging.info(f"Auto-calculated ramp_steps: {ramp_steps}")
    else:
        pass
        #logging.info(f"Using user-specified ramp_steps: {ramp_steps}")

    cruise_steps = total_steps - 2 * ramp_steps
    MIN_DELAY = 0.00001
    
    #logging.info(f"{motor_id}: {start_RPM}->{target_RPM} RPM, {run_time}s, {total_steps} steps")

    delays = []

    # Ramp-up
    for i in range(ramp_steps):
        if not run_flag: return
        p = i / ramp_steps
        d = interpolate_delay_sine(p, start_delay, target_delay)
        delays.append(max(d, MIN_DELAY))
        pulses_sent += 1

    # Cruise
    for _ in range(cruise_steps):
        if not run_flag: return
        delays.append(max(target_delay, MIN_DELAY))
        pulses_sent += 1

    # Ramp-down
    for i in range(ramp_steps):
        if not run_flag: return
        p = i / ramp_steps
        d = interpolate_delay_sine(p, target_delay, start_delay)
        delays.append(max(d, MIN_DELAY))
        pulses_sent += 1

    elapsed = time.time() - move_start_time

    # --- Track motor 1 specific data ---
    if step_pin == STEP1:
        motor1_total_pulses += pulses_sent
        motor1_total_revolutions += pulses_sent / pulses_per_rev
        motor1_total_run_time += run_time
        motor1_running = True
        motor1_run_start_time = time.time()

    #logging.info("Generated delays:", delays)
    #logging.info(f"Run Time: {motor1_total_run_time}")
    generate_steps_with_pigpio(step_pin, delays)
    #log_motor1_stats()

def log_motor1_stats():
    logging.info(f"[Motor 1] Total pulses: {motor1_total_pulses}")
    logging.info(f"[Motor 1] Total revolutions: {motor1_total_pulses / Pulses_rev:.2f}")
    logging.info(f"[Motor 1] Total run time: {motor1_total_run_time:.2f} seconds")

def log_motor1_summary():
    logging.info("="*40)
    logging.info("MOTOR 1 SESSION SUMMARY")
    logging.info(f"Total pulses: {motor1_total_pulses}")
    logging.info(f"Total revolutions: {motor1_total_pulses / Pulses_rev:.2f}")
    logging.info(f"Total run time: {motor1_total_run_time:.2f} seconds")
    logging.info(f"How did change drop if it did:")
    logging.info(f"Drivetrain Shaker Test Setup: {Test_setup}")

    if motor1_total_run_time > 0:
        average_rpm = (motor1_total_pulses / Pulses_rev) / (motor1_total_run_time / 60)
        logging.info(f"Average RPM: {average_rpm:.2f}")
    else:
        logging.info("Average RPM: N/A (no runtime)")
    
    logging.info("="*40)

# if __name__ == '__main__':
#     motor2 = ArduinoMotorController('/dev/ttyACM0')
#     motor2.send_reset()
#     motor2.send_pulses_per_rev(PULSES_PER_REV)

#     root = tk.Tk()
#     app = SerialMonitor(root, motor2.ser)
#     root.mainloop()

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    global current_drivetrain_cycle
    logging.info("Starting Motor 1 sequence...")
    time.sleep(20)
    for i in range(1,10):  # 9 cycles
        current_drivetrain_cycle = f"Drivetrain Cycle {i}"
        logging.info({current_drivetrain_cycle})
        Drivetrain_Cycle()
        #time.sleep(1)
    logging.info("Testing Completed.  The Chain Survived!")

def Drivetrain_Cycle():
    logging.info("Starting Drivetrain Cycle with ramp...")
    move_motor_with_ramp(DIR1, STEP1, 80, 80, 6, False) # Motor 1 Forward
    move_motor_with_ramp(DIR1, STEP1, 120, 140, 2, False) # Motor 1 Forward
    #time.sleep(0.5)
    move_motor_with_ramp(DIR1, STEP1, 80, 80, 1, True) # Motor 2 Backward
    move_motor_with_ramp(DIR1, STEP1, 100, 100, 1, True)
    #time.sleep(0.5)
    move_motor(DIR1, STEP1, 110, 1, False)
    move_motor(DIR1, STEP1, 140, 2, True)
    move_motor(DIR1, STEP1, 80, 1, False)
    move_motor(DIR1, STEP1, 140, 1, True)
    #time.sleep(0.5)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    move_motor(DIR1, STEP1, 180, 1, False)
    move_motor(DIR1, STEP1, 180, 1, True)
    #time.sleep(0.5)
    move_motor_with_ramp(DIR1, STEP1, 100, 100, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 100, 80, 2, True)
    logging.info("Drivetrain Cycle complete")

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    motor2.ser.reset_input_buffer()  # Clear any existing data in the input buffer
    motor2.ser.reset_output_buffer()  # Clear any existing data in the output buffer
    logging.info("Starting Motor 2 sequence with ramp...")
    # Motor moves are sent below in a batch
    # Initially get up to speed for first ramp, 20 seconds total
    commands = [
        (5, 80, 10, 0, 1000),      #warm up
        (80, 100, 10, 0, 8000),    #warm up
        (100, 108, 54, 0, 9000),   #1
        (108, 112, 54, 0, 9000),   #2
        (112, 116, 54, 0, 9000),   #3
        (116, 117, 54, 0, 9000),   #4
        (117, 118, 54, 0, 9000),   #5
        (118, 119, 54, 0, 9000),   #6
        (119, 120, 54, 0, 9000),   #7
        (120, 121, 54, 0, 9000),   #8
        (121, 121, 60, 0, 9000)    #9
    ]

    motor2.send_move_batch(commands)
    
    # Listen for completion or interrupt
    start_time = time.time()
    while run_flag:
        try:
            line = serial_queue.get(timeout=0.05)
            if line == "FORCE_STOP":
                logging.info("Motor 2 sequence interrupted by FORCE_STOP command.")
                break
            if not run_flag:
                break
            if line == "DONE":
                logging.info("Motor 2 batch complete")
                break
            else:
                logging.info(f"[Arduino-M2] {line}")
        except queue.Empty:
            if not run_flag:
                break
            pass  # No message, continue checking

    if not run_flag and not (line == "DONE" if 'line' in locals() else False) : # Check if interrupted vs completed
        logging.debug("Motor 2 sequence interrupted before completion or 'DONE' received.")
    elif not (line == "DONE" if 'line' in locals() else False):
         logging.warning("Motor 2 sequence finished but 'DONE' was not the reason (e.g. timeout).")

#####################################################
def start_motors():
    global run_flag
    run_flag = True #Enable motor movement
    logging.info("Get Ready!  Moving motors in sequence...")
    logging.info("Press Ctrl+C to stop!!!")
    for i in range(3, 0, -1):
        logging.info(f"Moving in {i} . . .")
        time.sleep(1)
    logging.info("Motors GO!")

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
        logging.info("Testing has concluded / Stopping Motors . . . ")  
        logging.info("///////")
        logging.info("///////")
        logging.info("///////")
    except KeyboardInterrupt:
        logging.info("\nKeyboardInterrupt detected!  Stopping motors . . . ")
        logging.info(f"Interrupted during drivetrain cycle: {current_drivetrain_cycle}")
        stop_motors()

def stop_motors():
    global run_flag
    run_flag = False
    logging.info("Stopping Motors . . . ")  
    try:
        motor2.ser.write(b"STOP\n")
    except Exception as e:
        logging.error(f"Failed to send STOP to Arduino: {e}")
    # Wake up Motor2_sequence if its blocked
    serial_queue.put("FORCE_STOP")

if __name__ == "__main__":
    atexit.register(stop_motors)
    try:
        start_motors()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected! Stopping motors . . .")
        stop_motors()
        logging.info(f"Interrupted during drivetrain cycle: {current_drivetrain_cycle}")
    finally:
        log_motor1_summary()
        logging.info('\nTesting has concluded')
        time.sleep(1)
        pi.stop()
        for handler in logging.getLogger().handlers:
            handler.flush()
