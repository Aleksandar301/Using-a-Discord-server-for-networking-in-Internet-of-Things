# Discord Bot API Commands

The value to be written is inside of the parentheses `()`. All commands are called with the `%` prefix.

| Command | Description |
|---------|-------------|
| `%ping` | Check the latency of the Discord bot |
| `%plot` | Plot the last `MAX_MEASUREMENTS` distance measurements |
| `%hist` | Show a histogram of the last `MAX_MEASUREMENTS` measurements |
| `%set_warning_threshold (int)` | Set the max distance value for printing warnings |
| `%send_ultrasonic` | Tell the ESP8266 to start sending ultrasonic distance sensor data |
| `%stop_ultrasonic` | Tell the ESP8266 to stop sending ultrasonic distance sensor data |
| `%send_pir` | Tell the ESP8266 to start sending passive IR sensor data |
| `%stop_pir` | Tell the ESP8266 to stop sending passive IR sensor data |
| `%allow_user_warning` | Allow the bot to send direct warning messages to all server members |
| `%disallow_user_warning` | Disallow the bot from sending direct warning messages |
| `%led_on` | Turn on the LED diode D0 |
| `%led_off` | Turn off the LED diode D0 |
