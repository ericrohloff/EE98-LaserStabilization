class PID:
    def __init__(
        self, Kp=0.0, Ki=0.0, Kd=0.0, setpoint=0.0, output_limits=(None, None)
    ):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.output_limits = output_limits

        self._prev_error = 0.0
        self._integral = 0.0

    def update(self, measurement, dt):
        """
        Calculate the control output based on the measurement and time step.
        """
        error = self.setpoint - measurement

        # Proportional term
        P = self.Kp * error

        # Integral term
        self._integral += error * dt
        I = self.Ki * self._integral

        # Derivative term
        derivative = (error - self._prev_error) / dt if dt > 0 else 0.0
        D = self.Kd * derivative

        # Calculate output
        output = P + I + D

        # Clamp output
        min_out, max_out = self.output_limits
        if min_out is not None and output < min_out:
            output = min_out
        elif max_out is not None and output > max_out:
            output = max_out

        self._prev_error = error

        return output

    def reset(self):
        self._prev_error = 0.0
        self._integral = 0.0
