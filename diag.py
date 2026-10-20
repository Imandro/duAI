import sys
sys.path.insert(0,'.')
from duai.ui import theme
orig = theme.render_css
def fixed(mode=None, accent=None):
    css = orig(mode, accent)
    css = css.replace('}  # texto negro sobre fondo blanco de botones', '}')
    return css
theme.render_css = fixed
from PySide6.QtWidgets import QApplication, QCheckBox, QWidget, QVBoxLayout
app = QApplication(sys.argv)
from duai.ui.theme import apply_theme
apply_theme(app, 'oscuro')
app.setStyleSheet(fixed('oscuro'))
w = QWidget()
l = QVBoxLayout(w)
c = QCheckBox('test')
c.setChecked(True)
l.addWidget(c)
w.show()
app.processEvents()
pix = c.grab()
img = pix.toImage()
# find indicator: first column with many whites
for x in range(30):
    wc = sum(1 for y in range(img.height()) if img.pixelColor(x,y).name().lower()=='#ffffff')
    if wc > 5:
        print('first white col', x, 'count', wc)
        break
# assume indicator at x..x+18, y..y+18 where y offset
# find y start
for y in range(img.height()):
    if img.pixelColor(x,y).name().lower()=='#ffffff':
        y0=y; break
print('y0', y0)
# count colors in 18x18 square
from collections import Counter
cnt=Counter()
for yy in range(y0, y0+18):
    for xx in range(x, x+18):
        cnt[img.pixelColor(xx,yy).name().lower()]+=1
print('indicator square colors:', cnt.most_common())
