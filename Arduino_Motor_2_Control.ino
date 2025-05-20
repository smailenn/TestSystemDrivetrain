#define STEP_PIN 6
#define DIR_PIN 5

const byte QUEUE_SIZE = 400;

struct MotionCommand {
  float startRPM;     // Note: overridden internally for smooth transitions
  float targetRPM;
  float runTimeSec;
  int direction;
  int rampSteps;
};

MotionCommand commandQueue[QUEUE_SIZE];
int queueHead = 0;
int queueTail = 0;
bool commandInProgress = false;
MotionCommand currentCommand;

unsigned int pulsesPerRev = 400;
unsigned int rampStepsDefault = 400;
bool stopRequested = false;
unsigned long startMillis;
unsigned int stepsCompleted = 0;

float currentRPM = 0;  // Track current motor RPM

float safeRPM(float rpm) {
  return (rpm < 5.0) ? 5.0 : rpm;  // Prevent too slow speeds
}

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  while (!Serial);

// Clear serial buffer
  while (Serial.available()) {
    Serial.read();
  }

  Serial.println("Waiting for pulsesPerRev...");
  while (Serial.available() == 0);
  pulsesPerRev = Serial.parseInt();
  Serial.print("Received pulsesPerRev: ");
  Serial.println(pulsesPerRev);

  currentRPM = 0;
}

void loop() {
  readSerialCommands();

  if (stopRequested) {
    if (currentRPM > 0) {
      Serial.println("Emergency stop: ramping motor down.");
      stopMotor();
      currentRPM = 0;
    }
    digitalWrite(LED_BUILTIN, LOW);
    return;  // no further commands
  }

  if (!commandInProgress && !isQueueEmpty()) {
    currentCommand = dequeue();
    stepsCompleted = 0;
    startMillis = millis();
    digitalWrite(LED_BUILTIN, HIGH);
    commandInProgress = true;

    Serial.print("Starting move: startRPM=");
    Serial.print(currentRPM);
    Serial.print(", targetRPM=");
    Serial.print(currentCommand.targetRPM);
    Serial.print(", runTime=");
    Serial.print(currentCommand.runTimeSec);
    Serial.print(", direction=");
    Serial.println(currentCommand.direction);

    moveMotor(currentRPM, currentCommand.targetRPM, currentCommand.runTimeSec, currentCommand.direction, currentCommand.rampSteps);
    currentRPM = currentCommand.targetRPM;

    digitalWrite(LED_BUILTIN, LOW);
    commandInProgress = false;
    Serial.println("Command finished.");

    // Automatically ramp down if no more commands left and motor is running
    if (isQueueEmpty() && currentRPM > 0) {
      Serial.println("No more commands. Ramping motor down smoothly.");
      stopMotor();
      currentRPM = 0;
    }
  }
}

void readSerialCommands() {
  static String inputBuffer = "";

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        Serial.print("Received line: '");
        Serial.print(inputBuffer);
        Serial.println("'");

        if (inputBuffer.startsWith("STOP")) {
          stopRequested = true;
          clearQueue();
          Serial.println("STOP received: queue cleared, stopping all motion.");

        } else if (inputBuffer.startsWith("RESET")) {
          stopRequested = false;
          clearQueue();
          currentRPM = 0;
          Serial.println("RESET received: system reset.");

        } else if (inputBuffer.startsWith("PPR:")) {
          pulsesPerRev = inputBuffer.substring(4).toInt();
          Serial.print("Updated pulsesPerRev to: ");
          Serial.println(pulsesPerRev);

        } else if (inputBuffer.startsWith("BATCH:")) {
          String batchData = inputBuffer.substring(6);
          parseBatchCommands(batchData);

        } else {
          parseAndEnqueueCommand(inputBuffer);
        }
      }
      inputBuffer = "";  // clear buffer for next line
    } else {
      inputBuffer += c;
    }
  }
}


void parseBatchCommands(String batchData) {
  int startIndex = 0;
  while (startIndex < batchData.length()) {
    int sepIndex = batchData.indexOf(';', startIndex);
    String cmd;
    if (sepIndex == -1) {
      cmd = batchData.substring(startIndex);
      startIndex = batchData.length();
    } else {
      cmd = batchData.substring(startIndex, sepIndex);
      startIndex = sepIndex + 1;
    }
    cmd.trim();
    if (cmd.length() > 0) {
      parseAndEnqueueCommand(cmd);
    }
  }
  Serial.println("Batch commands enqueued.");
}

void parseAndEnqueueCommand(String cmd) {
  float startRPM = 0, targetRPM = 0, runTimeSec = 0;
  int direction = 0;
  int rampSteps = rampStepsDefault;

  int index1 = cmd.indexOf(',');
  int index2 = cmd.indexOf(',', index1 + 1);
  int index3 = cmd.indexOf(',', index2 + 1);

  if (index1 == -1 || index2 == -1 || index3 == -1) {
  Serial.println("ERR: Invalid command format");
  while (Serial.available()) Serial.read(); // Clear junk
  return;
  }

  int index4 = cmd.indexOf(',', index3 + 1);

  startRPM = cmd.substring(0, index1).toFloat();
  targetRPM = cmd.substring(index1 + 1, index2).toFloat();
  runTimeSec = cmd.substring(index2 + 1, index3).toFloat();
  direction = cmd.substring(index3 + 1, (index4 == -1) ? cmd.length() : index4).toInt();

  if (index4 != -1) {
    rampSteps = cmd.substring(index4 + 1).toInt();
  }

  MotionCommand newCmd = {startRPM, targetRPM, runTimeSec, direction, rampSteps};
  enqueue(newCmd);
}

void enqueue(MotionCommand cmd) {
  int nextTail = (queueTail + 1) % QUEUE_SIZE;
  if (nextTail == queueHead) {
    Serial.println("Command queue full, discarding command.");
    return;
  }
  commandQueue[queueTail] = cmd;
  queueTail = nextTail;
}

MotionCommand dequeue() {
  MotionCommand cmd = commandQueue[queueHead];
  queueHead = (queueHead + 1) % QUEUE_SIZE;
  return cmd;
}

bool isQueueEmpty() {
  return queueHead == queueTail;
}

void clearQueue() {
  queueHead = 0;
  queueTail = 0;
}

// Move motor from startRPM to targetRPM, cruise, then ramp down to startRPM
void moveMotor(float startRPM, float targetRPM, float runTimeSec, int direction, int rampSteps) {
  digitalWrite(DIR_PIN, direction);

  int totalSteps = (int)(pulsesPerRev * (targetRPM / 60.0) * runTimeSec);

  float rpmDelta = abs(targetRPM - startRPM);
  if (rpmDelta > 50 && rampSteps < 400) rampSteps = 400;

  int cruiseSteps = totalSteps - 2 * rampSteps;
  if (cruiseSteps < 0) cruiseSteps = 0;  // prevent negative cruise steps

  float startDelay = 60.0 / (safeRPM(startRPM) * pulsesPerRev * 2.0);
  float targetDelay = 60.0 / (safeRPM(targetRPM) * pulsesPerRev * 2.0);

  // Ramp UP
  for (int i = 0; i < rampSteps && !stopRequested; i++) {
    float progress = (float)i / rampSteps;
    float delayMicros = interpolateSine(progress, startDelay, targetDelay) * 1e6;
    stepPulse(delayMicros);
    stepsCompleted++;
    checkForStop();
  }

  // Cruise
  for (int i = 0; i < cruiseSteps && !stopRequested; i++) {
    stepPulse(targetDelay * 1e6);
    stepsCompleted++;
    checkForStop();
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

void checkForStop() {
  if (Serial.available()) {
    if (Serial.peek() == 'S') {
      String cmd = Serial.readStringUntil('\n');
      if (cmd == "STOP") {
        stopRequested = true;
        Serial.println("Emergency STOP triggered.");
      }
    }
  }
}

// Smoothly ramp motor down from currentRPM to zero
void stopMotor() {
  Serial.print("Stopping motor from RPM ");
  Serial.println(currentRPM);

  digitalWrite(DIR_PIN, 1);  // Direction can stay same or be neutral, your choice

  int rampSteps = rampStepsDefault;

  float startDelay = 60.0 / (safeRPM(currentRPM) * pulsesPerRev * 2.0);
  float endDelay = 60.0 / (safeRPM(0.0 + 5.0) * pulsesPerRev * 2.0);  // use safe minimum RPM of 5 to avoid divide by zero

  for (int i = 0; i < rampSteps && !stopRequested; i++) {
    float progress = (float)i / rampSteps;
    float delayMicros = interpolateSine(progress, startDelay, endDelay) * 1e6;
    stepPulse(delayMicros);
  }

  Serial.println("Motor stopped smoothly.");
}
