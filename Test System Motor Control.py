import pigpio
import time
import threading
import math
import sys

pi = pigpio.pi()

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
Pulses_rev = 400 #Pulses per revolution, set on driver

if not pi.connected:
    print("Failed to connect to pigpio daemon. Make sure it's running.")
    sys.exit(1)

# Pin configuration for motor 1 - Drivetrain
DIR1 = 27   # Direction pin for motor 1
STEP1 = 22  # Step pin for motor 1

# Pin configuration for motor 2 - Oscillation
DIR2 = 24   # Direction pin for motor 2
STEP2 = 23  # Step pin for motor 2

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

            print(f"Generated {len(pulses)} pulses.")
            pi.wave_add_generic(pulses)
            wave_id = pi.wave_create()
            if wave_id < 0:
                print("Failed to create waveform")
                return
            else:
                print(f"Created waveform with ID {wave_id}")

            print(f"Sending waveform with ID {wave_id}")
            
            if wave_id == 0:
                print("Warning: Wave ID is 0, which may indicate an issue with waveform creation.")

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

    print(f"{Motor_ID}: {start_RPM}->{target_RPM} RPM, {run_time}s, {total_steps} steps")

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


# Function for Motor 1 Drivetrain Movement
def Motor1_sequence():
    print("Starting Motor 1 sequence...")
    print("Running Pedaling Cycle")
    move_motor_with_ramp(DIR1, STEP1, 5, 80, 2, True)
    move_motor_with_ramp(DIR1, STEP1, 80, 120, 1, True)
    time.sleep(0.5)
    move_motor_with_ramp(DIR1, STEP1, 120, 160, 2, False)
    move_motor_with_ramp(DIR1, STEP1, 120, 100, 2, True)
    time.sleep(1)
    move_motor_with_ramp(DIR1, STEP1, 100, 140, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 120, 125, 2, True)
    move_motor_with_ramp(DIR1, STEP1, 125, 130, 3, False)
    move_motor_with_ramp(DIR1, STEP1, 130, 85, 1, True)
    move_motor_with_ramp(DIR1, STEP1, 85, 130, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 130, 100, 2, True)
    move_motor_with_ramp(DIR1, STEP1, 100, 120, 1, False)
    time.sleep(0.5)
    move_motor_with_ramp(DIR1, STEP1, 120, 130, 1, False)
    move_motor_with_ramp(DIR1, STEP1, 130, 120, 2, True)   # Motor 1 forward

# Function for Motor 2 Oscillation Movement
def Motor2_sequence():
    print("Starting Motor 2 sequence with ramp...")
    move_motor_with_ramp(DIR2, STEP2, 5, 60, 10, True, ramp_steps=400)
    move_motor_with_ramp(DIR2, STEP2, 60, 60, 20, True, ramp_steps=400)
    move_motor_with_ramp(DIR2, STEP2, 60, 5, 7, True, ramp_steps=400)
    
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





