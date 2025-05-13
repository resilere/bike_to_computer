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

from xml.etree.ElementTree import Element, SubElement, ElementTree
import os
import xml.dom.minidom

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
        self.trackpoints = []  # List to store (timestamp, cadence, distance)
    
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
            distance_km = (self.total_revolutions * self.wheel_circumference) / 1000
            self.trackpoints.append((time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(current_time)), cadence, distance_km))
        
        total_distance = (self.total_revolutions * self.wheel_circumference) / 1000
        print(f"Cadence: {cadence:.2f} RPM")
        print(f"Total Ride Time: {self.total_time:.2f} seconds")
        print(f"Estimated Distance: {total_distance:.2f} km")

        self.timestamps.append(current_time)
        self.cadences.append(cadence)

def save_tcx(trackpoints):
    
    tcx = Element("TrainingCenterDatabase", {
        "xmlns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
    })

    activities = SubElement(tcx, "Activities")
    activity = SubElement(activities, "Activity", Sport="Biking")
    SubElement(activity, "Id").text = trackpoints[0][0] if trackpoints else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    lap = SubElement(activity, "Lap", StartTime=trackpoints[0][0])
    SubElement(lap, "TotalTimeSeconds").text = str(
        (datetime.strptime(trackpoints[-1][0], "%Y-%m-%dT%H:%M:%SZ") -
         datetime.strptime(trackpoints[0][0], "%Y-%m-%dT%H:%M:%SZ")).total_seconds())
    SubElement(lap, "DistanceMeters").text = str(trackpoints[-1][2] * 1000)

    track = SubElement(lap, "Track")
    for timestamp, cadence, distance_km in trackpoints:
        tp = SubElement(track, "Trackpoint")
        SubElement(tp, "Time").text = timestamp
        SubElement(tp, "DistanceMeters").text = str(distance_km * 1000)
        SubElement(tp, "Cadence").text = str(int(cadence))

    filename = f"workout_{datetime.now().strftime('%Y%m%d_%H%M')}.tcx"
    ElementTree(tcx).write(filename, encoding="utf-8", xml_declaration=True)
    print(f"Workout saved to {filename}")

def stop_button_callback(event):
    global is_running
    is_running = False
    if cadence_handler.start_time:
        
        save_tcx(cadence_handler.trackpoints)
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

