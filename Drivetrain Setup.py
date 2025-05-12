import gpiozero as GPIO
from gpiozero import DigitalOutputDevice
import time
import threading
import tkinter as tk 
import sys
import os
import math 

# Test System Drivetrain Motor control
# Look at test system drivetrain.xlsx in Engineering\Equipment\Drivetrain Tester Project folder for more information including motion analysis and variables
# Using VSC to ssh shell into Raspberry Pi 4 B headless to interact and run code
# ssh 192.168.1.134 ip of Raspberry Pi
# typical is mailman@SeanPi.local
# Password currently:  MRP!

# check if 
#if os.environ.get('DISPLAY','') == '':
#    print('no display found. Using :0.0')
#    os.environ.__setitem__('DISPLAY', ':0.0')

# Pin configuration for motor 1 - Drivetrain
DIR1 = 27   # Direction pin for motor 1
STEP1 = 22  # Step pin for motor 1

# Pin configuration for motor 2 - Oscillation
DIR2 = 24   # Direction pin for motor 2
STEP2 = 23  # Step pin for motor 2

# Motor parameters
# Nema 34, 1.8 deg (200 steps), 12 Nm, 6 A
# DM860T Stepper Driver
# Settings:  7.2A Peak, 6A Ref / 400 Pulse/Rev 
Pulses_rev = 800 #Pulses per revolution, set on driver

# Setup GPIO
dir1 = GPIO.DigitalOutputDevice(DIR1)
step1 = GPIO.DigitalOutputDevice(STEP1)

dir2 = GPIO.DigitalOutputDevice(DIR2)
step2 = GPIO.DigitalOutputDevice(STEP2)

#threading
run = True

#Global flag for stopping motors
run_flag = True

# Function for motor movement
def move_motor(direction_pin, step_pin, current_RPM, target_RPM, Run_time, direction):
    global run_flag
    # Moves a stepper motor a specified number of steps.

    #Args:
        #  direction_pin (OutputDevice): GPIO pin for direction control.
        #  step_pin (OutputDevice): GPIO pin for step control.
        #  STEP_DELAY (float): Delay between steps.
        #  steps (int): Number of steps to move.
        #  RPM (int): Motor speed in revolutions per minute.    
        #  Run_time (int): Time in seconds to run motor.    
        #  direction (bool): True for one direction, False for the other.
    
    direction_pin.value = direction  # Set direction

    # Let me know what motors are running what function
    Motor_ID = "Motor 1" if direction_pin == dir1 else "Motor 2"    

    STEP_DELAY = 60 / (2 * Pulses_rev * target_RPM) # Delay between steps in seconds  (60 seconds / (Pulses/Rev * RPM))   
    steps = int(Pulses_rev * target_RPM / 60 * Run_time) # Calculated Steps

    print(f"Motor: {Motor_ID}, RPM: {target_RPM}, Run_time: {Run_time}")  
    #print(f"Motor: {Motor_ID}, STEP_DELAY: {STEP_DELAY}, Steps: {steps}, RPM: {RPM}, Run_time: {Run_time}")    
   
    for _ in range(steps):
        if not run_flag: # Stop if flag is set
            print(f"Stopping {Motor_ID}")
            return
        
        #print(f"[{time.strftime('%H:%M:%S')}] Step {step}/{total_steps} | Delay: {delay:.6f}s")
        step_pin.on()
        time.sleep(STEP_DELAY)
        step_pin.off()
        time.sleep(STEP_DELAY)

# Function for motor movement with slow ramp for motor control
def interpolate_delay_sine(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * math.sin(progress * (math.pi / 2))

# Function for motor movement with linear ramp  
def interpolate_delay_linear(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * progress

# Function for motor movement with Ramp-Up
def move_motor_with_ramp_up(direction_pin, step_pin, current_RPM, target_RPM, Run_time, direction, ramp_steps=100):
    global run_flag

    direction_pin.value = direction
    Motor_ID = "Motor 1" if direction_pin == dir1 else "Motor 2"

    full_delay = 60 / (2 * Pulses_rev * target_RPM)
    current_delay = 60 / (2 * Pulses_rev * current_RPM) 
    total_steps = int(Pulses_rev * target_RPM / 60 * Run_time)

    if ramp_steps > total_steps:
        ramp_steps = total_steps

    print(f"{Motor_ID} w/ RAMP-UP: Current RPM={current_RPM}, Target RPM={target_RPM}, Time={Run_time}, Steps={total_steps}")

    for step in range(total_steps):
        if not run_flag:
            print(f"Stopping {Motor_ID}")
            return

        if step < ramp_steps:  # Ramp-up phase
            progress = step / ramp_steps
            delay = interpolate_delay_linear(progress, current_delay, full_delay)
        else:  # Constant speed phase
            delay = full_delay

        #print(f"[{time.strftime('%H:%M:%S')}] Step {step}/{total_steps} | Delay: {delay:.6f}s")

        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

# Function for motor movement with Ramp-Down
def move_motor_with_ramp_down(direction_pin, step_pin, current_RPM, target_RPM, steps, direction, ramp_steps=100):
    global run_flag

    direction_pin.value = direction
    Motor_ID = "Motor 1" if direction_pin == dir1 else "Motor 2"

    full_delay = 60 / (2 * Pulses_rev * target_RPM)
    current_delay = 60 / (2 * Pulses_rev * current_RPM)

    if ramp_steps > steps:
        ramp_steps = steps

    print(f"{Motor_ID} w/ RAMP-DOWN: RPM={target_RPM}, Steps={steps}")

    for step in range(steps):
        if not run_flag:
            print(f"Stopping {Motor_ID}")
            return

        if step >= steps - ramp_steps:  # Ramp-down phase
            progress = (step - (steps - ramp_steps)) / ramp_steps
            delay = interpolate_delay_sine(1 - progress, current_delay, full_delay)
        else:  # Constant speed phase
            delay = full_delay

        #print(f"[{time.strftime('%H:%M:%S')}] Step {step}/{total_steps} | Delay: {delay:.6f}s")

        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    print("Starting Motor 1 sequence...")
    print("Running Pedaling Cycle")
    move_motor_with_ramp_up(dir1, step1, 5, 40, 2, True, ramp_steps=100)   # Motor 1 forward
    move_motor(dir1, step1, 40, 40, 40, True)   # Motor 1 forward
   
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

    # Start Motor 1 Drivetrain in its own thread
    motor1_thread = threading.Thread(target=Motor1_sequence)

    # Start them
    motor1_thread.start()

    # Wait for both threads to finish
    try:
        motor1_thread.join()
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
    

if __name__ == "__main__":
    try:
        start_motors()
    except KeyboardInterrupt:
        stop_motors()
        print('\nTesting has concluded')






