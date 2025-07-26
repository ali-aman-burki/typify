#testing
import sys
import time

class ProgressBar:
    def __init__(self, total, length=40, fill='█', empty='-', prefix='', suffix='', decimals=1):
        self.total = total              # Total iterations
        self.length = length            # Length of the progress bar (in characters)
        self.fill = fill                # Character to show completed progress
        self.empty = empty              # Character to show remaining progress
        self.prefix = prefix            # Optional text before the bar
        self.suffix = suffix            # Optional text after the bar
        self.decimals = decimals        # Number of decimals to show in percentage
        self.iteration = 0              # Current iteration

    def update(self, iteration=None):
        if iteration is not None:
            self.iteration = iteration
        else:
            self.iteration += 1

        percent = f"{100 * (self.iteration / float(self.total)):.{self.decimals}f}"
        filled_len = int(self.length * self.iteration // self.total)
        bar = self.fill * filled_len + self.empty * (self.length - filled_len)

        # Print the progress bar with carriage return to overwrite the line
        print(f'\r{self.prefix} |{bar}| {percent}% {self.suffix}', end='', file=sys.stdout)

        # Print newline when complete
        if self.iteration >= self.total:
            print(file=sys.stdout)

    def finish(self):
        self.iteration = self.total
        self.update()

# Example usage:
if __name__ == '__main__':
    total = 100
    pb = ProgressBar(total, prefix='Progress', suffix='Complete', length=50)
    for i in range(total):
        time.sleep(0.02)  # Simulate work
        pb.update(i + 1)
