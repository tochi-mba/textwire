"""textwire: a text-mode web delivered over SMS.

The server half: it receives requests sent as SMS, fetches pages and runs searches on the
real internet, reduces them to text, compresses them and sends them back as numbered SMS
frames that the Android app reassembles.
"""

from importlib.metadata import version

__version__ = version("textwire")
