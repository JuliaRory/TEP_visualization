import math
from typing import Iterable, Tuple

def quatToYPR_ZYX_xyzw(
    q: Iterable[float],
    *,
    degrees: bool = True,
    inverse: bool = False,
    wrap_yaw_roll: bool = False
) -> Tuple[float, float, float]:
    """
    Convert quaternion q = [x, y, z, w] (scalar-last) to Euler angles (ZYX: yaw, pitch, roll)
    in a right-handed head frame (X forward, Y left, Z up).

    Assumes quaternion represents coil->head rotation (v_head = R * v_coil).
    If your quaternion is the opposite (head->coil), set inverse=True (uses conjugate).

    Returns: (yaw, pitch, roll) where:
      yaw   = rotation about +Z
      pitch = rotation about +Y
      roll  = rotation about +X
    """
    q = list(q)
    if len(q) != 4:
        raise ValueError("q must have 4 elements [x, y, z, w]")

    x, y, z, w = q

    # If quaternion maps head->coil (inverse of what we want), conjugate it:
    if inverse:
        x, y, z = -x, -y, -z

    # Normalize
    n = math.sqrt(x*x + y*y + z*z + w*w)
    if n == 0:
        raise ValueError("Zero-norm quaternion")
    x, y, z, w = x/n, y/n, z/n, w/n

    # Rotation matrix elements for q = [x y z w]
    R11 = 1 - 2*(y*y + z*z)
    R12 = 2*(x*y - w*z)
    R13 = 2*(x*z + w*y)

    R21 = 2*(x*y + w*z)
    R22 = 1 - 2*(x*x + z*z)
    R23 = 2*(y*z - w*x)

    R31 = 2*(x*z - w*y)
    R32 = 2*(y*z + w*x)
    R33 = 1 - 2*(x*x + y*y)

    # ZYX Euler angles: yaw (Z), pitch (Y), roll (X)
    yaw = math.atan2(R21, R11)

    s = -R31
    if s > 1.0:
        s = 1.0
    elif s < -1.0:
        s = -1.0
    pitch = math.asin(s)

    roll = math.atan2(R32, R33)

    if degrees:
        yaw = yaw * 180.0 / math.pi
        pitch = pitch * 180.0 / math.pi
        roll = roll * 180.0 / math.pi

    if wrap_yaw_roll:
        # Wrap to (-180, 180]
        def wrap(a: float) -> float:
            return (a + 180.0) % 360.0 - 180.0
        yaw = wrap(yaw)
        roll = wrap(roll)

    return yaw, pitch, roll

q1 = [-0.076, 0.127, -0.712, 0.687]     # от затылка к носу ровно на макушке            yaw=-92.60158262500418, pitch=3.7968952988216076, roll=-16.59865423475317
q2 = [-.513, -.275, -.546, .603]        # от затылка к носу параллельно виску           yaw=-56.083596238305276, pitch=-63.04759881511473, roll=-44.593233057114695
q3 = [-.169, .003, -.984, -.054]        # от левого к правому уху ровно на макушке      yaw=173.58910433086442, pitch=-19.451081114759074, roll=0.7505265419241994
q4 = [-.348, -.141, -.848, .374]        # М1 45 градусов (из левого уха к носу)         yaw=-131.71767238445116, pitch=-44.08305231688747, roll=-1.6887107109431876
q5 = [-.218, -.289, -.854, -.374]       # М1 -45 градусов (из левого глаза к затылку)   yaw=129.27570894281556, pitch=-8.982628224567891, roll=41.65717672653023

import numpy as np

for q in [q1, q2, q3, q4, q5]:
    q = np.array(q)
    # print(np.sum([value*value for value in q]))
    # print(q)
    yaw, pitch, roll = quatToYPR_ZYX_xyzw(q, inverse=True)
    print("yaw={}, pitch={}, roll={}".format(yaw, pitch, roll))

# yaw, pitch, roll = quatToYPR_ZYX_xyzw(q)
# print("yaw={}, pitch={}, roll={}".format(yaw, pitch, roll))



# Returns: (yaw, pitch, roll) where:
#       yaw   = rotation about +Z
#       pitch = rotation about +Y
#       roll  = rotation about +X