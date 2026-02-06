import pandas as pd
import matplotlib.pyplot as plt

def runSampleX(x):

    if(x < 10):
        fileName = "sampleData\TEK0000" + str(x) + ".CSV"
    else:
        fileName = "sampleData\TEK000" + str(x) + ".CSV"

    df = pd.read_csv(fileName, skiprows=15)

    time = df["TIME"].to_numpy()
    rampSignal = df["CH2"].to_numpy()
    laserSignal = df["CH3"].to_numpy()


    peakLocs = []
    inSpike = False
    currMax = 0
    currMaxPos = 0

    for i in range(1, len(laserSignal) - 1):
        if(inSpike and laserSignal[i] > currMax):
            currMax = laserSignal[i]
            currMaxPos = i

        if(rampSignal[i] < 25 and laserSignal[i] > 0.02 and not inSpike):
            inSpike = True
            currMax = laserSignal[i]
            currMaxPos = i
        elif(inSpike and laserSignal[i] < 0.01):
            inSpike = False
            peakLocs.append(currMaxPos)
            currMax = 0

    print("Calculated " + str(len(peakLocs)) + " peaks of " + str(laserSignal[peakLocs]) + " in sample " + str(x) + " at " + str(time[peakLocs]) + " seconds (indicies: " + str(peakLocs) + ")")


    fig, ax1 = plt.subplots()

    ax1.plot(time, rampSignal, label="Ramp Signal")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Ramp Signal Voltage")

    ax2 = ax1.twinx()
    ax2.plot(time, laserSignal, color='red', label="Laser Signal")
    ax2.set_ylabel("Laser Signal Voltage")
    ax2.plot(time[peakLocs], laserSignal[peakLocs], "go", label="Peaks")

    lines = ax1.get_lines() + ax2.get_lines()
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels)

    plt.grid(True)

    if(x < 10):
        fileName = "samplePlots\plot0" + str(x) + ".png"
    else:
        fileName = "samplePlots\plot" + str(x) + ".png"

    plt.savefig(fileName)
    plt.show()
    plt.close()

# for i in range(0, 100):
#     runSampleX(i)

runSampleX(94)
