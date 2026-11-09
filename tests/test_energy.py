#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.solarlog_client import EnergyDataService
from app.core.config import settings

def test():
    service = EnergyDataService(device_ip=settings.ENERGY_DEVICE_IP)
    print("Testing get_hourly_data for today (days_before=0)")
    data, total = service.get_hourly_data(0)
    print(f"Data: {data}")
    print(f"Total: {total}")

    print("\nTesting get_hourly_data for yesterday (days_before=1)")
    data, total = service.get_hourly_data(1)
    print(f"Data: {data}")
    print(f"Total: {total}")

if __name__ == "__main__":
    test()
