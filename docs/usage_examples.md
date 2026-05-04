# Usage Examples

This guide shows practical examples of how to use the laser stabilization system
from the host computer.

## Setup

First, make sure the server is running on the PYNQ board and the host client is
installed:

```bash
# On host computer
cd software/hostComputer
python host_cli.py
```

You'll see a prompt where you can type commands.

## Basic Workflow

### 1. Create a Laser

Before you can control a laser, you need to create it with PID parameters.

```
create_laser(pid)
```

**Parameters:**

- `pid`: Laser index (0-4). Pick any from 0-4 for the 5 available laser slots.

**Use Case: Set up laser 0 with initial PID tuning**

```
create_laser(0)
```

---

### 2. Configure Laser PID Parameters

Adjust the PID tuning parameters for feedback control.

```
configure_laser_pid(pid, kp, ki, kd)
```

**Parameters:**

- `pid`: Laser index (0-4)
- `kp`: Proportional gain. Higher = faster response, too high = unstable. Start
  with 100.
- `ki`: Integral gain. Reduces steady-state error over time. Start with 50.
- `kd`: Derivative gain. Helps dampen oscillations. Start with 10.

**Use Case: Tune laser 0 for better stability**

```
configure_laser_pid(0, kp=150, ki=75, kd=15)
```

**Use Case: Switch to a faster response (aggressive tuning)**

```
configure_laser_pid(0, kp=250, ki=100, kd=20)
```

---

### 3. Start Cavity Scan

Begin scanning the optical cavity. This is required before locking any laser.

```
start_cavity_scan(duration)
```

**Parameters:**

- `duration`: How long to scan in seconds.

**Use Case: Scan for 30 seconds to let the system stabilize**

```
start_cavity_scan(30)
```

**Use Case: Quick 5-second test scan**

```
start_cavity_scan(5)
```

---

### 4. Lock a Laser

Lock a laser to a target wavelength while the cavity is scanning.

```
lock(pid, wavelength)
```

**Parameters:**

- `pid`: Laser index (0-4)
- `wavelength`: Target wavelength in nanometers (nm)

**Use Case: Lock laser 0 to 650 nm (common red laser)**

```
lock(0, 650.0)
```

**Use Case: Lock laser 1 to 780 nm (near-IR)**

```
lock(1, 780.0)
```

**Use Case: Lock multiple lasers**

```
lock(0, 625.0)
lock(1, 650.0)
lock(2, 675.0)
```

---

### 5. Unlock a Laser

Release a laser from frequency locking. It will stop trying to hold its
wavelength.

```
unlock(pid)
```

**Parameters:**

- `pid`: Laser index (0-4)

**Use Case: Stop controlling laser 0**

```
unlock(0)
```

---

### 6. Stop Cavity Scan

Stop the cavity scan and disable all feedback.

```
stop_cavity_scan()
```

**Use Case: End the experiment**

```
stop_cavity_scan()
```

---

## Complete Example: Multi-Laser Lock

This example shows a realistic workflow with multiple lasers.

```
# Set up three lasers with different PID tuning
create_laser(0)
create_laser(1)
create_laser(2)

# Tune each one differently based on laser characteristics
configure_laser_pid(0, kp=100, ki=50, kd=10)    # Slow laser
configure_laser_pid(1, kp=150, ki=75, kd=15)    # Medium laser
configure_laser_pid(2, kp=200, ki=100, kd=20)   # Fast laser

# Start scanning for 60 seconds
start_cavity_scan(60)

# Lock them to target wavelengths
lock(0, 625.0)
lock(1, 650.0)
lock(2, 675.0)

# Let them run and stabilize
# ... (wait a bit)

# Stop when done
stop_cavity_scan()
```

---

## Tips

- **Start conservative with PID tuning** - High gains can cause oscillations
- **Scan duration matters** - Shorter scans are good for testing, longer scans
  for stability measurement
- **Lock in order** - Create all lasers first, then start scanning, then lock
  them
- **Wavelength ranges** - Keep wavelengths between 600-800 nm for typical
  visible/IR lasers
