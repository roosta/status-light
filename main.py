import serial
import time

ser = serial.Serial('/dev/ttyUSB0', 9600)
time.sleep(2)  # Arduino resets on connection, need to wait

ser.write(b'r')  # red
time.sleep(1)
ser.write(b'g')  # green
time.sleep(1)
ser.write(b'o')  # off

ser.close()
