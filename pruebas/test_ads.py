import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS1115_mod
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115_mod.ADS1115(i2c)
ads.gain = 1

canales = [AnalogIn(ads, ch) for ch in range(4)]

print("Leyendo ADS1115...")

while True:
    for i, canal in enumerate(canales):
        print(f"A{i}: {canal.voltage:.4f} V", end="  |  ")
    print()
    time.sleep(1)
