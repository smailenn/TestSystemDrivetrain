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
Pulses_rev = 400 #Pulses per revolution, set on driver

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
def move_motor(direction_pin, step_pin, RPM, Run_time, direction):
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

    STEP_DELAY = 60 / (2 * Pulses_rev * RPM) # Delay between steps in seconds  (60 seconds / (Pulses/Rev * RPM))   
    steps = int(Pulses_rev * RPM / 60 * Run_time) # Calculated Steps

    print(f"Motor: {Motor_ID}, RPM: {RPM}, Run_time: {Run_time}")  
    #print(f"Motor: {Motor_ID}, STEP_DELAY: {STEP_DELAY}, Steps: {steps}, RPM: {RPM}, Run_time: {Run_time}")    
   
    for _ in range(steps):
        if not run_flag: # Stop if flag is set
            print(f"Stopping {Motor_ID}")
            return
        step_pin.on()
        time.sleep(STEP_DELAY)
        step_pin.off()
        time.sleep(STEP_DELAY)

# Function for motor movement with slow ramp for motor control
def interpolate_delay_sine(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * math.sin(progress * (math.pi / 2))

# Function for motor movement with Ramp-Up and Constant Speed
def move_motor_with_ramp_up(direction_pin, step_pin, RPM, Run_time, direction, ramp_steps=100):
    global run_flag

    direction_pin.value = direction
    Motor_ID = "Motor 1" if direction_pin == dir1 else "Motor 2"

    full_delay = 60 / (2 * Pulses_rev * RPM)
    total_steps = int(Pulses_rev * RPM / 60 * Run_time)

    if ramp_steps > total_steps:
        ramp_steps = total_steps

    print(f"{Motor_ID} w/ RAMP-UP: RPM={RPM}, Time={Run_time}, Steps={total_steps}")

    for step in range(total_steps):
        if not run_flag:
            print(f"Stopping {Motor_ID}")
            return

        if step < ramp_steps:  # Ramp-up phase
            progress = step / ramp_steps
            delay = interpolate_delay_sine(progress, full_delay * 2, full_delay)
        else:  # Constant speed phase
            delay = full_delay

        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

# Function for motor movement with Ramp-Down
def move_motor_with_ramp_down(direction_pin, step_pin, RPM, steps, direction, ramp_steps=100):
    global run_flag

    direction_pin.value = direction
    Motor_ID = "Motor 1" if direction_pin == dir1 else "Motor 2"

    full_delay = 60 / (2 * Pulses_rev * RPM)

    if ramp_steps > steps:
        ramp_steps = steps

    print(f"{Motor_ID} w/ RAMP-DOWN: RPM={RPM}, Steps={steps}")

    for step in range(steps):
        if not run_flag:
            print(f"Stopping {Motor_ID}")
            return

        if step >= steps - ramp_steps:  # Ramp-down phase
            progress = (step - (steps - ramp_steps)) / ramp_steps
            delay = interpolate_delay_sine(1 - progress, full_delay * 2, full_delay)
        else:  # Constant speed phase
            delay = full_delay

        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    print("Starting Motor 1 sequence...")
    print("Running Pedaling Cycle")
    move_motor_with_ramp_up(dir1, step1, 80, 2, True, ramp_steps=100)   # Motor 1 forward
    move_motor(dir1, step1, 120, 1, True)   # Motor 1 forward
    time.sleep(0.5)
    move_motor(dir1, step1, 160, 1, False)  # Motor 1 backward, backpedal
    move_motor(dir1, step1, 100, 3, True)   # Motor 1 forward
    time.sleep(2)                           # Pause
    move_motor(dir1, step1, 120, 1, False)  # Motor 1 backward, backpedal
    move_motor_with_ramp_up(dir1, step1, 125, 3, True, ramp_steps=200)   # Motor 1 forward 
    move_motor(dir1, step1, 120, 3, False)  # Motor 1 backward, backpedal   
    move_motor(dir1, step1, 85, 2, True)   # Motor 1 forward
    move_motor(dir1, step1, 120, 2, False)  # Motor 1 backward, backpedal
    move_motor(dir1, step1, 100, 3, True)   # Motor 1 forward
    move_motor(dir1, step1, 120, 2, False)  # Motor 1 backward, backpedal
    time.sleep(0.5)                         # Pause
    move_motor(dir1, step1, 100, 1, False)   # Motor 1 backward, backpedal
    move_motor(dir1, step1, 110, 2, True)   # Motor 1 forward

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    print("Starting Motor 2 sequence with ramp...")
    #move_motor_with_ramp_up(dir2, step2, 50, 5, True, ramp_steps=1000) 
    #move_motor_with_ramp_up(dir2, step2, 100, 10, True, ramp_steps=1000)
    #move_motor_with_ramp_up(dir2, step2, 160, 10, True, ramp_steps=1400)
    #move_motor_with_ramp_up(dir2, step2, 200, 10, True, ramp_steps=1400)  # Motor 2 forward
    #move_motor_with_ramp_up(dir2, step2, 220, 10, True, ramp_steps=1400)  # Motor 2 forward
    move_motor_with_ramp_up(dir2, step2, 200, 40, True, ramp_steps=20000)  # Motor 2 backward
    #move_motor_with_ramp_up(dir2, step2, 260, 15, True, ramp_steps=400)
    #move_motor(dir2, step2, 260, 5, True)
    time.sleep(1)
    move_motor_with_ramp_down(dir2, step2, 220, 15, True, ramp_steps=10000)
    
    
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

    # Start Motor 2 Oscillator in its own thread
    motor2_thread = threading.Thread(target=Motor2_sequence)

    # Start Motor 1 Drivetrain in its own thread
    motor1_thread = threading.Thread(target=Motor1_sequence)

    # Start them
    motor2_thread.start()
    motor1_thread.start()

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
    

if __name__ == "__main__":
    try:
        start_motors()
    except KeyboardInterrupt:
        stop_motors()
        print('\nTesting has concluded')

# Create Tkinter GUI
#root = tk.Tk()
#root.title("Motor Controller")

# start_button = tk.Button(root, text="Start", command=start_motors, height=2, width=10, bg="green", fg="white")
# start_button.pack(pady=10)

# stop_button = tk.Button(root, text="Stop", command=stop_motors, height=2, width=10, bg="red", fg="white")
# stop_button.pack(pady=10)

# Run Tkinter event loop
# root.mainloop()





