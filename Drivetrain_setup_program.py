# Test System Drivetrain Setup Program 
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

pi = pigpio.pi()


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
# Combined ramp-up, cruise, and ramp-down
def move_motor_with_ramp(direction_pin, step_pin, start_RPM, target_RPM, run_time, direction, ramp_steps=100):
    global run_flag
    global motor1_total_pulses, motor1_total_revolutions, motor1_total_run_time
    global motor1_running, motor1_run_start_time

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

    if ramp_steps * 2 > total_steps:
        ramp_steps = total_steps // 2

    cruise_steps = total_steps - 2 * ramp_steps
    MIN_DELAY = 0.00002
    
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

    #logging.info("Generated delays:", delays)
    generate_steps_with_pigpio(step_pin, delays)

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    global current_drivetrain_cycle
    logging.info("Starting Motor 1 sequence...")
    Drivetrain_Cycle()

def Drivetrain_Cycle():
    logging.info("Starting Drivetrain Cycle with ramp...")
    move_motor_with_ramp(DIR1, STEP1, 5, 40, 120, False)
    logging.info("Drivetrain Cycle complete")

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

    # Start motors
    motor1_thread.start()

    # Synchronize both motors' start
    #start_event.set()

    # Wait for both threads to finish
    try:
        motor1_thread.join()
        logging.info("Testing has concluded / Stopping Motors . . . ")  
        logging.info("///////")
        logging.info("///////")
        logging.info("///////")
    except KeyboardInterrupt:
        logging.info("\nKeyboardInterrupt detected!  Stopping motors . . . ")
        logging.info(f"Interrupted during drivetrain cycle: {current_drivetrain_cycle}")
    finally:
        stop_motors()
        pi.stop()

def stop_motors():
    global run_flag
    run_flag = False
    logging.info("Stopping Motors . . . ")  
    try:
        logging.info("Sending STOP to Arduino . . . ")
    except Exception as e:
        logging.error(f"Failed to send STOP to Arduino: {e}")

if __name__ == "__main__":
    try:
        start_motors()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected! Stopping motors . . .")
        logging.info(f"Interrupted during drivetrain cycle: {current_drivetrain_cycle}")
    finally:
        stop_motors()
        for handler in logging.getLogger().handlers:
            handler.flush()
        pi.stop()
        logging.info('\nTesting has concluded')
        atexit.register(stop_motors)
