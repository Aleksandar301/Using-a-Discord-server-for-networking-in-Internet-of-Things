#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h> 

// WiFi parameters
const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";

// Creating the secure client object
WiFiClientSecure client;
HTTPClient http;

// Your Discord webhook URLs for sending messages
const char* discordWebhookURL1 = "YOUR_WEBHOOK_URL1";
const char* discordWebhookURL2 = "YOUR_WEBHOOK_URL2";

// Create a web server on port 80
ESP8266WebServer server(80);

// Ultrasonic distance sensor pins
const int trigPin = 12;
const int echoPin = 14;

// PIR sensor pin
const byte PIR_SENSOR_PIN = 4;

// Define LED pin
#define LED D0

// Variables to track PIR sensor state
bool motionDetected = false;
bool previousMotionDetected = false;

// Define sound velocity in cm/uS
#define SOUND_VELOCITY 0.034

// Duration between sending and acquiring
long duration;

// Measured distance
float distanceCm;

bool sendUltrasonic = false; // Variable to control ultrasonic data sending
bool sendPIR = false; // Variable to control PIR data sending

void setup() {
  // Initialize the trigPin, echoPin, and LED
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW); // Ensure LED is off initially

  Serial.begin(115200);
  delay(10);

  // Connect to Wi-Fi
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());

  // Allow time for the secure client to set up
  client.setInsecure(); // This is insecure, use only for testing purposes

  // Define the root handler and other handlers
  server.on("/", HTTP_GET, handleRoot);
  server.begin(); // Start the server
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient(); // Handle incoming client requests

  if (sendPIR) {
    checkPIRSensor(); // Check PIR sensor state
  }

  if (sendUltrasonic) {
    // Calculate the distance via ultrasonic sensor
    distanceCm = CalculateDistance();
    // Send distance to Discord webhook
    sendToDiscord(discordWebhookURL1, "Distance is " + String(distanceCm) + " cm");

    delay(3000); // Delay between measurements
  }
}

void sendToDiscord(const char* webhookURL, String message) {
  if (WiFi.status() == WL_CONNECTED) {
    http.begin(client, webhookURL); // Use http.begin directly with URL
    http.addHeader("Content-Type", "application/json");

    String payload = "{\"content\": \"" + message + "\"}";

    int httpResponseCode = http.POST(payload);

    if (httpResponseCode > 0) {
      String response = http.getString();
      // the code bellow is used for debuging purposes if needed
      //Serial.print("HTTP Response code: ");
      //Serial.println(httpResponseCode);
      //Serial.print("Response: ");
      //Serial.println(response);
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  } else {
    Serial.println("WiFi not connected");
  }
}

enum CommandType {
  CMD_SEND_ULTRASONIC,
  CMD_STOP_ULTRASONIC,
  CMD_SEND_PIR,
  CMD_STOP_PIR,
  CMD_LED_ON,
  CMD_LED_OFF,
  CMD_DATA_COLLECTED,
  CMD_INVALID
};

CommandType parseCommand(const String& command) {
  if (command == "send_ultrasonic") return CMD_SEND_ULTRASONIC;
  if (command == "stop_ultrasonic") return CMD_STOP_ULTRASONIC;
  if (command == "send_pir") return CMD_SEND_PIR;
  if (command == "stop_pir") return CMD_STOP_PIR;
  if (command == "led_on") return CMD_LED_ON;
  if (command == "led_off") return CMD_LED_OFF;
  if (command.startsWith("data_collected:")) return CMD_DATA_COLLECTED;

  return CMD_INVALID;
}

void handleRoot() {
  String command = server.arg("command");
  CommandType cmd = parseCommand(command);

  switch (cmd) {

    case CMD_SEND_ULTRASONIC:
      sendUltrasonic = true;
      server.send(200, "text/plain", "Ultrasonic sensor data sending started");
      Serial.println("Ultrasonic sensor data sending started");
      break;

    case CMD_STOP_ULTRASONIC:
      sendUltrasonic = false;
      server.send(200, "text/plain", "Ultrasonic sensor data sending stopped");
      Serial.println("Ultrasonic sensor data sending stopped");
      break;

    case CMD_SEND_PIR:
      sendPIR = true;
      server.send(200, "text/plain", "PIR sensor data sending started");
      Serial.println("PIR sensor data sending started");
      break;

    case CMD_STOP_PIR:
      sendPIR = false;
      server.send(200, "text/plain", "PIR sensor data sending stopped");
      Serial.println("PIR sensor data sending stopped");
      break;

    case CMD_LED_ON:
      digitalWrite(LED, HIGH);
      server.send(200, "text/plain", "LED is turned on");
      Serial.println("LED is turned on");
      break;

    case CMD_LED_OFF:
      digitalWrite(LED, LOW);
      server.send(200, "text/plain", "LED is turned off");
      Serial.println("LED is turned off");
      break;

    case CMD_DATA_COLLECTED: {
      String data = command.substring(15);
      Serial.print("Data collected: ");
      Serial.println(data);
      server.send(200, "text/plain", "Data collected received");
      break;
    }

    default:
      server.send(200, "text/plain", "Invalid command");
      break;
  }
}

float CalculateDistance() {
  // Clear the trigPin
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  // Set the trigPin on HIGH state for 10 micro seconds
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // Read the echoPin
  duration = pulseIn(echoPin, HIGH);

  // Calculate the distance
  distanceCm = duration * SOUND_VELOCITY / 2;

  return distanceCm;
}

void checkPIRSensor() {
  motionDetected = digitalRead(PIR_SENSOR_PIN); // Read PIR sensor
  delayMicroseconds(10);
  if (motionDetected != previousMotionDetected) {
    if (motionDetected) {
      sendToDiscord(discordWebhookURL2, "Motion detected!"); // Send message to Discord webhook
    }
    previousMotionDetected = motionDetected;
  }
}
