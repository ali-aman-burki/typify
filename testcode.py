from typify.progbar import IndeterminateProgressBar
import time

bar = IndeterminateProgressBar(prefix="Loading", suffix="Please wait...")
bar.start()

# Simulate work
time.sleep(5)

bar.set_suffix("Almost done...")
time.sleep(2)

bar.done()  # Will instantly fill and finish
