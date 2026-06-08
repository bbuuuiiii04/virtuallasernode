"""
VirtualLaserNode — virtual Art-Net node + ArtDMX inspector for SoundSwitch.

Renders SoundSwitch's DMX laser output on screen with no Enttec hardware or
physical lasers. Run with:  python3 -m virtuallasernode --web

Package layout:
    artnet.py     Art-Net node, ArtPollReply, UDP receiver, UniverseState
    fixtures.py   fixture patch + (step 5) 36CH profile decoder
    webserver.py  HTTP + SSE inspector server
    static/       browser inspector (index.html / app.js / style.css)
    __main__.py   CLI + wiring
"""

__version__ = "0.5.0"
