# Fonts

OFL-licensed fonts embedded in overlays and certificates (DESIGN 6). `pdf/text.py` loads them.

| File | Font | License |
| --- | --- | --- |
| `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | Noto Sans 2.015, static unhinted build from [notofonts/latin-greek-cyrillic](https://github.com/notofonts/latin-greek-cyrillic/releases/tag/NotoSans-v2.015) | `OFL-NotoSans.txt` |
| `NotoNaskhArabic-Regular.ttf` | Noto Naskh Arabic 2.021, static unhinted build from [notofonts/arabic](https://github.com/notofonts/arabic/releases/tag/NotoNaskhArabic-v2.021) | `OFL-NotoNaskhArabic.txt` |

Typed signatures are drawn in the browser and reach the server as images, so their script fonts live in the frontend (P1.14).
