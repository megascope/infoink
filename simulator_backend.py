import io
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw

LOGGER = logging.getLogger(__name__)


def landscape_to_raw_touch(x, y, display_width, display_height):
    return (display_height - 1) - y, (display_width - 1) - x


class SimulatorState:
    def __init__(self, display_width, display_height, up_button, down_button):
        self.lock = threading.Lock()
        self.pending_touches = []
        self.frame_png = b""
        self.display_width = display_width
        self.display_height = display_height
        self.up_button = up_button
        self.down_button = down_button
        self.set_landscape_image(Image.new("1", (display_width, display_height), 255))

    def set_landscape_image(self, image):
        with self.lock:
            out = image.convert("L").resize((self.display_width * 2, self.display_height * 2), Image.NEAREST)
            draw = ImageDraw.Draw(out)
            draw.rectangle((0, 0, out.width - 1, out.height - 1), outline=0, width=1)
            buffer = io.BytesIO()
            out.save(buffer, format="PNG")
            self.frame_png = buffer.getvalue()

    def get_frame_png(self):
        with self.lock:
            return self.frame_png

    def enqueue_touch_for_button(self, button_name):
        if button_name == "up":
            x = (self.up_button[0] + self.up_button[2]) // 2
            y = (self.up_button[1] + self.up_button[3]) // 2
        elif button_name == "down":
            x = (self.down_button[0] + self.down_button[2]) // 2
            y = (self.down_button[1] + self.down_button[3]) // 2
        else:
            return

        raw_x, raw_y = landscape_to_raw_touch(x, y, self.display_width, self.display_height)
        with self.lock:
            self.pending_touches.append((raw_x, raw_y))

    def pop_touch(self):
        with self.lock:
            if self.pending_touches:
                return self.pending_touches.pop(0)
            return None

    def has_pending_touch(self):
        with self.lock:
            return bool(self.pending_touches)


class SimulatorServer:
    def __init__(self, host, port, state):
        self._state = state
        self._host = host
        self._port = port
        self._httpd = None
        self._thread = None

    def start(self):
        state = self._state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    html = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"> 
  <title>E-Paper Simulator</title>
  <style>
    body { font-family: sans-serif; margin: 16px; background: #f3f3f3; }
    .wrap { display: flex; gap: 16px; align-items: flex-start; }
    .panel { background: #fff; border: 1px solid #ccc; padding: 12px; border-radius: 8px; }
    button { font-size: 16px; padding: 10px 14px; margin-bottom: 8px; width: 80px; }
  </style>
</head>
<body>
  <h3>Waveshare 2.13 V4 Simulator</h3>
  <div class=\"wrap\">
    <div class=\"panel\">
      <img id=\"frame\" src=\"/frame.png\" alt=\"display\"> 
    </div>
    <div class=\"panel\">
      <button onclick=\"touch('up')\">UP</button><br>
      <button onclick=\"touch('down')\">DOWN</button>
    </div>
  </div>
  <script>
    function refreshFrame() {
      document.getElementById('frame').src = '/frame.png?t=' + Date.now();
    }
    async function touch(button) {
      await fetch('/touch?button=' + button, { method: 'POST' });
      setTimeout(refreshFrame, 80);
    }
    setInterval(refreshFrame, 400);
  </script>
</body>
</html>
"""
                    body = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if parsed.path == "/frame.png":
                    body = state.get_frame_png()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path != "/touch":
                    self.send_response(404)
                    self.end_headers()
                    return

                params = parse_qs(parsed.query)
                button = params.get("button", [""])[0]
                state.enqueue_touch_for_button(button)

                body = b"ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *args):
                return

        self._httpd = ThreadingHTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        LOGGER.info("Simulator available at http://%s:%s", self._host, self._port)

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


class MockGTDevelopment:
    def __init__(self):
        self.Touch = 0
        self.TouchpointFlag = 0
        self.TouchCount = 0
        self.Touchkeytrackid = [0, 1, 2, 3, 4]
        self.X = [0, 1, 2, 3, 4]
        self.Y = [0, 1, 2, 3, 4]
        self.S = [0, 1, 2, 3, 4]


class MockGT1151:
    INT = 27

    def __init__(self, state):
        self._state = state

    def GT_Init(self):
        return

    def digital_read(self, pin):
        if pin != self.INT:
            return 1
        return 0 if self._state.has_pending_touch() else 1

    def GT_Scan(self, gt_dev, gt_old):
        if gt_dev.Touch != 1:
            return

        gt_dev.Touch = 0
        touch = self._state.pop_touch()
        if touch is None:
            gt_dev.TouchpointFlag = 0
            return

        raw_x, raw_y = touch
        gt_old.X[0] = gt_dev.X[0]
        gt_old.Y[0] = gt_dev.Y[0]
        gt_old.S[0] = gt_dev.S[0]

        gt_dev.TouchpointFlag = 0x80
        gt_dev.TouchCount = 1
        gt_dev.X[0] = raw_x
        gt_dev.Y[0] = raw_y
        gt_dev.S[0] = 24


class MockEPD:
    FULL_UPDATE = 0
    PART_UPDATE = 1

    def __init__(self, state, display_width, display_height):
        self.width = 122
        self.height = 250
        self._state = state
        self._display_width = display_width
        self._display_height = display_height

    def init(self, update):
        return 0

    def Clear(self, color):
        fill = 255 if color else 0
        self._state.set_landscape_image(Image.new("1", (self._display_width, self._display_height), fill))

    def getbuffer(self, image):
        img = image
        imwidth, imheight = img.size
        if imwidth == self.width and imheight == self.height:
            img = img.rotate(180, expand=True).convert("1")
        elif imwidth == self.height and imheight == self.width:
            img = img.rotate(270, expand=True).convert("1")
        else:
            return [0x00] * (int(self.width / 8) * self.height)

        return bytearray(img.tobytes("raw"))

    def _show_buffer(self, image_buffer):
        panel = Image.frombytes("1", (self.width, self.height), bytes(image_buffer))
        landscape = panel.rotate(90, expand=True)
        self._state.set_landscape_image(landscape)

    def displayPartBaseImage(self, image):
        self._show_buffer(image)

    def displayPartial(self, image):
        self._show_buffer(image)

    def displayPartial_Wait(self, image):
        self._show_buffer(image)

    def display(self, image):
        self._show_buffer(image)

    def sleep(self):
        return

    def Dev_exit(self):
        return


def create_simulator_runtime(host, port, display_width, display_height, up_button, down_button):
    state = SimulatorState(display_width, display_height, up_button, down_button)
    server = SimulatorServer(host, port, state)
    server.start()

    epd = MockEPD(state, display_width, display_height)
    gt = MockGT1151(state)
    gt_dev = MockGTDevelopment()
    gt_old = MockGTDevelopment()
    return epd, gt, gt_dev, gt_old, server
