import numpy as np
import matplotlib.pyplot as plt

times = np.linspace(0, 2, 5001) # in ms

whiteNoise = np.random.normal(0, 0.002, len(times))

G = 0.005
A = 0.1 * G / 2
t0 = 1.0

t0Noise = np.random.normal(0, 0.001, len(times))

signal = A * G/2 / ((times - (t0 + t0Noise))**2 + (G/2)**2)

# best possible- 2.5MHz - fully recreate signal

# worst possible- 250KHz

# not limited by processing speed 

# signal noise can be modeled as white noise with a standard deviation of 1-2mV, i.e. can be as much as 6-8 mV, over 10 is very unlikely, peaks typically range from [20-100] mV, maybe as low as 15 mV

# very crude peak detection
data = signal + whiteNoise
sampleIndex = 0
currMax = 0
peakVals = []
peakLocs = []
seqOvers = 0

for val in data:
    if(val > 0.01):
        seqOvers += 1
        if(currMax < val):
            currMax = val
            maxLoc = sampleIndex
    if(val < 0.01):
        if(seqOvers > 5):
            peakVals.append(int(currMax*100000)/100)
            peakLocs.append(maxLoc)
        currMax = 0
        seqOvers = 0
    sampleIndex += 1

print(peakVals)
print(peakLocs)


fig = plt.figure(figsize=(10/2.54, 6/2.54))
plt.plot(times, data)
plt.title("Sample Generated Signal")
plt.ylabel("Signal / V")
plt.xlabel("Time / ms")
plt.tight_layout()
plt.savefig("sampleSignal.png")
plt.close()

fig = plt.figure(figsize=(10/2.54, 6/2.54))
plt.plot(times, data)
plt.title("Sample Generated Signal (Zoomed In)")
plt.xlim(0.98, 1.02)
plt.ylabel('Signal / V')
plt.xlabel('Time / ms')
plt.tight_layout()
plt.savefig("sampleSignalZoom.png")
plt.close()
