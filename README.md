# ASH Terminal V7.2 — Flying Candles

## Replay clarity
The old green replay labels meant only "signal fired." V7.2 now distinguishes outcome:

- GREEN: the strategy's underlying direction worked from 3:45 PM to the next-session open.
- RED: the direction failed over that interval.
- GRAY: outcome unavailable.

CALL worked = next open > 3:45 underlying price.
PUT worked = next open < 3:45 underlying price.

This is explicitly a directional underlying proxy, not historical option P&L.

Replay now shows signal count, worked count, missed count and directional hit rate.

## Flying candlestick intro
The storm objects are actual miniature candles with:
- variable body width and height
- independent upper/lower wick lengths
- mixed bullish/bearish bodies
- variable speed, direction and depth
- clockwise and counter-clockwise flight
- independent rotation / tumble
- lift, fall, radial drift and lateral gusts
- multi-frequency turbulence

They fly through the 2.5D storm while the camera pulls back/up into the eye.

## Three intro schemes
Settings -> Intro visual style:
1. Green / Red Candles
2. Classic White
3. Pink Glitter

The selection is stored locally and takes effect on the next launch.

## Upgrade
```bash
pkill -f "python app.py"
cd ~/storage/downloads/CEG_V7_2_FLYING_CANDLES
bash setup_termux.sh
bash start.sh
```

Open http://127.0.0.1:8765

Clear Chrome site data for 127.0.0.1 once if V7.1 remains cached.
