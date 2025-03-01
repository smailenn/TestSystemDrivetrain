import gpiozero as GPIO
from gpiozero import DigitalOutputDevice
import time
import threading
import tkinter as tk 
import sys
import os

# Test System Drivetrain Motor control
# Look at test system drivetrain.xlsx in Engineering Project folder for more information including motion analysis and variables
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

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    print("Starting Motor 1 sequence...")
    #slow start
    print("Soft Start Cycle")
    move_motor(dir1, step1, 10, 5, True)   # Motor 1 forward
    move_motor(dir1, step1, 30, 5, True)   # Motor 1 forward
    move_motor(dir1, step1, 70, 5, True)   # Motor 1 forward
    # "pedaling" cycling start
    print("Running Pedaling Cycle")
    move_motor(dir1, step1, 80, 10, True)   # Motor 1 forward
    time.sleep(0.7)                           # Pause
    move_motor(dir1, step1, 160, 0.5, False)  # Motor 1 backward, backpedal
    move_motor(dir1, step1, 125, 3, True)   # Motor 1 forward    
    move_motor(dir1, step1, 85, 10, True)   # Motor 1 forward
    move_motor(dir1, step1, 100, 6, True)   # Motor 1 forward
    time.sleep(1.6)                         # Pause
    move_motor(dir1, step1, 90, 4, False)   # Motor 1 backward, backpedal
    move_motor(dir1, step1, 80, 10, True)   # Motor 1 forward

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    print("Starting Motor 2 sequence...")
    move_motor(dir2, step2, 180, 40, True)  # Motor 2 forward
    #move_motor(dir2, step2, 300, 30, True)  # Motor 2 forward


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





