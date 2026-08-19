

def get_time_ticks(max_time):   
    # max_time: [ms]
    # Returns: d_time [ms]
    if max_time >= 40:
        return 10
    elif max_time >=20:
        return 5
    else:
        return 2

def get_voltage_ticks(amp, n_tick=4):
    amp = abs(float(amp))
    n_tick = max(1, int(n_tick))
    if amp <= 0:
        return 1
    return amp / n_tick
