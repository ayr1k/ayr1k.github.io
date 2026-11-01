"""Regenerate the website font subsets from the original Sarasa UI SC fonts.

Requires fonttools and brotli. Run from website/:
  python scripts/subset-fonts.py /path/to/original-fonts
"""
import sys
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

source = Path(sys.argv[1])
root = Path(__file__).resolve().parents[1]
text = '\n'.join(path.read_text(encoding='utf-8-sig') for path in (root / 'src').rglob('*.jsx'))
text += (root / 'index.html').read_text(encoding='utf-8-sig')
text += ''.join(chr(i) for i in range(32, 127))
for weight in ('Regular', 'Bold'):
    font = TTFont(source / f'SarasaUiSC-{weight}.woff2')
    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = []
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    font.save(root / 'public/assets' / f'AmberWeb-{weight}.woff2')

