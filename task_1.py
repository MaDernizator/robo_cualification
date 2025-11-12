ZONE_SPEED = {"red":0.10, "yellow":0.50, "green":0.80}
ZONE_BORDERS = [ -168, -112, -56, 0, 56, 112, 168 ]  # границы J1 в градусах (соответствуют 180,150,120,60,30,0)

def zone_of_j1(j1_deg):
    # 0..±168: красные на краях, жёлтые рядом, зелёная в центре
    if abs(j1_deg) > 112: return "red"
    if abs(j1_deg) > 56:  return "yellow"
    return "green"

def nearest_border_between(a, b):
    lo, hi = (a, b) if a < b else (b, a)
    mids = [x for x in ZONE_BORDERS if lo < x < hi]
    return min(mids, key=lambda x: abs(x-a)) if mids else None

def rad2deg(r): return r*180/3.1415926535
def deg2rad(d): return d*3.1415926535/180

class SpeedGuard:
    def __init__(self, robot, safe_j2, safe_j3):
        self.r = robot
        self.safe_j2 = safe_j2
        self.safe_j3 = safe_j3

    def move_j1_guarded(self, j1_target_deg, max_step_deg=5):
        # едем по J1, автоматически меняя скорость по зонам
        j1_now = rad2deg(self.r.get_joint_angles()[0])
        direction = 1 if j1_target_deg > j1_now else -1

        while abs(j1_target_deg - j1_now) > 0.5:
            # ближайшая граница зоны на пути
            border = nearest_border_between(j1_now, j1_target_deg)
            # подцель = ближайшая граница или маленький шаг, что ближе
            candidate = j1_now + direction*max_step_deg
            sub_target = (
                border if (border is not None and
                           abs(border - j1_now) < abs(candidate - j1_now))
                else candidate
            )
            # не перелететь конечную
            if (direction > 0 and sub_target > j1_target_deg) or (direction < 0 and sub_target < j1_target_deg):
                sub_target = j1_target_deg

            vf = ZONE_SPEED[zone_of_j1(j1_now)]
            self.r.move_to_angles(deg2rad(sub_target), self.safe_j2, self.safe_j3,
                                  velocity_factor=vf, acceleration_factor=0.2)
            j1_now = rad2deg(self.r.get_joint_angles()[0])

    def move_waypoints_guarded(self, j1_sequence_deg):
        for j1_deg in j1_sequence_deg:
            self.move_j1_guarded(j1_deg)

# ---- пример использования ----
# guard = SpeedGuard(m, SAFE_J2, SAFE_J3)
# guard.move_j1_guarded(+168)     # вправо
# guard.move_waypoints_guarded([+100, +40, -20, -90, -168])  # произвольный маршрут по J1
