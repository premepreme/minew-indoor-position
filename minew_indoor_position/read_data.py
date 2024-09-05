from core.config import settings
from db.services import get_avg

if __name__ == "__main__":
    device_macs = settings.DEVICE_MACS
    gateway_macs = settings.GATEWAY_MACS

    print(device_macs)
    print(gateway_macs)

    print(get_avg(key=f"{device_macs[0]}_{gateway_macs[0]}"))
    print(get_avg(key=f"{device_macs[0]}_{gateway_macs[1]}"))
