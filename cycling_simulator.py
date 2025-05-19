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
from datetime import datetime, timezone
import gpxpy
import math
import json

from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
import xml.etree.ElementTree as ET
import os
from xml.dom import minidom

CADENCE_CHARACTERISTIC_UUID = "00002a5b-0000-1000-8000-00805f9b34fb"  # Replace if needed
DEVICE_ADDRESS = "E5:80:49:E3:FC:92"  # Replace with your sensor's address
GPX_FILE_PATH = r"C:\Users\eser\Documents\codes\personal\bike_cadence_files\routes\2025-05-16_2247688153_GPX Download_ Grunewaldturm – Havel loop from Hohenzollernplatz.gpx"
PROGRESS_FILE_PATH = r"C:\Users\eser\Documents\codes\personal\ride_progress.json"
def save_progress(gps_index, total_distance_m, filename="ride_progress.json"):
    progress = {
        "gps_index": gps_index,
        "total_distance_m": total_distance_m
    }
    with open(filename, "w") as f:
        json.dump(progress, f)
def load_progress(filename=PROGRESS_FILE_PATH):
    try:
        with open(filename, "r") as f:
            progress = json.load(f)
            return progress.get("gps_index", 0), progress.get("total_distance_m", 0.0)
    except FileNotFoundError:
        return 0, 0.0  # start from beginning if no file found        

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
# Load GPS points from GPX file
def load_gpx_points(GPX_FILE_PATH):
    tree = ET.parse(GPX_FILE_PATH)
    root = tree.getroot()

     # GPX namespaces
    ns = {"default": "http://www.topografix.com/GPX/1/1"}
    trkpts = root.findall(".//default:trkpt", ns)

    gps_points = []
    total_distance = 0.0
    prev_lat, prev_lon = None, None
    for pt in trkpts:
        lat = float(pt.attrib["lat"])
        lon = float(pt.attrib["lon"])
        ele_tag = pt.find("default:ele", ns)
        ele = float(ele_tag.text) if ele_tag is not None else None

        if prev_lat is not None:
            dist = haversine(prev_lat, prev_lon, lat, lon)
            total_distance += dist

        gps_points.append({
            "lat": lat,
            "lon": lon,
            "ele": ele,
            "cum_distance": total_distance  # in meters
        })

        prev_lat, prev_lon = lat, lon

    return gps_points
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
        
        self.start_time = None
        self.total_time = 0
        self.wheel_circumference = wheel_circumference
        self.cadence_timeout = cadence_timeout
        self.timestamps = deque(maxlen=300)
        self.cadences = deque(maxlen=300)
        self.trackpoints = []  # List to store (timestamp, cadence, distance)
        self.gps_points = load_gpx_points(GPX_FILE_PATH)
        self.gps_index, self.total_distance_m = load_progress()
        self.loaded_distance_m = self.total_distance_m
        self.total_revolutions = self.total_distance_m / self.wheel_circumference
        self.session_distance_m = 0.0

    # def get_next_gps_point(self):
    #     if self.gps_index < len(self.gps_points):
    #         point = self.gps_points[self.gps_index]
    #         self.gps_index += 1
    #         return point["lat"], point["lon"]
    #     return None, None
    
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
            # Calculate total distance in km BEFORE matching GPS point
            self.total_distance_m = (self.total_revolutions * self.wheel_circumference)
            self.session_distance_m = self.total_distance_m - self.loaded_distance_m
            
            # Find closest GPX point matching total distance
            lat, lon, ele = None, None, None
            for i in range(self.gps_index, len(self.gps_points) - 1):
                d1 = self.gps_points[i]["cum_distance"]
                d2 = self.gps_points[i + 1]["cum_distance"]
                if d1 <= self.total_distance_m <= d2:
                    ratio = (self.total_distance_m - d1) / (d2 - d1)
                    lat = self.gps_points[i]["lat"] + ratio * (self.gps_points[i + 1]["lat"] - self.gps_points[i]["lat"])
                    lon = self.gps_points[i]["lon"] + ratio * (self.gps_points[i + 1]["lon"] - self.gps_points[i]["lon"])
                    ele = self.gps_points[i]["ele"] + ratio * (self.gps_points[i + 1]["ele"] - self.gps_points[i]["ele"])
                    self.gps_index = i
                    print(f"Trackpoint GPS: lat={round(lat, 5)}, lon={round(lon, 5)}, ele = {round(ele, 1)}")
                    break
                    
                    
            else:
                # End of route reached, use last known GPS point if available
                if self.gps_points:
                    lat = self.gps_points[-1]["lat"]
                    lon = self.gps_points[-1]["lon"]
                    ele = self.gps_points[-1]["ele"]    
            self.trackpoints.append({
            "time": datetime.fromtimestamp(current_time, tz=timezone.utc).isoformat(),
            "cadence": cadence,
            "lat": round(lat, 5) if lat is not None else None,
            "lon": round(lon, 5) if lon is not None else None,
            "ele": round(ele, 1) if ele is not None else None,
            "distance": round(self.session_distance_m, 2)
        })
        session_distance_km = self.session_distance_m /1000   
        total_distance_km = self.total_distance_m / 1000
        print(f"Cadence: {cadence:.2f} RPM")
        print(f"Total Ride Time: {self.total_time:.2f} seconds")
        print(f"Estimated Distance for Session: {session_distance_km:.2f} km")
        print(f"Estimated Distance for Route: {total_distance_km:.2f} km")
        self.timestamps.append(current_time)
        self.cadences.append(cadence)

def save_tcx(trackpoints):
    # Parse ISO time strings back to datetime objects for time calculations
    start_time = datetime.fromisoformat(trackpoints[0]["time"])
    end_time = datetime.fromisoformat(trackpoints[-1]["time"])
    total_time_seconds = (end_time - start_time).total_seconds()

    # Calculate total distance from last trackpoint or 0 if not available
    total_distance = trackpoints[-1].get("distance", 0) # meters
    
    tcx = Element("TrainingCenterDatabase", {
        "xmlns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
    })

    activities = SubElement(tcx, "Activities")
    activity = SubElement(activities, "Activity", Sport="Biking")
    SubElement(activity, "Id").text = trackpoints[0]["time"]

    lap = SubElement(activity, "Lap", StartTime=trackpoints[0]["time"])
    SubElement(lap, "TotalTimeSeconds").text = str(total_time_seconds)
    SubElement(lap, "DistanceMeters").text = str(total_distance)
    SubElement(lap, "Intensity").text = "Active"
    SubElement(lap, "TriggerMethod").text = "Manual"

    track = SubElement(lap, "Track")
    for pt in trackpoints:
        tp = SubElement(track, "Trackpoint")
        SubElement(tp, "Time").text = pt["time"]

        # Position is optional
        if "lat" in pt and pt["lat"] is not None and "lon" in pt and pt["lon"] is not None:
            position = SubElement(tp, "Position")
            SubElement(position, "LatitudeDegrees").text = str(pt["lat"])
            SubElement(position, "LongitudeDegrees").text = str(pt["lon"])
        if "ele" in pt and pt["ele"] is not None:
            SubElement(tp, "AltitudeMeters").text = str(pt["ele"])
        if "distance" in pt and pt["distance"] is not None:
            SubElement(tp, "DistanceMeters").text = str(pt["distance"])

        if "cadence" in pt and pt["cadence"] is not None:
            SubElement(tp, "Cadence").text = str(int(pt["cadence"]))


    filename = f"workout_{datetime.now().strftime('%Y%m%d_%H%M')}.tcx"

    # Beautify and save
    xmlstr = minidom.parseString(tostring(tcx)).toprettyxml(indent="   ")
    with open(filename, "w") as f:
        f.write(xmlstr)
    print(f"Workout saved to {filename}")

def stop_button_callback(event):
    global is_running
    is_running = False
    if cadence_handler.start_time:
        
        save_tcx(cadence_handler.trackpoints)
        save_progress(cadence_handler.gps_index, cadence_handler.total_distance_m)
    plt.close()

# Plotting function
def update_plot(frame):
    ax_plot.clear()
    if cadence_handler.cadences:
        relative_times = [t - cadence_handler.timestamps[0] for t in cadence_handler.timestamps]
        ax_plot.plot(relative_times, cadence_handler.cadences, label="Cadence (RPM)", color="green")
        total_distance_km = cadence_handler.total_distance_m / 1000
        session_distance_km = cadence_handler.session_distance_m / 1000
        duration_sec = cadence_handler.total_time
        duration_min = duration_sec / 60
        ax_plot.set_title(f"Cadence Monitor | Route Distance: {total_distance_km:.2f} km | Session Distance: {session_distance_km:.2f} km | Time: {duration_min:.1f} min")
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

