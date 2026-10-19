"""Projection and view-direction mathematics, independent of Windows."""
import math


def project(point, matrix, width, height):
    if len(matrix) != 16 or not all(math.isfinite(x) for x in (*point, *matrix)):
        return None
    x, y, z = point
    w = matrix[12] * x + matrix[13] * y + matrix[14] * z + matrix[15]
    if w <= 0.01:
        return None
    cx = matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3]
    cy = matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7]
    return (width * (1 + cx / w) / 2, height * (1 - cy / w) / 2)


def look_endpoint(eye, pitch, yaw, length):
    p, y = math.radians(pitch), math.radians(yaw)
    forward = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p))
    return tuple(a + length * b for a, b in zip(eye, forward))


def player_box(origin, eye, matrix, width, height):
    feet = project(origin, matrix, width, height)
    head = project((eye[0], eye[1], eye[2] + 8), matrix, width, height)
    if feet is None or head is None:
        return None
    size = feet[1] - head[1]
    if not 3 <= size <= height * 4:
        return None
    half = size * 0.23
    return feet[0] - half, head[1], feet[0] + half, feet[1]
