#define STEP_PIN 3
#define DIR_PIN 4

unsigned int pulsesPerRev = 800;  // Will be set via serial
unsigned int rampStepsDefault = 100;

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  Serial.begin(115200);
  while (!Serial);

  Serial.println("Waiting for pulsesPerRev...");
  while (Serial.available() == 0);
  pulsesPerRev = Serial.parseInt();
  Serial.print("Received pulsesPerRev: ");
  Serial.println(pulsesPerRev);
}

void loop() {
  if (Serial.available() > 0) {
    float startRPM = Serial.parseFloat();
    float targetRPM = Serial.parseFloat();
    float runTimeSec = Serial.parseFloat();
    int direction = Serial.parseInt();
    int rampSteps = rampStepsDefault;

    // Optional ramp steps
    if (Serial.peek() != '\n' && Serial.available()) {
      rampSteps = Serial.parseInt();
    }

    // Wait for line end
    while (Serial.available() && Serial.read() != '\n');

    Serial.println("Executing motion...");
    moveMotor(startRPM, targetRPM, runTimeSec, direction, rampSteps);
    Serial.println("Done.");
  }
}

void moveMotor(float startRPM, float targetRPM, float runTime, int direction, int rampSteps) {
  digitalWrite(DIR_PIN, direction);
  int totalSteps = (int)(pulsesPerRev * (targetRPM / 60.0) * runTime);

  if (rampSteps * 2 > totalSteps) rampSteps = totalSteps / 2;
  int cruiseSteps = totalSteps - 2 * rampSteps;

  float startDelay = 60.0 / (startRPM * pulsesPerRev * 2.0);
  float targetDelay = 60.0 / (targetRPM * pulsesPerRev * 2.0);

  // Ramp up
  for (int i = 0; i < rampSteps; i++) {
    float progress = (float)i / rampSteps;
    float delayMicros = interpolateSine(progress, startDelay, targetDelay) * 1e6;
    stepPulse(delayMicros);
  }

  // Cruise
  for (int i = 0; i < cruiseSteps; i++) {
    stepPulse(targetDelay * 1e6);
  }

  // Ramp down
  for (int i = 0; i < rampSteps; i++) {
    float progress = (float)i / rampSteps;
    float delayMicros = interpolateSine(progress, targetDelay, startDelay) * 1e6;
    stepPulse(delayMicros);
  }
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
