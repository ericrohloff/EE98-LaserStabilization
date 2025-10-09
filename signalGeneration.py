import numpy as np
import matplotlib.pyplot as plt

times = np.linspace(0, 2, 5001) # in ms

whiteNoise = np.random.normal(0, 0.002, len(times))

G = 0.005
A = 0.1 * G / 2
t0 = 1.0

t0Noise = np.random.normal(0, 0.001, len(times))

signal = A * G/2 / ((times - (t0 + t0Noise))**2 + (G/2)**2)

fig = plt.figure(figsize=(10/2.54, 6/2.54))
plt.plot(times, signal + whiteNoise)
plt.title("Sample Generated Signal")
plt.ylabel("Signal / V")
plt.xlabel("Time / ms")
plt.tight_layout()
plt.savefig("sampleSignal.png")
plt.close()

fig = plt.figure(figsize=(10/2.54, 6/2.54))
plt.plot(times, signal + whiteNoise)
plt.title("Sample Generated Signal (Zoomed In)")
plt.xlim(0.98, 1.02)
plt.ylabel('Signal / V')
plt.xlabel('Time / ms')
plt.tight_layout()
plt.savefig("sampleSignalZoom.png")
plt.close()
