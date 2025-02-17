import RPi.GPIO as GPIO
import time

# Pin configuration for motor 1 - Drivetrain
DIR1 = 27   # Direction pin for motor 1
STEP1 = 17  # Step pin for motor 1

# Pin configuration for motor 2 - Vibration
DIR2 = 24   # Direction pin for motor 2
STEP2 = 23  # Step pin for motor 2

# Motor parameters
# Nema 34, 1.8 deg (200 steps), 12 Nm, 6 A
# DM860T Stepper Driver
# Settings:  7.2A Peak, 6A Ref / 400 Pulse/Rev 

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(DIR1, GPIO.OUT)
GPIO.setup(STEP1, GPIO.OUT)
GPIO.setup(DIR2, GPIO.OUT)
GPIO.setup(STEP2, GPIO.OUT)

def move_motor(direction_pin, step_pin, STEP_DELAY, steps, direction):
    """
    Moves a stepper motor a specified number of steps.

    Args:
        direction_pin (int): GPIO pin for direction control.
        step_pin (int): GPIO pin for step control.
        STEP_DELAY (int): Delay between steps
        steps (int): Number of steps to move.
        direction (bool): True for one direction, False for the other.
    """
    GPIO.output(direction_pin, GPIO.HIGH if direction else GPIO.LOW)
    for _ in range(steps):
        GPIO.output(step_pin, GPIO.HIGH)
        time.sleep(STEP_DELAY)
        GPIO.output(step_pin, GPIO.LOW)
        time.sleep(STEP_DELAY)

#def main():
#    try:
        # Example: Move motor 1 forward 200 steps and motor 2 backward 200 steps

while True:
    try:
        print("Get Ready!  Moving motors...")
        #time.sleep(5)
        RPM = 90
        Run_time = 30 # seconds
        STEP_DELAY = 1/(RPM / 60 * 200)
        steps = 200 * 90 / 60 * Run_time
        #STEP_DELAY = 0.001  # Delay between steps (adjust for speed)
        move_motor(DIR1, STEP1, STEP_DELAY, steps, True)  # Motor 1 forward


        move_motor(DIR2, STEP2, STEP_DELAY, steps, False)  # Motor 2 backward

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
    finally:
        GPIO.cleanup()

#if __name__ == "__main__":
#    main()
