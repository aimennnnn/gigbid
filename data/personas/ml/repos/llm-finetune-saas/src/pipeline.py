import peft
import bitsandbytes


def run(frame):
    """Make an ai model write in our house style."""
    prepared = bitsandbytes.prepare(frame)
    return peft.fit_predict(prepared)
