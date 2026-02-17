from abc import ABC, abstractmethod


class PeakDetector(ABC):
    @abstractmethod
    def detect_peaks(self, cavity_output, cavity_positions):
        """
        Detect peaks in the cavity output.

        Args:
            cavity_output (list): List of output voltages from the cavity scan.
            cavity_positions (list): List of corresponding cavity positions (wavelengths).

        Returns:
            list: List of detected peak positions (wavelengths).
        """
        return []


class SimpleThresholdDetector(PeakDetector):
    def __init__(self, threshold=0.02):
        self.threshold = threshold

    def detect_peaks(self, cavity_output, cavity_positions):
        """
        Detect peaks using a simple threshold and maximum value logic.
        Returns peaks sorted by amplitude (descending).
        """
        candidates = []  # Store (pos, amplitude)
        in_spike = False
        curr_max = 0
        curr_max_pos = 0

        for v, pos in zip(cavity_output, cavity_positions):
            if not in_spike:
                if v > self.threshold:
                    in_spike = True
                    curr_max = v
                    curr_max_pos = pos
            else:
                if v > curr_max:
                    curr_max = v
                    curr_max_pos = pos
                elif v < self.threshold:
                    in_spike = False
                    candidates.append((curr_max_pos, curr_max))
                    curr_max = 0
                    curr_max_pos = 0

        # Handle case where scan ends while still in a spike
        if in_spike:
            candidates.append((curr_max_pos, curr_max))

        # Sort by amplitude descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Return only positions
        return [p[0] for p in candidates]
