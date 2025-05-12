import gpiozero as GPIO
from gpiozero import DigitalOutputDevice
import pigpio
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

buffer_time = 0.000 # Add a small buffer to the delay

pi = pigpio.pi()
if not pi.connected:
    print("Failed to connect to pigpio daemon. Make sure it's running.")
    sys.exit(1)

# Setup GPIO
dir1 = GPIO.DigitalOutputDevice(DIR1)
step1 = GPIO.DigitalOutputDevice(STEP1)

dir2 = GPIO.DigitalOutputDevice(DIR2)
step2 = GPIO.DigitalOutputDevice(STEP2)

#threading
run = True

#Global flag for stopping motors
run_flag = True

# Function for motor movement with slow ramp for motor control
def interpolate_delay_sine(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * math.sin(progress * (math.pi / 2))

# Function for motor movement with linear ramp  
def interpolate_delay_linear(progress, start_delay, end_delay):
    return start_delay - (start_delay - end_delay) * progress

def generate_steps_with_pigpio(step_pin, num_steps, delay):
    # Extract the GPIO pin number if step_pin is a DigitalOutputDevice
    if isinstance(step_pin, GPIO.DigitalOutputDevice):
        step_pin = step_pin.pin.number

    if delay <= 0:
        raise ValueError(f"Invalid delay value: {delay}. Delay must be greater than 0.")
    
    pi.wave_clear()  # Clear existing waveforms

    # Create a waveform for the step pulses
    pulses = []
    for _ in range(num_steps):
        pulse_duration = int(delay * 1e6)
        if pulse_duration <= 0:
            raise ValueError(f"Invalid pulse duration: {pulse_duration}. Delay must result in a positive duration.")
        pulses.append(pigpio.pulse(1 << step_pin, 0, pulse_duration))  # High pulse
        pulses.append(pigpio.pulse(0, 1 << step_pin, pulse_duration))  # Low pulse

    if not pulses:
        raise ValueError("No pulses generated. Check the delay value.")

    pi.wave_add_generic(pulses)
    wave_id = pi.wave_create()

    if wave_id < 0:
        raise RuntimeError("Failed to create waveform. Check pigpio configuration.")


    # Send the waveform
    pi.wave_send_once(wave_id)
    while pi.wave_tx_busy():
        time.sleep(0.01)  # Wait for the waveform to finish
    pi.wave_clear()

# Function for motor movement
def move_motor(direction_pin, step_pin, target_RPM, Run_time, direction):
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
        
        generate_steps_with_pigpio(step_pin, 1, STEP_DELAY)

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

    MIN_DELAY = 0.00001  # Minimum delay to prevent too fast stepping

    for step in range(total_steps):
        if not run_flag:
            print(f"Stopping {Motor_ID}")
            return

        if step < ramp_steps:  # Ramp-up phase
            progress = step / ramp_steps
            #delay = interpolate_delay_linear(progress, current_delay, full_delay)
            delay = interpolate_delay_sine(progress, current_delay, full_delay)
        else:  # Constant speed phase
            delay = full_delay

        # Ensure delay is above the minimum threshold
        if delay < MIN_DELAY:
            delay = MIN_DELAY

        # Debugging output
        #print(f"Step {step}/{total_steps}, Delay: {delay:.6f}s")        

        #print(f"[{time.strftime('%H:%M:%S')}] Step {step}/{total_steps} | Delay: {delay:.6f}s")

        generate_steps_with_pigpio(step_pin, 1, delay)

# Function for motor movement with Ramp-Down
def move_motor_with_ramp_down(direction_pin, step_pin, current_RPM, target_RPM, Run_time, direction, ramp_steps=100):
    global run_flag

    direction_pin.value = direction
    Motor_ID = "Motor 1" if direction_pin == dir1 else "Motor 2"

    full_delay = 60 / (2 * Pulses_rev * target_RPM)
    current_delay = 60 / (2 * Pulses_rev * current_RPM)
    total_steps = int(Pulses_rev * current_RPM / 60 * Run_time)

    if ramp_steps > total_steps:
        ramp_steps = total_steps

    print(f"{Motor_ID} w/ RAMP-DOWN: Current RPM={current_RPM}, Target RPM={target_RPM}, Time={Run_time}, Steps={total_steps}")

    for step in range(total_steps):
        if not run_flag:
            print(f"Stopping {Motor_ID}")
            return

        if step < ramp_steps:  # Ramp-down phase
            progress = step / ramp_steps
            delay = interpolate_delay_sine(progress, current_delay, full_delay)
        else:  # Constant speed phase
            delay = full_delay

        #print(f"[{time.strftime('%H:%M:%S')}] Step {step}/{total_steps} | Delay: {delay:.6f}s")

        # Generate a single step with the calculated delay
        generate_steps_with_pigpio(step_pin, 1, delay)

# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    print("Starting Motor 1 sequence...")
    print("Running Pedaling Cycle")
    move_motor_with_ramp_up(dir1, step1, 5, 80, 2, True, ramp_steps=200)   # Motor 1 forward
    move_motor_with_ramp_up(dir1, step1, 80, 120, 1, True, ramp_steps=200)   # Motor 1 forward
    time.sleep(0.5)
    move_motor_with_ramp_down(dir1, step1, 120, 160, 2, False, ramp_steps=100)  # Motor 1 backward, backpedal
    move_motor_with_ramp_up(dir1, step1, 120, 100, 2, True, ramp_steps=100)   # Motor 1 forward
    time.sleep(1)                           # Pause
    move_motor_with_ramp_down(dir1, step1, 100, 140, 1, False, ramp_steps=100)  # Motor 1 backward, backpedal
    move_motor_with_ramp_up(dir1, step1, 120, 125, 2, True, ramp_steps=200)   # Motor 1 forward 
    move_motor_with_ramp_down(dir1, step1, 125, 130, 3, False, ramp_steps=100)  # Motor 1 backward, backpedal   
    move_motor_with_ramp_up(dir1, step1, 130, 85, 1, True, ramp_steps=100)   # Motor 1 forward
    move_motor_with_ramp_down(dir1, step1, 85, 130, 1, False, ramp_steps=100)  # Motor 1 backward, backpedal
    move_motor_with_ramp_up(dir1, step1, 130, 100, 2, True, ramp_steps=100)   # Motor 1 forward
    move_motor_with_ramp_down(dir1, step1, 100, 120, 1, False, ramp_steps=100)  # Motor 1 backward, backpedal
    time.sleep(0.5)                         # Pause
    move_motor_with_ramp_down(dir1, step1, 120, 130, 1, False, ramp_steps=100)   # Motor 1 backward, backpedal
    move_motor_with_ramp_up(dir1, step1, 130, 120, 2, True, ramp_steps=100)   # Motor 1 forward

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    print("Starting Motor 2 sequence with ramp...")
    move_motor_with_ramp_up(dir2, step2, 5, 160, 10, True, ramp_steps=200) 
    move_motor_with_ramp_up(dir2, step2, 160, 160, 20, True, ramp_steps=200)
    move_motor_with_ramp_down(dir2, step2, 160, 5, 7, True, ramp_steps=100)
    
    
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
    time.sleep(12)
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





