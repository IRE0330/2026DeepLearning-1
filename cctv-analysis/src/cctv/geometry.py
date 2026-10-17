"""Small dependency-free geometry helpers. Coordinates may be normalized."""
import math


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def line_distance(p, line):
    a, b = line
    return cross(a, b, p) / math.dist(a, b)


def on_segment(p, a, b):
    return (abs(cross(a, b, p)) < 1e-9 and
            min(a[0], b[0]) - 1e-9 <= p[0] <= max(a[0], b[0]) + 1e-9 and
            min(a[1], b[1]) - 1e-9 <= p[1] <= max(a[1], b[1]) + 1e-9)


def segments_intersect(a, b, c, d):
    x, y, z, w = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    if x * y < 0 and z * w < 0:
        return True
    return any((abs(v) < 1e-9 and on_segment(p, u, q)) for v, p, u, q in
               ((x, c, a, b), (y, d, a, b), (z, a, c, d), (w, b, c, d)))


def in_polygon(p, poly):
    if not poly:
        return False
    inside = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if on_segment(p, a, b):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < x:
                inside = not inside
    return inside


def validate_points(points, count=None):
    if not isinstance(points, list) or (count is not None and len(points) != count):
        raise ValueError(f"좌표는 {count or '3개 이상'}의 점 배열이어야 합니다.")
    for p in points:
        if (not isinstance(p, list) or len(p) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) or not 0 <= v <= 1 for v in p)):
            raise ValueError("좌표는 0~1 범위의 유한한 [x, y] 값이어야 합니다.")


def validate_polygon(poly):
    validate_points(poly)
    if len(poly) < 3 or len(set(map(tuple, poly))) != len(poly):
        raise ValueError("다각형에는 서로 다른 점 3개 이상이 필요합니다.")
    edges = list(zip(poly, poly[1:] + poly[:1]))
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) / 2
    if area < 1e-6:
        raise ValueError("다각형 면적이 너무 작습니다.")
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if segments_intersect(a, b, c, d):
                raise ValueError("다각형 변이 교차합니다. 점을 둘레 순서로 지정하세요.")
