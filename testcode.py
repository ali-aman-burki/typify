from typify.progbar import ProgressBar
import time

p = ProgressBar(total=10, prefix="Hello")
p.display()

for i in range(5):
    p.update()
    time.sleep(0.5)