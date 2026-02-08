import discord
from discord.ext import commands, tasks
import requests
import matplotlib.pyplot as plt
import io
import numpy as np
from datetime import datetime, timedelta
import re

# Default settings for macros
MAX_MEASUREMENTS = 100
LOOP_SECONDS_D = 2
LOOP_SECONDS_PIR = 2.73
WARNING_THRESHOLD = 800
WARNING_INTERVAL_PIR = 5  # Time in seconds between consecutive warnings for PIR
WARNING_INTERVAL_DISTANCE = 4  # Time in seconds between consecutive warnings for ultrasonic

# Prefix for accessing the Discord bot command
client = commands.Bot(command_prefix="%", intents=discord.Intents.all())

# IP of the ESP8266
esp8266_ip = "YOUR_IP"  # Replace with the actual IP of your ESP8266

# ID of the channel to monitor
channel_id = "YOUR_CHANNEL_ID"  # Your actual channel ID

# List to store the last MAX_MEASUREMENTS measurements for the task function
measurements = []
# Data buffer for data collector role
data_buffer = []
# Plotting buffer 
plotting_buffer = []

# Flag used to allow sending to Discord server users
user_warning_flag = False

# Event handlers setup 
@client.event
async def on_ready():
    print("Success: Bot is connected to Discord.")
    if not check_messages.is_running():
        check_messages.start()
    if not check_motion_messages.is_running():
        check_motion_messages.start()

#===============================================================================
# USER WARNING COMMANDS 

@client.command()
async def allow_user_warning(ctx):
    global user_warning_flag
    user_warning_flag = True
    await ctx.send("Server member warnings are now allowed.")

@client.command()
async def disallow_user_warning(ctx):
    global user_warning_flag
    user_warning_flag = False
    await ctx.send("Server member warnings are now disallowed.")

#===============================================================================
# CHECK BOT LATENCY COMMAND

@client.command()
async def ping(ctx):
    bot_latency = round(client.latency * 1000)
    await ctx.send(f"Bot latency: {bot_latency} ms.")

#===============================================================================
# ULTRASONIC SENSOR COMMANDS 

# Role name for Distance Measurement
DISTANCE_MEASUREMENT_ROLE_NAME = "Distance measurement"  # Replace with your actual role name

@client.command()
async def send_ultrasonic(ctx):
    if has_role(ctx.author, DISTANCE_MEASUREMENT_ROLE_NAME):
        await send_command_to_esp("send_ultrasonic")
        await ctx.send("Command to start sending ultrasonic data sent to ESP8266.")
    else:
        await ctx.send("You do not have the required role to use this command.")

@client.command()
async def stop_ultrasonic(ctx):
    if has_role(ctx.author, DISTANCE_MEASUREMENT_ROLE_NAME):
        await send_command_to_esp("stop_ultrasonic")
        await ctx.send("Command to stop sending ultrasonic data sent to ESP8266.")
    else:
        await ctx.send("You do not have the required role to use this command.")

@client.command()
async def set_warning_threshold(ctx, value: int):
    if has_role(ctx.author, DISTANCE_MEASUREMENT_ROLE_NAME):
        global WARNING_THRESHOLD
        WARNING_THRESHOLD = value
        await ctx.send(f"Warning threshold updated to {WARNING_THRESHOLD} cm.")
    else:
        await ctx.send("You do not have the required role to use this command.")

@client.command()
async def plot(ctx):
    if has_role(ctx.author, DISTANCE_MEASUREMENT_ROLE_NAME):
        if len(plotting_buffer) == 0:
            await ctx.send("No data to plot.")
            return

        # Create indices starting from 1
        indices = list(range(1, len(plotting_buffer) + 1))
        distances = list(plotting_buffer)

        # Plotting the data
        plt.figure(figsize=(10, 5))
        plt.stem(indices, distances)
        plt.title('Distance Measurements')
        plt.xlabel('Measurement history')
        plt.ylabel('Distance (cm)')

        # Hide x-axis ticks
        plt.xticks([])

        plt.tight_layout()

        # Save plot to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Send the plot to Discord
        await ctx.send(file=discord.File(buf, 'plot.png'))
    else:
        await ctx.send("You do not have the required role to use this command.")

@client.command()
async def hist(ctx):
    if has_role(ctx.author, DISTANCE_MEASUREMENT_ROLE_NAME):
        if len(measurements) == 0:
            await ctx.send("No data for histogram.")
            return

        # Plotting the data
        plt.figure(figsize=(10, 5))
        
        distances = [m for m in plotting_buffer]
        weights = np.ones_like(distances) / float(len(distances))
        plt.hist(distances, weights=weights)
        plt.title('Histogram of measurements')
        plt.xlabel('Distance value')
        plt.ylabel('Frequency')
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Save plot to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Send the plot to Discord
        await ctx.send(file=discord.File(buf, 'plot.png'))
    else:
        await ctx.send("You do not have the required role to use this command.")

#===============================================================================
# PIR SENSOR COMMANDS

# Role name for Motion Detection
MOTION_DETECTION_ROLE_NAME = "Motion detection" 

@client.command()
async def send_pir(ctx):
    if has_role(ctx.author, MOTION_DETECTION_ROLE_NAME):
        await send_command_to_esp("send_pir")
        await ctx.send("Command to start sending PIR data sent to ESP8266.")
    else:
        await ctx.send("You do not have the required role to use this command.")

@client.command()
async def stop_pir(ctx):
    if has_role(ctx.author, MOTION_DETECTION_ROLE_NAME):
        await send_command_to_esp("stop_pir")
        await ctx.send("Command to stop sending PIR data sent to ESP8266.")
    else:
        await ctx.send("You do not have the required role to use this command.")

#===============================================================================
# TASK DEFINITIONS 

# Variables to track the last warning time and warning status
last_warning_time = datetime.now() - timedelta(seconds=WARNING_INTERVAL_DISTANCE)  # Initialize to allow an immediate first warning
warning_sent = False

@tasks.loop(seconds=LOOP_SECONDS_D)
async def check_messages():
    global last_warning_time, warning_sent
    channel = client.get_channel(channel_id)
    if channel is None:
        print("Channel not found")
        return

    async for message in channel.history(limit=MAX_MEASUREMENTS):
        # Extract distance measurement from the message
        distance = extract_distance(message.content)
        if distance is not None:
            add_measurement(distance)
            # Check if the distance exceeds the WARNING_THRESHOLD
            if distance > WARNING_THRESHOLD:
                current_time = datetime.now()
                # Check if the warning interval has passed
                if (current_time - last_warning_time).total_seconds() >= WARNING_INTERVAL_DISTANCE:
                    if not warning_sent:
                        # Notify the channel
                        await channel.send(f"⚠️ **Warning**: The distance measured is {distance} cm, which is higher than the threshold of {WARNING_THRESHOLD} cm.")
                        last_warning_time = current_time  # Update last warning time
                        warning_sent = True  # Set flag to indicate warning has been sent
                        
                        # Notify all users via direct message
                        if user_warning_flag:
                            guild = channel.guild
                            for member in guild.members:
                                if member != client.user:  # Skip the bot itself
                                    try:
                                        await member.send(f"⚠️ **Warning**: The distance measured is {distance} cm, which is higher than the threshold of {WARNING_THRESHOLD} cm.")
                                    except discord.Forbidden:
                                        print(f"Could not send message to {member.name}")
            else:
                # Reset warning flag if no alert is needed and the interval has passed
                if (datetime.now() - last_warning_time).total_seconds() >= WARNING_INTERVAL_DISTANCE:
                    warning_sent = False

# Variables to track the last intruder warning time and warning status
last_intruder_warning_time = datetime.now() - timedelta(seconds=5)  # Initialize to allow an immediate first warning
warning_sent = False

@tasks.loop(seconds=LOOP_SECONDS_PIR)
async def check_motion_messages():
    global last_intruder_warning_time, warning_sent
    channel = client.get_channel(channel_id)  # Use the data channel ID here
    if channel is None:
        print("Channel not found")
        return

    # Retrieve the last 2 messages from the channel
    messages = [message async for message in channel.history(limit=2)]

    # Check if all messages contain "Motion detected!"
    if all("Motion detected!" in message.content for message in messages):
        current_time = datetime.now()
        # Check if 5 seconds have passed since the last warning and if the warning hasn't been sent yet
        if not warning_sent and (current_time - last_intruder_warning_time).total_seconds() >= WARNING_INTERVAL_PIR:
            if user_warning_flag:
                guild = channel.guild
                for member in guild.members:
                    if member != client.user:  # Skip the bot itself
                        try:
                            await member.send("⚠️ **Warning**: Motion detection persists! Possible intruder?")
                            print(f"Notification sent to {member.name}")
                        except discord.Forbidden:
                            print(f"Could not send message to {member.name}")
            await channel.send("⚠️ **Warning**: Motion detection persists! Possible intruder?")
            last_intruder_warning_time = current_time  # Update last warning time
            warning_sent = True  # Set flag to indicate warning has been sent
    else:
        # Reset warning flag if no alert is needed
        warning_sent = False

#===============================================================================
# LED TOGGLE COMMANDS

@client.command()
async def led_on(ctx):
    await send_command_to_esp("led_on")
    await ctx.send("LED turned on.")

# Command to turn the LED off
@client.command()
async def led_off(ctx):
    await send_command_to_esp("led_off")
    await ctx.send("LED turned off.")

#===============================================================================
# EVENT DEFINITIONS

@client.event
async def on_message(message):
    global data_buffer, plotting_buffer
    if message.author == client.user:
        return  # Ignore messages from the bot itself

    role_name = "Data collector"

    if has_role(message.author, role_name):
        # Check for float numbers in the message
        if "set_warning_threshold" not in message.content:
            float_pattern = re.compile(r'[-+]?\d*\.\d+|\d+')
            floats = float_pattern.findall(message.content)

            for float_number in floats:
                try:
                    float_value = float(float_number)
                    data_buffer.append(float_value)
                    if len(data_buffer) == 10:
                        print(f"Found float from {message.author}: {data_buffer}")
                        await send_command_to_esp(f"data_collected: {data_buffer}")
                        data_buffer.clear()
                except ValueError:
                    continue

    # Ensure the bot processes commands too
    await client.process_commands(message)
    
    # Update measurements for plotting buffer
    if "Distance is" in message.content:
        try:
            float_pattern = re.compile(r'[-+]?\d*\.\d+|\d+')
            float_value = float(float_pattern.findall(message.content)[0])
            plotting_buffer.append(float_value)

            if len(plotting_buffer) > MAX_MEASUREMENTS:
                plotting_buffer.pop(0)
        except (ValueError, AttributeError):
            pass

#===============================================================================
# RESPONSE HANDLING FUNCTION DEFINITION

async def send_command_to_esp(command):
    endpoint = f"{esp8266_ip}/?command={command}"
    try:
        response = requests.get(endpoint)
        if response.status_code == 200:
            print(f"Command '{command}' sent to ESP8266.")
        else:
            print(f"Failed to send command. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

#===============================================================================
# HELPER FUNCTION DEFINITIONS 

def extract_distance(message):
    '''Parsing the distance string, extract distance value'''
    if "Distance is" in message:
        try:
            parts = message.split(" ")
            distance = float(parts[2])
            return distance
        except (IndexError, ValueError):
            return None
    return None

def add_measurement(distance):
    '''Update the measurements buffer in the task function'''
    measurements.append(distance)
    if len(measurements) > MAX_MEASUREMENTS:
        measurements.pop(0)

# Ensure you have the has_role function defined
def has_role(user, role_name):
    """Check if the user has a specific role by name."""
    if not hasattr(user, 'guild') or user.guild is None:
        return False  # The user might be in a DM or otherwise not in a guild

    role = discord.utils.get(user.guild.roles, name=role_name)
    if role:
        return role in user.roles
    return False
#===============================================================================

# Run the client
client.run("YOUR_DISCORD_BOT_TOKKEN")
