import asyncio
from bleak import BleakClient

SENSOR_ADDRESS = "E5:80:49:E3:FC:92"  # Replace with your sensor's MAC address
UUID = "00002a5b-0000-1000-8000-00805f9b34fb"
async def restart_sensor():
    async with BleakClient(SENSOR_ADDRESS) as client:
        print("Disconnecting...")
        await client.disconnect()
        await asyncio.sleep(2)  # Wait for 2 seconds before reconnecting
        print("Reconnecting...")
        await client.connect()
        print("Reconnected!")
        await client.start_notify(UUID, lambda s, d: print(f"Data: {d}"))
        await asyncio.sleep(10)  # Listen for 10 seconds
        await client.stop_notify(UUID)
asyncio.run(restart_sensor())
