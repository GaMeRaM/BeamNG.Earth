"""Attach embedded tracks and sidewalks to the road deck they actually share."""
import numpy as np
import roads


def levels(cells):
    out = {}
    for f in cells:
        if f is None:
            continue
        for i, fid in enumerate(f.ids):
            value = roads._rule_value(f.rules.get('level'), i)
            out[str(fid)] = float(value) if value is not None and np.isfinite(value) else 1.
    return out


def surface(xy, decks, half, level=1., reach=2., overlap_mask=False):
    """(surface Z, fully covered) for a parallel same-level companion, else None.

    Crossings and other levels never attach. Every sampled point must have a
    nearby parallel deck, so a path which only crosses a bridge stays independent.
    overlap_mask returns a per-point footprint-overlap mask for trimming walks.
    """
    xy = np.asarray(xy, np.float64)[:, :2]
    if len(xy) < 2:
        return None
    tangent = np.gradient(xy, axis=0)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1)[:, None], 1e-9)
    best = np.full(len(xy), np.inf)
    z = np.full(len(xy), np.nan)
    covered = np.zeros(len(xy), bool)
    for deck in decks:
        if abs(float(deck.get('level', 1.)) - level) > .1:
            continue
        line = np.asarray(deck['n'], np.float64)
        for a, b in zip(line[:-1], line[1:]):
            d = b[:2] - a[:2]
            length = float(np.linalg.norm(d))
            if length < 1e-6:
                continue
            u = d / length
            raw_along = (xy - a[:2]) @ u
            along = np.clip(raw_along, 0., length)
            distance = np.linalg.norm(xy - (a[:2] + along[:, None] * u), axis=1)
            width = float(deck['w']) / 2
            ok = (np.abs(tangent @ u) > .966) & (distance <= width + half + reach) & (distance < best)
            z[ok] = a[2] + along[ok] / length * (b[2] - a[2])
            covered[ok] = ((distance[ok] + (-half if overlap_mask else half) <= width + .05)
                           & (raw_along[ok] >= -.05) & (raw_along[ok] <= length + .05))
            best[ok] = distance[ok]
    return (z, covered if overlap_mask else bool(covered.all())) if np.isfinite(z).all() else None
