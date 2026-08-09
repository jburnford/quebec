"""Render Act II as a social-media video.

    python build/video_act2.py

Loads quebec-arrivals.html headless, steps the Act II animation
deterministically (one advance() per frame, so nothing ever stutters or drops
frames), screenshots each step, and encodes an H.264 MP4:

  cheap-bridge-act2.mp4    1920x1080, 30 fps, ~80 s: the full 23 seasons,
                           closing on the "record ends at the quay" card.

The page is captured at 1440x810 with a 2x device scale factor and downscaled
to 1080p, which renders all the type a third larger than desktop — sized for
a phone feed. Control buttons and the caption dismiss button are hidden for
the recording; the legend, timeline, clock and captions stay.

Requires playwright and av (PyAV). PyAV is used for the encode because it
carries FFmpeg as libraries inside Python — standalone ffmpeg.exe downloads
land under AppData, which managed machines block by group policy.
"""
import glob
import os
import shutil

import av
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(ROOT, "quebec-arrivals.html")
FRAMES = os.path.join(HERE, "_video_frames")
OUT = os.path.join(ROOT, "cheap-bridge-act2.mp4")

FPS = 30
MAIN_SECONDS = 75          # the 23 seasons
OUTRO_SECONDS = 5          # hold on the closing card
VIEW_W, VIEW_H = 1440, 810 # x2 DSF, downscaled to 1920x1080

SETUP_JS = """
() => {
  const st = document.createElement('style');
  st.textContent = [
    '#ctrls{display:none}',            // no buttons in a video
    '#noteX{display:none}',
    '#tip{display:none}',
    '#inter2Veil button{display:none}',// the end card is the outro
    '*{transition-duration:.1s !important}', // wall-clock fades vs stepped time
  ].join('');
  document.head.appendChild(st);
  setAct(2); playing = false; setPlayBtn();
  return VTMAX;
}
"""

STEP_JS = """
(t) => { advance(t); render(); paintUI(vt); }
"""


def main():
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES)

    n_main = MAIN_SECONDS * FPS
    n_outro = OUTRO_SECONDS * FPS

    with sync_playwright() as p:
        # managed machines often block executables under AppData (group
        # policy), which stops Playwright's own chromium — the system-installed
        # Edge or Chrome in Program Files is allowed, so try those first
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = p.chromium.launch(channel=channel)
                print(f"launched browser channel: {channel or 'bundled chromium'}")
                break
            except Exception as e:
                err = e
        if browser is None:
            raise err
        page = browser.new_page(viewport={"width": VIEW_W, "height": VIEW_H},
                                device_scale_factor=2)
        page.goto("file:///" + PAGE.replace(os.sep, "/"))
        vtmax = page.evaluate(SETUP_JS)
        print(f"VTMAX {vtmax:.0f}; {n_main + n_outro} frames "
              f"({MAIN_SECONDS}s + {OUTRO_SECONDS}s outro)")

        k = 0
        for i in range(n_main):
            page.evaluate(STEP_JS, vtmax * i / (n_main - 1))
            page.screenshot(path=os.path.join(FRAMES, f"f{k:05d}.png"))
            k += 1
            if k % 300 == 0:
                print(f"  {k}/{n_main + n_outro} frames")

        page.evaluate("() => document.getElementById('inter2Veil').classList.add('on')")
        for i in range(n_outro):
            page.screenshot(path=os.path.join(FRAMES, f"f{k:05d}.png"))
            k += 1
        browser.close()

    files = sorted(glob.glob(os.path.join(FRAMES, "f*.png")))
    out = av.open(OUT, "w")
    stream = out.add_stream("libx264", rate=FPS)
    stream.width, stream.height = 1920, 1080
    stream.pix_fmt = "yuv420p"
    # explicit bitrate: PyAV's libx264 wrapper ignores a crf option here and
    # encodes at an enormous default rate (a 75 s run came out at 143 MB)
    stream.bit_rate = 3_500_000
    stream.options = {"preset": "medium"}
    for i, f in enumerate(files):
        frame = next(av.open(f).decode(video=0))
        frame = frame.reformat(width=1920, height=1080, format="yuv420p",
                               interpolation=av.video.reformatter.Interpolation.LANCZOS)
        for pkt in stream.encode(frame):
            out.mux(pkt)
        if (i + 1) % 600 == 0:
            print(f"  encoded {i + 1}/{len(files)}")
    for pkt in stream.encode():
        out.mux(pkt)
    out.close()
    shutil.rmtree(FRAMES, ignore_errors=True)
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
