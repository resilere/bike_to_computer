from bleak import BleakClient
import asyncio
async def get_services(address):
    async with BleakClient(address) as client:
        services = await client.get_services()
        for service in services:
            print(f"Service: {service.uuid}")
            for char in service.characteristics:
                print(f"  Characteristic: {char.uuid}, Properties: {char.properties}")

address = "E5:80:49:E3:FC:92"  # Replace with your device's address
asyncio.run(get_services(address))
