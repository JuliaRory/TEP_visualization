def get_time_scale_step(value):
    value = abs(float(value))
    if value <= 10:
        return 1
    if value <= 100:
        return 10
    return 25


def get_voltage_scale_step(value):
    value = abs(float(value))
    if value <= 10:
        return 1
    if value <= 50:
        return 5
    if value <= 100:
        return 10
    return 25


def get_time_ticks(max_time):   
    # max_time: [ms]
    # Returns: d_time [ms]
    return get_time_scale_step(max_time)

def get_voltage_ticks(amp, n_tick=4):
    amp = abs(float(amp))
    if amp <= 0:
        return 1
    return get_voltage_scale_step(amp)
