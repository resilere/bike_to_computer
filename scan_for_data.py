import asyncio
from bleak import BleakClient

SENSOR_ADDRESS = "E5:80:49:E3:FC:92"  # Replace with your sensor's MAC address
UUID = "00002a5b-0000-1000-8000-00805f9b34fb"  # CSC Measurement UUID

async def check_data():
    async with BleakClient(SENSOR_ADDRESS) as client:
        print("Connected to sensor.")
        
        def notification_handler(sender, data):
            print(f"Data from {sender}: {data}")
        
        await client.start_notify(UUID, notification_handler)
        await asyncio.sleep(10)  # Listen for 10 seconds
        await client.stop_notify(UUID)

asyncio.run(check_data())
