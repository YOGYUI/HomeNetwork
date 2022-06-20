import time
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(23, GPIO.OUT)
GPIO.output(23, GPIO.LOW)

for i in range(2):
    GPIO.output(23, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(23, GPIO.LOW)
    time.sleep(0.2)

GPIO.cleanup()
