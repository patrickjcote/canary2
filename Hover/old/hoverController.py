# File: hoverController.py
# Version: 0.1 - untested
# Author: 2018 - Patrick Cote
# Description: Hover Controller with i2c sensor read and threading

# Libraries
import RPi.GPIO as GPIO
from time import sleep, strftime, time
from SensorComm import SensorComm
from CanaryComm import CanaryComm
from threading import Thread
#import serial

# Init Classes
sensors = SensorComm(0x52)
canary = CanaryComm(0x08)

# --------------- Test Settings------------------------------------------------
armDrone = input("Arm drone [0 - No, 1 - yes]: ")	 # enable drone
logOn = 1		# enable data logging
setpoint = 55	# [cm]
testDur = 25	# Length of test [s]
# Limits
TMAX = 1780		# Max throttle value
TMIN = 1600# Min throttle value
TMID = 1630	# Initial Throttle
IMAX = 5000
IMIN = -5000
SMA_LENGTH = 3

# Controller Gains
Kp = input("Kp Gain : ")		# Proportional gain
Ki = input("Ki Gain : ")		# Integral gain
Kd = input("Kd Gain : ")		# Derivative gain

# Display Test Parameters
print "---- Test Plan ----"
print "Set point: ",setpoint
print "Throttle Range of ",TMIN,"-",TMAX," for ",testDur,"s"
print "P: ",Kp," I: ",Ki," Kd: ",Kd

# Confirm Drone Arming
if armDrone:
	armDrone = input("Confirm drone arm [0 - No, 1 - yes]: ")	 # enable drone

# --------------- Init Threading ----------------------------------------------
global height
# Flight Value Thread Function
def _FlightValuesThread():
	global throttle, canary, flightThreadFlag, flightThreadEnable, armDrone
	while flightThreadFlag:
		if flightThreadEnable:
			try:
				canary.setThrottle(throttle)
			except:
				print "Throttle set error"
			sleep(.06)

# Sensor read thread Function
def _SensorThread():
	global height, sensors, sensorThreadFlag, heightUpdated
	distArray = [0]*SMA_LENGTH
	while sensorThreadFlag:
		distIn = sensors.readSingle('1')
		distArray.append(distIn)
		del distArray[0]
		height = sum(distArray)/SMA_LENGTH
		heightUpdated = 1
		sleep(.06)

if armDrone:
	flightThreadFlag = 1
	flightThreadEnable = 0
	flightThread = Thread(target=_FlightValuesThread)
	flightThread.start()
	sleep(.01)

heightUpdated = 0
sensorThreadFlag = 1
sensorThread = Thread(target=_SensorThread)
sensorThread.start()
sleep(1)

# --------------- Takeoff Sequence---------------------------------------------
if armDrone:
	canary = CanaryComm(0x08)
	sleep(1)
	canary.arm()
	sleep(2)
	# Take off Sequence
	tTakeoff = time()
	try:
		while time()<(tTakeoff + .15):
			canary.setThrottle(TMID*.6)
		while time()<(tTakeoff + .25):
			canary.setThrottle(TMID*.7)
		while time()<(tTakeoff + .35):
			canary.setThrottle(TMID*.8)
		while time()<(tTakeoff + .45):
			canary.setThrottle(TMID*.9)
		while time()<(tTakeoff + 1.5):
			canary.setThrottle(TMID)
	except KeyboardInterrupt:
		canary.disarm()
		exit()

# --------------- Init Controller ---------------------------------------------
throttle = TMID
dt = 1
dErr = 0
iErr = 0
heightPrev = height
flightThreadEnable = 1
# --------------- Test Start --------------------------------------------------
tstart = time()

if logOn:
	fname = 'logs/hcontroller/'
	if armDrone == 0:
		fname = fname+'x'
	fname = fname+strftime("%Y.%m.%d.%H%M%S")+'.S'+str(setpoint)
	fname = fname+'Tl'+str(TMIN)+'Th'+str(TMAX)+'A'
	fname = fname+'PID'+str(Kp)+'-'+str(Ki)+'-'+str(Kd)+'.csv'
	f = open(fname,'a')


while time()<(tstart+testDur):
	try:
		# Controller
		error = (setpoint-height)
		iErr = iErr + error*dt
		# Anti-windup reset
		iErr = min(max(iErr,IMIN),IMAX)
		dErr = (height-heightPrev)/dt
		heightPrev = height
		Tpid = Kp*error+Ki*iErr-Kd*dErr + TMID
		# Limit Throttle Values
		throttle = int(min(max(Tpid,TMIN),TMAX))
		
		# Logging - CSV File:
		# Time, height, throttle, error, controller out, <CR>
		if logOn:
			data = str(time())+','+str(height)+','+str(throttle)+','
			data = data + str(error)+','+str(Tpid)+','
			data = data+'\n'
			f.write(data)
		# Status Output
		print "Height: ",height,"cm","   Error: ",error
		print "Set Throttle: ",throttle,"    Controller Output: ",Tpid
		print "Height: {0:3d} Perr: {1:3d} Ierr: {2:4d}  Derr: {3:4d}".format(height,error,int(iErr),int(dErr))
		
		heightUpdated = 0
		while not heightUpdated:
			pass
		
	except KeyboardInterrupt:
		if armDrone:
			print "\nCanary Disarm"
			canary.disarm()
			flightThreadFlag = 0
		if logOn:
			f.close()
		GPIO.cleanup()
		sensorThreadFlag = 0
		print "\nKeyboard Exit"
		exit()
# --------------- Test Complete   ---------------------------------------------

if armDrone:
	# ODO: Proper landing sequence
	print "\nCanary Landing..."
	tTakeoff = time()
	while time()<(tTakeoff + 2):
		canary.setThrottle(1580)
	while time()<(tTakeoff + 2.5):
		canary.setThrottle(1575)
	print "\nCanary Disarm"
	canary.disarm()
	flightThreadFlag = 0
sensorThreadFlag = 0
f.close()
GPIO.cleanup()
if logOn:
	f.close()
print "\nTest Completed"
