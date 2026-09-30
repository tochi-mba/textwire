# On-device acceptance

The only place this repository makes claims about a real phone on a real network. Each line
records the date it was observed, how long it took, how many SMS it used, and what Twilio
charged. A line without a date has not been observed.

Device: Samsung Galaxy S21 Ultra (SM-G998B), Android 15, UK carrier.

| # | Check | Date | Result | Time | SMS | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Mobile data and Wi-Fi off; a browser loads nothing. | | | | | |
| 2 | Diagnostics, Send probe (`?`): the status arrives. | | | | | |
| 3 | Search `bbc weather london`: results within 60 s; tap result 1: page 1 within 3 min. | | | | | |
| 4 | Next page, back, and a link chip inside the article. | | | | | |
| 5 | A URL longer than 160 characters as a `g` request. | | | | | |
| 6 | Server started with `TEXTWIRE_DEBUG_DROP_ONCE=3`: the app asks for frame 3 after 60 s and completes. | | | | | |
| 7 | Server budget set to 20: a request is refused with `E budget`. | | | | | |
| 8 | App killed while frames arrive; reopened: the page completes from storage. | | | | | |
| 9 | Plain mode from Samsung Messages (`s! weather london`) alongside the app. | | | | | |
| 10 | Alphabet probe (`textwire probe`): Diagnostics shows the frame decoded with no CRC error. | | | | | |
