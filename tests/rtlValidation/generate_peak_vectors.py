import csv
import os
import random
from typing import List, Tuple

THRESHOLD = 2000
ASSIGN_WINDOW = 1500
MAX_CANDIDATES = 8

REF_TARGET = 32000
L1_TARGET = 12000
L2_TARGET = 24000
L3_TARGET = 40000
L4_TARGET = 52000

SAMPLES_PER_SCAN = 128
RAMP_MIN = 0
RAMP_MAX = 63000
NUM_SCANS = 8


def abs_diff(a: int, b: int) -> int:
    return abs(int(a) - int(b))


def nearest_candidate(expected: int, candidates: List[Tuple[int, int]], used: List[bool]):
    best_idx = None
    best_diff = None

    for i, (pos, _amp) in enumerate(candidates):
        if used[i]:
            continue
        d = abs_diff(pos, expected)
        if d > ASSIGN_WINDOW:
            continue
        if best_idx is None or d < best_diff:
            best_idx = i
            best_diff = d

    return best_idx


def detect_candidates(scan_rows):
    in_spike = False
    peak_amp = 0
    peak_pos = 0
    candidates = []

    for row in scan_rows:
        adc = row["adc"]
        pos = row["ramp_pos"]

        if adc > THRESHOLD:
            if not in_spike:
                in_spike = True
                peak_amp = adc
                peak_pos = pos
            elif adc >= peak_amp:
                peak_amp = adc
                peak_pos = pos
        elif in_spike:
            if len(candidates) < MAX_CANDIDATES:
                candidates.append((peak_pos, peak_amp))
            in_spike = False
            peak_amp = 0
            peak_pos = 0

    if in_spike and len(candidates) < MAX_CANDIDATES:
        candidates.append((peak_pos, peak_amp))

    return candidates


def assign_positions(candidates, prev_positions):
    used = [False] * len(candidates)

    # Reserve one candidate near the reference first.
    idx = nearest_candidate(REF_TARGET, candidates, used)
    if idx is not None:
        used[idx] = True

    out = dict(prev_positions)

    for key, expected in [
        ("l1", L1_TARGET),
        ("l2", L2_TARGET),
        ("l3", L3_TARGET),
        ("l4", L4_TARGET),
    ]:
        idx = nearest_candidate(expected, candidates, used)
        if idx is not None:
            used[idx] = True
            out[key] = candidates[idx][0]

    return out


def gaussian_peak(x: int, center: int, amp: int, width: int) -> int:
    dx = x - center
    # Integer-friendly gaussian-like shape for reproducible vectors.
    return int(amp * (2.718281828 ** (-(dx * dx) / float(width * width))))


def build_scan(scan_idx: int):
    rows = []

    centers = [
        L1_TARGET + random.randint(-350, 350),
        L2_TARGET + random.randint(-350, 350),
        REF_TARGET + random.randint(-350, 350),
        L3_TARGET + random.randint(-350, 350),
        L4_TARGET + random.randint(-350, 350),
    ]
    amps = [3200, 3500, 3600, 3300, 3400]

    for i in range(SAMPLES_PER_SCAN):
        ramp_pos = int(RAMP_MIN + (RAMP_MAX - RAMP_MIN) * i / (SAMPLES_PER_SCAN - 1))

        # Low baseline with noise, then add peaks above threshold.
        adc = random.randint(200, 500)

        for c, a in zip(centers, amps):
            adc += gaussian_peak(ramp_pos, c, a, 450)

        # Force an occasional no-peak scan to test hold-last behavior.
        if scan_idx % 5 == 4:
            adc = random.randint(100, 900)

        adc = max(0, min(65535, adc))

        rows.append({"adc": adc, "ramp_pos": ramp_pos})

    return rows


def simulate_reference(stim_rows):
    l1_pos = L1_TARGET
    l2_pos = L2_TARGET
    l3_pos = L3_TARGET
    l4_pos = L4_TARGET

    in_spike = False
    curr_peak_amp = 0
    curr_peak_pos = 0

    candidates: List[Tuple[int, int]] = []
    out_rows = []
    scan_idx = -1

    def push_candidate(amp: int, pos: int):
        if len(candidates) < MAX_CANDIDATES:
            candidates.append((pos, amp))

    for row in stim_rows:
        adc = row["adc"]
        adc_valid = row["adc_valid"]
        ramp_pos = row["ramp_pos"]
        scan_start = row["ramp_start"]

        if scan_start:
            if in_spike:
                push_candidate(curr_peak_amp, curr_peak_pos)
                in_spike = False
                curr_peak_amp = 0
                curr_peak_pos = 0

            used = [False] * len(candidates)

            idx = nearest_candidate(REF_TARGET, candidates, used)
            if idx is not None:
                used[idx] = True

            idx = nearest_candidate(L1_TARGET, candidates, used)
            if idx is not None:
                used[idx] = True
                l1_pos = candidates[idx][0]

            idx = nearest_candidate(L2_TARGET, candidates, used)
            if idx is not None:
                used[idx] = True
                l2_pos = candidates[idx][0]

            idx = nearest_candidate(L3_TARGET, candidates, used)
            if idx is not None:
                used[idx] = True
                l3_pos = candidates[idx][0]

            idx = nearest_candidate(L4_TARGET, candidates, used)
            if idx is not None:
                l4_pos = candidates[idx][0]

            candidates = []

            scan_idx += 1
            out_rows.append([scan_idx, l1_pos, l2_pos, l3_pos, l4_pos])

        if adc_valid:
            if adc > THRESHOLD:
                if not in_spike:
                    in_spike = True
                    curr_peak_amp = adc
                    curr_peak_pos = ramp_pos
                elif adc >= curr_peak_amp:
                    curr_peak_amp = adc
                    curr_peak_pos = ramp_pos
            elif in_spike:
                push_candidate(curr_peak_amp, curr_peak_pos)
                in_spike = False
                curr_peak_amp = 0
                curr_peak_pos = 0

    return out_rows


def main():
    random.seed(98)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    vectors_dir = os.path.join(repo_root, "hardware", "rtl", "vectors")
    os.makedirs(vectors_dir, exist_ok=True)

    stim_path = os.path.join(vectors_dir, "peak_stimulus.csv")
    expected_path = os.path.join(vectors_dir, "peak_expected.csv")

    all_scan_rows = [build_scan(i) for i in range(NUM_SCANS)]

    stim_rows = []

    with open(stim_path, "w", newline="") as f_stim:
        w = csv.writer(f_stim)
        w.writerow([
            "cycle",
            "adc_sample",
            "adc_sample_valid",
            "current_ramp_pos",
            "ramp_start",
            "ref_target",
            "l1_target",
            "l2_target",
            "l3_target",
            "l4_target",
        ])

        cycle = 0
        for scan_idx, scan_rows in enumerate(all_scan_rows):
            for i, row in enumerate(scan_rows):
                stim_row = {
                    "cycle": cycle,
                    "adc": row["adc"],
                    "adc_valid": 1,
                    "ramp_pos": row["ramp_pos"],
                    "ramp_start": 1 if i == 0 else 0,
                    "ref_target": REF_TARGET,
                    "l1_target": L1_TARGET,
                    "l2_target": L2_TARGET,
                    "l3_target": L3_TARGET,
                    "l4_target": L4_TARGET,
                }
                stim_rows.append(stim_row)

                w.writerow([
                    stim_row["cycle"],
                    stim_row["adc"],
                    stim_row["adc_valid"],
                    stim_row["ramp_pos"],
                    stim_row["ramp_start"],
                    stim_row["ref_target"],
                    stim_row["l1_target"],
                    stim_row["l2_target"],
                    stim_row["l3_target"],
                    stim_row["l4_target"],
                ])
                cycle += 1

    expected_rows = simulate_reference(stim_rows)

    with open(expected_path, "w", newline="") as f_exp:
        w = csv.writer(f_exp)
        w.writerow(["scan_idx", "l1_position", "l2_position", "l3_position", "l4_position"])
        w.writerows(expected_rows)

    print(f"Wrote stimulus: {stim_path}")
    print(f"Wrote expected: {expected_path}")


if __name__ == "__main__":
    main()
