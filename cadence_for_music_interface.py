import asyncio
import pyautogui
import keyboard
import time
import struct
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button
from bleak import BleakClient
from collections import deque
import threading
from datetime import datetime
import xml.etree.ElementTree as ET
import os

CADENCE_CHARACTERISTIC_UUID = "00002a5b-0000-1000-8000-00805f9b34fb"  # Replace if needed
DEVICE_ADDRESS = "E5:80:49:E3:FC:92"  # Replace with your sensor's address

# Decoder function
def decode_csc_data(data, previous_revolutions=None, previous_time=None):
    flags = data[0]
    crank_revolutions = struct.unpack_from("<H", data, 1)[0]
    crank_event_time = struct.unpack_from("<H", data, 3)[0]

    cadence = None
    if previous_revolutions is not None and previous_time is not None:
        delta_revolutions = crank_revolutions - previous_revolutions
        delta_time = (crank_event_time - previous_time) / 1024
        if delta_time > 0:
            cadence = (delta_revolutions / delta_time) * 60
        else:
            cadence = None

    return crank_revolutions, crank_event_time, cadence

# Real-time cadence handler with graph support
class CadenceHandler:
    def __init__(self, wheel_circumference=2.1, cadence_timeout=3):
        self.previous_revolutions = None
        self.previous_time = None
        self.last_valid_cadence = 0
        self.last_cadence_time = None
        self.is_music_playing = False
        self.total_revolutions = 0
        self.start_time = None
        self.total_time = 0
        self.wheel_circumference = wheel_circumference
        self.cadence_timeout = cadence_timeout
        self.timestamps = deque(maxlen=300)
        self.cadences = deque(maxlen=300)
        
    def handle_data(self, sender, data):
        self.previous_revolutions, self.previous_time, cadence = decode_csc_data(
            data, self.previous_revolutions, self.previous_time)
        current_time = time.time()

        if cadence is not None:
            self.last_valid_cadence = cadence
            self.last_cadence_time = current_time
        elif self.last_cadence_time and (current_time - self.last_cadence_time) < self.cadence_timeout:
            cadence = self.last_valid_cadence
        else:
            cadence = 0

        if self.start_time is None and cadence > 0:
            self.start_time = current_time

        if cadence > 50:
            if not self.is_music_playing:
                keyboard.send("play/pause media")
                self.is_music_playing = True
                print("Music Started 🎵")
        else:
            if self.is_music_playing:
                keyboard.send("play/pause media")
                self.is_music_playing = False
                print("Music Paused ⏸")

        if cadence > 0:
            self.total_revolutions += cadence / 60
            self.total_time = current_time - self.start_time

        total_distance = (self.total_revolutions * self.wheel_circumference) / 1000
        print(f"Cadence: {cadence:.2f} RPM")
        print(f"Total Ride Time: {self.total_time:.2f} seconds")
        print(f"Estimated Distance: {total_distance:.2f} km")

        self.timestamps.append(current_time)
        self.cadences.append(cadence)

def generate_tcx(filename, start_time, duration_sec, distance_km):
    tcx_ns = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
    ET.register_namespace('', tcx_ns)

    root = ET.Element(f"{{{tcx_ns}}}TrainingCenterDatabase")
    activities = ET.SubElement(root, f"{{{tcx_ns}}}Activities")
    activity = ET.SubElement(activities, f"{{{tcx_ns}}}Activity", Sport="Biking")
    ET.SubElement(activity, f"{{{tcx_ns}}}Id").text = start_time.isoformat()

    lap = ET.SubElement(activity, f"{{{tcx_ns}}}Lap", StartTime=start_time.isoformat())
    ET.SubElement(lap, f"{{{tcx_ns}}}TotalTimeSeconds").text = f"{duration_sec:.1f}"
    ET.SubElement(lap, f"{{{tcx_ns}}}DistanceMeters").text = f"{distance_km * 1000:.1f}"
    ET.SubElement(lap, f"{{{tcx_ns}}}Intensity").text = "Active"
    ET.SubElement(lap, f"{{{tcx_ns}}}TriggerMethod").text = "Manual"

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)
    print(f"Workout saved to {os.path.abspath(filename)}")

def stop_button_callback(event):
    global is_running
    is_running = False
    if cadence_handler.start_time:
        end_time = time.time()
        duration = cadence_handler.total_time
        distance = (cadence_handler.total_revolutions * cadence_handler.wheel_circumference) / 1000
        start_time_dt = datetime.fromtimestamp(cadence_handler.start_time)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"workout_{timestamp}.tcx"
        generate_tcx(filename, start_time_dt, duration, distance)
    plt.close()

# Plotting function
def update_plot(frame):
    ax_plot.clear()
    if cadence_handler.cadences:
        relative_times = [t - cadence_handler.timestamps[0] for t in cadence_handler.timestamps]
        ax_plot.plot(relative_times, cadence_handler.cadences, label="Cadence (RPM)", color="green")
        distance = (cadence_handler.total_revolutions * cadence_handler.wheel_circumference) / 1000
        
        duration_sec = cadence_handler.total_time
        duration_min = duration_sec / 60
        ax_plot.set_title(f"Cadence Monitor | Distance: {distance:.2f} km | Time: {duration_min:.1f} min")
        ax_plot.set_xlabel("Time (s)")
        ax_plot.set_ylabel("Cadence (RPM)")
        # Set plot limits to avoid text overlap
        ax_plot.set_ylim(0, 150)
        ax_plot.set_xlim(0, max(relative_times) if relative_times else 10)
    
        ax_plot.legend()
    
# Main subscription function
async def subscribe_to_cadence(address, char_uuid):
    async with BleakClient(address) as client:
        print("Connected to device")
        await client.start_notify(char_uuid, cadence_handler.handle_data)

        try:
            print("Listening for cadence data. Press Ctrl+C to stop.")
            while is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Stopping notification...")
        finally:
            await client.stop_notify(char_uuid)
            if cadence_handler.start_time:
                end_time = time.time()
                duration = cadence_handler.total_time
                distance = (cadence_handler.total_revolutions * cadence_handler.wheel_circumference) / 1000
                start_time_dt = datetime.fromtimestamp(cadence_handler.start_time)
                generate_tcx("workout.tcx", start_time_dt, duration, distance)

                print("Disconnected from device")

# Setup
cadence_handler = CadenceHandler()
# Set up plot and button using gridspec
fig = plt.figure(figsize=(8, 6))
gs = fig.add_gridspec(5, 1)  # 5 rows, 1 column

# Use most of the space for the plot
ax_plot = fig.add_subplot(gs[:-1])  # rows 0-3
ax_button = fig.add_subplot(gs[-1])  # row 4

# Hide button axis borders
ax_button.axis("off")

ani = animation.FuncAnimation(fig, update_plot, interval=1000)

is_running = True  # Global flag to control stopping

# Create actual button widget
button_ax = fig.add_axes([0.4, 0.01, 0.2, 0.05])  # You can tweak this
stop_button = Button(button_ax, "Stop Workout")
stop_button.on_clicked(stop_button_callback)
# Run BLE subscription in a thread-safe event loop
def start_async_loop():
    asyncio.run(subscribe_to_cadence(DEVICE_ADDRESS, CADENCE_CHARACTERISTIC_UUID))

if __name__ == "__main__":
    threading.Thread(target=start_async_loop, daemon=True).start()
    plt.show()

