:Author: Sean Mailen
:Email: sean@mrpbike.com
:Date: 7/1/2025
:Revision: A-00
:License: Public Domain

= Project: Test System Drivetrain

Summary:  A drivetrain test system utilizing two Nema 34 stepper motors 
and a pivoting rear center test structure.  Motor 1 drives the crankset while Motor 2 is heavily imbalanced to provide large displacement
oscillations.  A raspberry Pi is used to run the entire system.  The pi drives motor 1 via GPIO pins because timing doesn't need to be as 
precise while an Adafruit Feather ESP32 with much higher timing requirements drives Motor 2.  

Also see the Drivetrain_Tester_Design.xlsx in the Engineering Folder / Projects

== Step 1: Installation
The Python Code "Test_System_Motor_Control.py" is the main program to interact with the drivetrain Tester
The Python program is run directly on the Raspberry Pi and you can hook up a monitor and mouse and run it directly or run it 
headless using VSC to ssh shell into Raspberry Pi 4 B headless to interact and run code

# Using VSC to ssh shell into Raspberry Pi 4 B headless to interact and run code
# ssh 192.168.1.134 ip of Raspberry Pi
# typical is mailman@SeanPi.local
# Password currently:  MRP! 

The Arduino is hooked up to the Raspberry Pi via a serial connection / USB
You do not need to interact with the Arduino unless the code needs to be updated
If you do need to update the code it runs the "Arduino_Motor_2_Control" and you must directly connect to the controlboard via USB and typically Arduino IDE to program

"Drivetrain_setup_program.py" is a program to do troubleshooting since its a simple program to run motors and check software and hardware 

== Step 2: Assemble the circuit

Motor 1 or 2 is wired to Driver and Power supply, they each have individual units
Motor 1 setup (Drivetrain):
Nema 34, 1.8 deg (200 steps), 12 Nm, 6 A
DM860T Stepper Driver
Settings:  7.2A Peak, 6A Ref / 400 Pulse/Rev 
400 Pulses per rev
microstep 2, steps/rev 400
2.4 A, 2.0 a
Idle current - off 
Control mode - on
smoothing - off 


Motor 2 setup:
Nema 34, 1.8 deg (200 steps), 12 Nm, 6 A
DM860T Stepper Driver
Settings:  7.2A Peak, 6A Ref / 400 Pulse/Rev 
400 Pulses per rev
microstep 2, steps/rev 400
2.4 A, 2.0 a
Idle current - off 
Control mode - on
smoothing - off

# Pin configuration for motor 1 - Drivetrain
Hooked up to raspberry pi
DIR1 = 27   # Direction pin for motor 1
STEP1 = 22  # Step pin for motor 1

# Pin configuration for motor 2 - Oscillator
# Hooked up to Adafruit Feather ESP32
Hooked up via raspberry pi USB to feather serial micro
From feather to stepper Driver
#define STEP_PIN 6
#define DIR_PIN 5

All ground wires from motors, microcontrollers, stepper controllers, and power units wired together to reduce noise

== Step 3: Load the code

Code is on Raspberry Pi /Test System Drivetrain
- ssh into Raspberry Pi and run Python Code in chosen programmer, my choice is VSC.  Or use monitor and mouse and open Python Code file to run

The program uses start_motors() to run each motors thread in parellel.  
Motor 1 Runs through a pedaling cycle in the program called "Drivetrain_Cycle():"
This program runs for a full 32 seconds.  

Motor 2 runs through its Motor2_sequence() 1x times.

Motor1_sequence() is called to run 9 cycles and is timed with Motor2_sequence() timing but they do not call on each or are programmed to work together.  I just 
matched timing of each manually to each other.  

Log files are created for each run to track how many cycles it went, total run time, error codes etc.  These results are saved each time in the "Results" folder.  Unless
you update the name then if you do multiple runs it will just save all data to the same file but will not overwrite so it can be retreived.  

=== Folder structure
....
 Test System Drivetrain   => Python Folder
  ├── Test System Motor Control.py
  |-- Drivetrain_setup_program.py
  |-- Results
  |-- Results - Archive
  |-- Arduino_Motor_2_Control (hosted here but does not run here, on ESP32 microcontroller)
  └── ReadMe.adoc         => this file
....

=== License
No license

=== BOM
See Test Systen Drivetrain .xlsx


=== Help

