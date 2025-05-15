#define STEP_PIN 6
#define DIR_PIN 5

unsigned int pulsesPerRev = 400;  // Updated to 400 pulses per revolution
unsigned int rampStepsDefault = 400;
bool stopRequested = false;
unsigned long startMillis;  // For calculating elapsed time
unsigned int stepsCompleted = 0;  // Track the number of steps completed

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  while (!Serial);

  Serial.println("Waiting for pulsesPerRev...");
  while (Serial.available() == 0);
  pulsesPerRev = Serial.parseInt();
  Serial.print("Received pulsesPerRev: ");
  Serial.println(pulsesPerRev);
}

void loop() {
  if (Serial.available()) {
    if (Serial.peek() == 'S') {
      String cmd = Serial.readStringUntil('\n');
      if (cmd == "STOP") {
        stopRequested = true;
        Serial.println("STOP received. Interrupting motion...");
        return;
      }
    }

    float startRPM = Serial.parseFloat();
    float targetRPM = Serial.parseFloat();
    float runTimeSec = Serial.parseFloat();
    int direction = Serial.parseInt();
    int rampSteps = rampStepsDefault;

    if (Serial.peek() != '\n' && Serial.available()) {
      rampSteps = Serial.parseInt();
    }

    while (Serial.available() && Serial.read() != '\n');

    if (startRPM < 0.1) startRPM = 0.1;
    if (targetRPM < 0.1) targetRPM = 0.1;

    // Print received parameters
    Serial.print("Start RPM: ");
    Serial.println(startRPM);
    Serial.print("Target RPM: ");
    Serial.println(targetRPM);
    Serial.print("Run Time (s): ");
    Serial.println(runTimeSec);
    Serial.print("Direction: ");
    Serial.println(direction);

    Serial.println("Executing motion...");
    digitalWrite(LED_BUILTIN, HIGH);
    stopRequested = false;
    stepsCompleted = 0;  // Reset steps counter
    startMillis = millis();  // Start the timer
    moveMotor(startRPM, targetRPM, runTimeSec, direction, rampSteps);
    digitalWrite(LED_BUILTIN, LOW);
  }
}

void moveMotor(float startRPM, float targetRPM, float runTime, int direction, int rampSteps) {
  digitalWrite(DIR_PIN, direction);
  int totalSteps = (int)(pulsesPerRev * (targetRPM / 60.0) * runTime);

  // Print total steps
  Serial.print("Total steps: ");
  Serial.println(totalSteps);

  if (rampSteps * 2 > totalSteps) rampSteps = totalSteps / 2;
  int cruiseSteps = totalSteps - 2 * rampSteps;

  // Calculate start and target delays
  float startDelay = 60.0 / (startRPM * pulsesPerRev * 2.0);
  float targetDelay = 60.0 / (targetRPM * pulsesPerRev * 2.0);

  // Print start and target delays
  Serial.print("Start delay: ");
  Serial.println(startDelay, 6);
  Serial.print("Target delay: ");
  Serial.println(targetDelay, 6);

  // Check if we're ramping or staying constant
  if (startRPM < targetRPM) {
    // Ramp-up
    Serial.println("Ramping up...");
    for (int i = 0; i < rampSteps && !stopRequested; i++) {
      float progress = (float)i / rampSteps;
      float delayMicros = interpolateSine(progress, startDelay, targetDelay) * 1e6;
      stepPulse(delayMicros);
      stepsCompleted++;
      printRealTimeRPM();
      checkForStop();
    }
  } else if (startRPM > targetRPM) {
    // Ramp-down
    Serial.println("Ramping down...");
    for (int i = 0; i < rampSteps && !stopRequested; i++) {
      float progress = (float)i / rampSteps;
      float delayMicros = interpolateSine(progress, targetDelay, startDelay) * 1e6;
      stepPulse(delayMicros);
      stepsCompleted++;
      printRealTimeRPM();
      checkForStop();
    }
  }

  // Cruise (constant speed)
  if (!stopRequested) {
    for (int i = 0; i < cruiseSteps && !stopRequested; i++) {
      stepPulse(targetDelay * 1e6);
      stepsCompleted++;
      printRealTimeRPM();
      checkForStop();
    }
  }

  // Ramp-down (if we're not already ramping down)
  if (startRPM > targetRPM && !stopRequested) {
    for (int i = 0; i < rampSteps && !stopRequested; i++) {
      float progress = (float)i / rampSteps;
      float delayMicros = interpolateSine(progress, targetDelay, startDelay) * 1e6;
      stepPulse(delayMicros);
      stepsCompleted++;
      printRealTimeRPM();
      checkForStop();
    }
  }
  Serial.println("DONE");
}

float interpolateSine(float t, float startDelay, float endDelay) {
  return startDelay - (startDelay - endDelay) * sin(t * (PI / 2));
}

void stepPulse(float delayMicros) {
  digitalWrite(STEP_PIN, HIGH);
  delayMicroseconds((int)delayMicros);
  digitalWrite(STEP_PIN, LOW);
  delayMicroseconds((int)delayMicros);
}

void checkForStop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    if (cmd == "STOP") {
      stopRequested = true;
      Serial.println("Emergency STOP triggered.");
    }
  }
}

void printRealTimeRPM() {
  unsigned long elapsedMillis = millis() - startMillis;  // Elapsed time in milliseconds
  float elapsedSeconds = elapsedMillis / 1000.0;
  float currentRPM = (stepsCompleted / pulsesPerRev) / elapsedSeconds * 60.0;  // Real-time RPM

  Serial.print("Real-Time RPM: ");
  Serial.println(currentRPM, 2);  // Print with 2 decimal places
}
