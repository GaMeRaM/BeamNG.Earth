#!/usr/bin/env python3
"""Lane arrow masks based on GOST R 51256-2018, fig. B.5/table B.1.

Two speed profiles, seven directions each. Deterministic, supersampled opacity;
run mod_textures_dds.py on the output to update the packaged WebP source.
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
KINDS = ('left', 'right', 'through', 'left_through', 'right_through', 'left_right', 'left_right_through')
CELL = 128


def dimensions(kind, high=False):
    length = 7.5 if high else 5.0
    if kind == 'left_right_through':
        length += 2.05
    return length + .3, 2.4  # transparent border; glyph dimensions exclude it


def build():
    scale = 4
    atlas = Image.new('L', (CELL * 4 * scale, CELL * 4 * scale))
    d = ImageDraw.Draw(atlas)
    for high in (False, True):
        L = 7.5 if high else 5.0
        a1, a2, b, d2 = (1.2, 1.3, .5, 4.6) if high else (.7, .8, .5, 2.6)
        for i, kind in enumerate(KINDS):
            index = i + 7 * high
            x, y = index % 4 * CELL * scale, index // 4 * CELL * scale
            length, width = dimensions(kind, high)
            def polygon(points):
                d.polygon([(x + round((.5 - px / width) * CELL * scale),
                            y + round((1 - (py + .15) / length) * CELL * scale))
                           for px, py in points], fill=255)
            triple = kind == 'left_right_through'
            # Shaft 0.15 m, straight head 0.75 m wide and 2.05 m long.
            tip = L + (2.05 if triple else 0)
            polygon([(-.075, 0), (.075, 0), (.075, d2 + .15), (-.075, d2 + .15)])
            if 'through' in kind:
                polygon([(-.075, 0), (.075, 0), (.075, tip-2.05),
                         (.375, tip-2.05), (0, tip), (-.375, tip-2.05), (-.075, tip-2.05)])
            # Angled turn head (45 degrees), lateral extent 1.05 m from
            # the stem's outer edge; shared stem for combined directions.
            turn = [(-.075,d2), (.675,d2+a1), (.675,L),
                    (1.125,d2+a1+b), (.375,d2), (.075,d2-.3)]
            if 'left' in kind:
                polygon(turn)
            if 'right' in kind:
                polygon([(-px,py) for px,py in turn])
    return atlas.resize((CELL*4, CELL*4), Image.Resampling.LANCZOS)


def main():
    p = ROOT/'mod/beamng_earth/levels/beamng_earth/art/roadmarkings/bne_ru_arrows.data.png'
    p.parent.mkdir(parents=True, exist_ok=True)
    build().save(p)
    print(p)


if __name__ == '__main__':
    main()
