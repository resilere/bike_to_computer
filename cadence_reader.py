import asyncio
import pyautogui
import keyboard
import time
from bleak import BleakClient
import struct
CADENCE_CHARACTERISTIC_UUID = "00002a5b-0000-1000-8000-00805f9b34fb"  # Replace if needed


# Decoder function
def decode_csc_data(data, previous_revolutions=None, previous_time=None):
    # Unpack the data
    flags = data[0]
    crank_revolutions = struct.unpack_from("<H", data, 1)[0]  # 2 bytes, little-endian
    crank_event_time = struct.unpack_from("<H", data, 3)[0]  # 2 bytes, little-endian

    # Print parsed data
    print(f"Flags: {bin(flags)}")
    print(f"Cumulative Crank Revolutions: {crank_revolutions}")
    print(f"Last Crank Event Time: {crank_event_time} (1/1024 seconds)")

    # Calculate cadence
    cadence = None
    if previous_revolutions is not None and previous_time is not None:
        delta_revolutions = crank_revolutions - previous_revolutions
        delta_time = (crank_event_time - previous_time) / 1024  # Convert to seconds
        if delta_time > 0:
            cadence = (delta_revolutions / delta_time) * 60  # Convert to RPM
            print(f"Cadence: {cadence:.2f} RPM")
        else:
            cadence = None
            print("Delta time is zero or negative, skipping cadence calculation.","cadence is:",cadence)

    return crank_revolutions, crank_event_time, cadence

# Real-time cadence handler
class CadenceHandler:
    def __init__(self):
        self.previous_revolutions = None
        self.previous_time = None
        self.last_cadence = None  # Store last cadence value to track changes
        self.last_keypress_time = time.time()  # Track the time of the last keypress
    def handle_data(self, sender, data):
        # Decode and calculate cadence
        print(f"Data from {sender}: {data}")
        self.previous_revolutions, self.previous_time, cadence = decode_csc_data(
            data,
            self.previous_revolutions,
            self.previous_time,
        )
        if cadence is not None:
            print(f"Current Cadence: {cadence:.2f} RPM")
            if cadence > 80:
                if self.last_cadence != cadence:  # Avoid repeated pressing
                    print("Cadence > 80: Pressing 'w' and 'shift'","cadence and last cadence",cadence, self.last_cadence)
                    keyboard.press('w')
                    keyboard.press('shift')
                    self.last_keypress_time = time.time()  # Update time of last key press
                    self.last_cadence = cadence
            elif cadence > 0:
                if self.last_cadence != cadence:  # Avoid repeated pressing
                    print("Cadence > 0: Pressing 'w'","cadence and last cadence",cadence, self.last_cadence)
                    keyboard.press('w')
                    self.last_keypress_time = time.time()  # Update time of last key press
                    self.last_cadence = cadence
        else:
            print('cadence is none',"cadence and last cadence",cadence, self.last_cadence)
            if self.last_cadence is not None:
                print("Cadence data invalid: Releasing keys.","cadence and last cadence",cadence, self.last_cadence)
                keyboard.release('w')
                keyboard.release('shift')
                self.last_cadence = None  # Reset cadence tracking
        # Sleep to avoid overloading the CPU
        if time.time() - self.last_keypress_time < 0.1:  # Only press again after 100ms
            time.sleep(0.1)

# Main subscription function
async def subscribe_to_cadence(address, char_uuid):
    cadence_handler = CadenceHandler()

    async with BleakClient(address) as client:
        print("Connected to device")
        await client.start_notify(char_uuid, cadence_handler.handle_data)

        # Keep listening for data
        try:
            print("Listening for cadence data. Press Ctrl+C to stop.")
            while True:
                await asyncio.sleep(1)  # Keep the script alive
        except KeyboardInterrupt:
            print("Stopping notification...")
        finally:
            await client.stop_notify(char_uuid)
            print("Disconnected from device")

DEVICE_ADDRESS = "E5:80:49:E3:FC:92"  # Replace with your sensor's address
# Run the main loop
if __name__ == "__main__":
    asyncio.run(subscribe_to_cadence(DEVICE_ADDRESS, CADENCE_CHARACTERISTIC_UUID))