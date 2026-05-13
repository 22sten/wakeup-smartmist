import machine
import sys
import time

# リレーがつながっているGPIOピン (例: GP15)
relay = machine.Pin(11, machine.Pin.OUT)
relay.value(0) # 最初はOFF

print("Pico Ready...")

while True:
    # 標準入力（USBシリアル）から1行読み込む
    line = sys.stdin.readline().strip()
    
    if line == "ON":
        relay.value(1)
        print("Relay ON")
    elif line == "OFF":
        relay.value(0)
        print("Relay OFF")
    
    time.sleep(0.1)