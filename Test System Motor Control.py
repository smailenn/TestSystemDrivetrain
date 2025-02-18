import gpiozero as GPIO
import time

# Pin configuration for motor 1 - Drivetrain
DIR1 = 27   # Direction pin for motor 1
STEP1 = 22  # Step pin for motor 1

# Pin configuration for motor 2 - Vibration
DIR2 = 24   # Direction pin for motor 2
STEP2 = 23  # Step pin for motor 2

# Motor parameters
# Nema 34, 1.8 deg (200 steps), 12 Nm, 6 A
# DM860T Stepper Driver
# Settings:  7.2A Peak, 6A Ref / 400 Pulse/Rev 
Pulses_rev = 400 #Pulses per revolution, set on driver

# Setup GPIO
dir1 = GPIO.OutputDevice(DIR1)
step1 = GPIO.OutputDevice(STEP1)

dir2 = GPIO.OutputDevice(DIR2)
step2 = GPIO.OutputDevice(STEP2)


def move_motor(direction_pin, step_pin, STEP_DELAY, steps, direction):
    """
    Moves a stepper motor a specified number of steps.

    Args:
        direction_pin (OutputDevice): GPIO pin for direction control.
        step_pin (OutputDevice): GPIO pin for step control.
        STEP_DELAY (float): Delay between steps.
        steps (int): Number of steps to move.
        direction (bool): True for one direction, False for the other.
    """
    direction_pin.value = direction  # Set direction
    print(f"Direction set to {'HIGH' if direction else 'LOW'} on pin {direction_pin.pin}")

    for _ in range(steps):
        step_pin.on()
        time.sleep(STEP_DELAY)
        step_pin.off()
        time.sleep(STEP_DELAY)

while True:
    try:
        print("Get Ready!  Moving motors...")
        time.sleep(2)
        RPM = 60
        Run_time = 20 # seconds
        STEP_DELAY = 60 / (2 * Pulses_rev * RPM) # Delay between steps in seconds  (60 seconds / (Pulses/Rev * RPM))   
        steps = int(200 * RPM / 60 * Run_time) # Calculated Steps

        print(f"STEP_DELAY: {STEP_DELAY}, Steps: {steps}")
        
        move_motor(dir1, step1, STEP_DELAY, steps, True)  # Motor 1 forward
        
        #move_motor(DIR2, STEP2, STEP_DELAY, steps, False)  # Motor 2 backward

        # Example: Move both motors together
        # for _ in range(200):
        #     GPIO.output(STEP1, GPIO.HIGH)
        #     GPIO.output(STEP2, GPIO.HIGH)
        #     time.sleep(STEP_DELAY)
        #     GPIO.output(STEP1, GPIO.LOW)
        #     GPIO.output(STEP2, GPIO.LOW)
        #     time.sleep(STEP_DELAY)

    except KeyboardInterrupt:
        print("\nOperation stopped by user.")
    break


#if __name__ == "__main__":
#    main()
