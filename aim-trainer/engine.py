"""Self-contained aim-training simulation. No OS input or process access."""
from dataclasses import dataclass
import math
import random


@dataclass
class Target:
    identity: int
    x: float
    y: float
    vx: float
    vy: float
    generation: int = 0
    radius: float = 13

    @property
    def head(self):
        return self.x, self.y - 31


def smooth_axis(position, velocity, target, seconds, smooth_time=0.12, target_velocity=0):
    """Critically damped spring in the moving target's reference frame."""
    omega = 2 / smooth_time
    change = position - target
    relative_velocity = velocity - target_velocity
    temp = (relative_velocity + omega * change) * seconds
    decay = math.exp(-omega * seconds)
    return target + target_velocity * seconds + (change + temp) * decay, target_velocity + (relative_velocity - omega * temp) * decay


class Trainer:
    def __init__(self, width=1000, height=650, seed=None):
        self.width, self.height = width, height
        self.rng = random.Random(seed)
        self.targets = []
        self.base = [width / 2, height / 2]
        self.velocity = [0.0, 0.0]
        self.recoil = [0.0, 0.0]
        self.tracking_enabled = True
        self.auto_fire = True
        self.compensate = True
        self.search_radius = 260
        self.smooth_time = 0.12
        self.speed = 1.0
        self.shots = self.hits = self.headshots = self.kills = 0
        self.elapsed = 0.0
        self.duration = 60.0
        self.cooldown = 0.0
        self.dwell = 0.0
        self.locked = None
        self.paused = False
        self.tracers = []
        for identity in range(5):
            self.targets.append(self.spawn(identity))

    @property
    def crosshair(self):
        return (max(0, min(self.width, self.base[0] + self.recoil[0])),
                max(0, min(self.height, self.base[1] + self.recoil[1])))

    @property
    def finished(self):
        return self.elapsed >= self.duration

    @property
    def accuracy(self):
        return 100 * self.hits / self.shots if self.shots else 0.0

    def spawn(self, identity, generation=0):
        return Target(identity, self.rng.uniform(70, self.width - 70),
                      self.rng.uniform(115, self.height - 65),
                      self.rng.choice((-1, 1)) * self.rng.uniform(65, 145),
                      self.rng.choice((-1, 1)) * self.rng.uniform(25, 75), generation)

    def resize(self, width, height):
        if width < 300 or height < 250:
            return
        sx, sy = width / self.width, height / self.height
        self.base = [self.base[0] * sx, self.base[1] * sy]
        for target in self.targets:
            target.x = max(45, min(width - 45, target.x * sx))
            target.y = max(85, min(height - 45, target.y * sy))
        self.width, self.height = width, height

    def release(self):
        self.locked = None
        self.dwell = 0.0
        self.velocity = [0.0, 0.0]

    def select(self):
        x, y = self.crosshair
        candidates = []
        for target in self.targets:
            distance = math.hypot(target.head[0] - x, target.head[1] - y)
            if distance <= self.search_radius:
                candidates.append((distance, target))
        if not candidates:
            return None
        previous = next((target for _, target in candidates if (target.identity, target.generation) == self.locked), None)
        return previous or min(candidates, key=lambda pair: pair[0])[1]

    def fire(self):
        if self.paused or self.finished or self.cooldown > 1e-8:
            return False
        self.shots += 1
        self.cooldown = 0.15
        x, y = self.crosshair
        hit = None
        headshot = False
        # Match draw order: the last target is visually on top.
        for target in reversed(self.targets):
            hx, hy = target.head
            if math.hypot(x - hx, y - hy) <= target.radius:
                hit, headshot = target, True
                break
            if abs(x - target.x) <= 17 and target.y - 15 <= y <= target.y + 32:
                hit = target
                break
        if hit:
            self.hits += 1
            self.headshots += int(headshot)
            self.kills += 1
            index = self.targets.index(hit)
            self.targets[index] = self.spawn(hit.identity, hit.generation + 1)
            self.release()
        self.tracers.append([x, y, 0.16, bool(hit)])
        # Local reticle displacement only. Compensation never emits mouse input.
        scale = 0.12 if self.compensate else 1.0
        self.recoil[0] += self.rng.uniform(-5, 5) * scale
        self.recoil[1] -= self.rng.uniform(11, 17) * scale
        return bool(hit)

    def step(self, seconds, tracking=False, firing=False):
        if self.paused or self.finished:
            self.release()
            return
        if not math.isfinite(seconds) or seconds <= 0:
            return
        # Substeps keep tracking, cooldown and collisions stable across frame rates.
        remaining = min(seconds, self.duration - self.elapsed, 0.25)
        while remaining > 1e-8:
            dt = min(remaining, 1 / 120)
            remaining -= dt
            self.elapsed += dt
            self.cooldown = max(0, self.cooldown - dt)
            for tracer in self.tracers:
                tracer[2] -= dt
            self.tracers = [t for t in self.tracers if t[2] > 0]
            for target in self.targets:
                target.x += target.vx * self.speed * dt
                target.y += target.vy * self.speed * dt
                if target.x < 45 or target.x > self.width - 45:
                    target.x = max(45, min(self.width - 45, target.x))
                    target.vx = -target.vx
                if target.y < 85 or target.y > self.height - 45:
                    target.y = max(85, min(self.height - 45, target.y))
                    target.vy = -target.vy
            decay = math.exp(-(32 if self.compensate else 3) * dt)
            self.recoil = [v * decay for v in self.recoil]
            target = self.select() if tracking and self.tracking_enabled else None
            if target:
                key = (target.identity, target.generation)
                if key != self.locked:
                    self.velocity = [0.0, 0.0]
                    self.dwell = 0.0
                self.locked = key
                target_velocity = (target.vx * self.speed, target.vy * self.speed)
                desired = tuple(target.head[axis] - target_velocity[axis] * dt for axis in range(2))
                for axis in range(2):
                    self.base[axis], self.velocity[axis] = smooth_axis(
                        self.base[axis], self.velocity[axis], desired[axis], dt, self.smooth_time, target_velocity[axis])
                error = math.dist(self.crosshair, target.head)
                self.dwell = self.dwell + dt if error <= target.radius * 0.7 else 0.0
                if self.auto_fire and self.dwell >= 0.06 and self.cooldown <= 1e-8:
                    self.fire()
            else:
                self.release()
            if firing:
                self.fire()
