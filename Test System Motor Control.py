import gpiozero as GPIO
import time
import threading
from tkinter import Tk, Button

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
run_flag = False 

# Function for motor movement
def move_motor(direction_pin, step_pin, RPM, Run_time, direction):
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
    STEP_DELAY = 60 / (2 * Pulses_rev * RPM) # Delay between steps in seconds  (60 seconds / (Pulses/Rev * RPM))   
    steps = int(Pulses_rev * RPM / 60 * Run_time) # Calculated Steps

    print(f"STEP_DELAY: {STEP_DELAY}, Steps: {steps}, RPM: {RPM}, Run_time: {Run_time}")    
    #print(f"Direction set to {'HIGH' if direction else 'LOW'} on pin {direction_pin.pin}")

    for _ in range(steps):
        step_pin.on()
        time.sleep(STEP_DELAY)
        step_pin.off()
        time.sleep(STEP_DELAY)

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    global run_flag
    print("Starting Motor 1 sequence...")
    move_motor(dir1, step1, 90, 10, True)   # Motor 1 forward
    time.sleep(1)                           # Pause
    move_motor(dir1, step1, 160, 0.5, False)  # Motor 1 backward, backpedal
    move_motor(dir1, step1, 105, 4, True)   # Motor 1 forward    
    move_motor(dir1, step1, 85, 10, True)   # Motor 1 forward
    move_motor(dir1, step1, 100, 6, True)   # Motor 1 forward
    time.sleep(1.6)                         # Pause
    move_motor(dir1, step1, 90, 4, False)   # Motor 1 backward, backpedal
    move_motor(dir1, step1, 80, 10, True)   # Motor 1 forward

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    global run_flag
    print("Starting Motor 2 sequence...")
    move_motor(dir2, step2, 180, 30, True)  # Motor 2 forward
    move_motor(dir2, step2, 300, 30, True)  # Motor 2 forward


#####################################################
try:
    print("Get Ready!  Moving motors in sequence...")
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
    motor1_thread.join()
    motor2_thread.join()
    
except KeyboardInterrupt:
    print("\Operation stopped by user.")

finally: 
    print("Testing has concluded")



