#!/usr/bin/python3
# -*- coding:utf-8 -*-
import argparse
import datetime
import fcntl
import logging
import os
import socket
import struct
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

from simulator_backend import create_simulator_runtime

fontdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "pic")
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
if os.path.exists(libdir):
    sys.path.append(libdir)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 5
FULL_REFRESH_EVERY_N_UPDATES = 30
NETWORK_CACHE_TTL_SECONDS = 60
ADMIN_PAGE_INDEX = 3
PAGES = ("IP Addresses", "Wi-Fi", "Clock", "Admin")

DISPLAY_WIDTH = 250
DISPLAY_HEIGHT = 122
SIDEBAR_X0 = 220
UP_BUTTON = (223, 8, 247, 56)
DOWN_BUTTON = (223, 66, 247, 114)
TOUCH_DEBOUNCE_SECONDS = 0.25
TOUCH_POLL_IDLE_SECONDS = 0.12
TOUCH_POLL_ACTIVE_SECONDS = 0.03
ADMIN_CONFIRM_WINDOW_SECONDS = 5.0

ADMIN_REBOOT_BUTTON = (14, 36, 110, 54)
ADMIN_SHUTDOWN_BUTTON = (14, 74, 110, 92)
ADMIN_CONFIRM_BUTTON = (222, 40, 248, 82)

_IP_CACHE = {"updated_at": 0.0, "value": []}
_WIFI_CACHE = {"updated_at": 0.0, "value": []}


def get_non_loopback_ipv4():
    addresses = []
    for _, ifname in socket.if_nameindex():
        if ifname == "lo":
            continue

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            req = struct.pack("256s", ifname[:15].encode("utf-8"))
            ip = socket.inet_ntoa(fcntl.ioctl(sock.fileno(), 0x8915, req)[20:24])
            if not ip.startswith("127."):
                addresses.append((ifname, ip))
        except OSError:
            continue
        finally:
            sock.close()

    addresses.sort(key=lambda item: item[0])
    return addresses


def get_connected_wifi_networks():
    wifi_links = []
    net_dir = "/sys/class/net"
    try:
        interfaces = sorted(os.listdir(net_dir))
    except OSError:
        return wifi_links

    for ifname in interfaces:
        if not os.path.isdir(os.path.join(net_dir, ifname, "wireless")):
            continue

        ssid = ""
        try:
            ssid = subprocess.check_output(
                ["iwgetid", ifname, "--raw"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            ssid = ""

        if not ssid:
            try:
                link_out = subprocess.check_output(
                    ["iw", "dev", ifname, "link"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                for line in link_out.splitlines():
                    line = line.strip()
                    if line.startswith("SSID:"):
                        ssid = line.split(":", 1)[1].strip()
                        break
            except (FileNotFoundError, subprocess.CalledProcessError):
                ssid = ""

        if ssid:
            wifi_links.append((ifname, ssid))

    return wifi_links


def get_non_loopback_ipv4_cached(now_mono):
    if (now_mono - _IP_CACHE["updated_at"]) >= NETWORK_CACHE_TTL_SECONDS:
        _IP_CACHE["value"] = get_non_loopback_ipv4()
        _IP_CACHE["updated_at"] = now_mono
    return _IP_CACHE["value"]


def get_connected_wifi_networks_cached(now_mono):
    if (now_mono - _WIFI_CACHE["updated_at"]) >= NETWORK_CACHE_TTL_SECONDS:
        _WIFI_CACHE["value"] = get_connected_wifi_networks()
        _WIFI_CACHE["updated_at"] = now_mono
    return _WIFI_CACHE["value"]


def load_font(size):
    for name in ("Roboto-Regular.ttf", "Font.ttc"):
        path = os.path.join(fontdir, name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_sidebar(draw, font_button, show_confirm=False):
    draw.rectangle((SIDEBAR_X0, 0, DISPLAY_WIDTH - 1, DISPLAY_HEIGHT - 1), outline=0, fill=255, width=1)
    draw.text((223, 1), "MENU", font=font_button, fill=0)

    if show_confirm:
        draw.rectangle(ADMIN_CONFIRM_BUTTON, outline=0, fill=255, width=1)
        draw.text((224, 50), "CONF", font=font_button, fill=0)
        draw.text((225, 62), "IRM", font=font_button, fill=0)
    else:
        draw.rectangle(UP_BUTTON, outline=0, fill=255, width=1)
        draw.polygon([(235, 16), (229, 26), (241, 26)], fill=0)
        draw.text((229, 32), "UP", font=font_button, fill=0)

        draw.rectangle(DOWN_BUTTON, outline=0, fill=255, width=1)
        draw.polygon([(235, 106), (229, 96), (241, 96)], fill=0)
        draw.text((225, 72), "DOWN", font=font_button, fill=0)


def build_frame(page, font_title, font_body, font_button, armed_admin_action="", armed_seconds_left=0):
    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
    draw = ImageDraw.Draw(image)

    now = datetime.datetime.now()
    draw.rectangle((0, 0, SIDEBAR_X0 - 1, DISPLAY_HEIGHT - 1), outline=0, fill=255, width=1)
    draw.text((4, 4), PAGES[page], font=font_title, fill=0)
    draw.line((2, 21, SIDEBAR_X0 - 3, 21), fill=0, width=1)
    draw.line((2, 28, SIDEBAR_X0 - 3, 28), fill=0, width=1)

    now_mono = time.monotonic()
    if page == 0:
        rows = [f"{ifname}: {ip}" for ifname, ip in get_non_loopback_ipv4_cached(now_mono)]
        if not rows:
            rows = ["No non-loopback", "IPv4 addresses"]
    elif page == 1:
        rows = [f"{ifname}: {ssid}" for ifname, ssid in get_connected_wifi_networks_cached(now_mono)]
        if not rows:
            rows = ["No connected Wi-Fi", "networks detected"]
    elif page == 2:
        rows = [now.strftime("%H:%M:%S"), now.strftime("%Y-%m-%d")]
    else:
        rows = []

    if page == ADMIN_PAGE_INDEX:
        draw.rectangle(ADMIN_REBOOT_BUTTON, outline=0, fill=255, width=1)
        draw.text((22, 40), "Reboot", font=font_button, fill=0)

        draw.rectangle(ADMIN_SHUTDOWN_BUTTON, outline=0, fill=255, width=1)
        draw.text((22, 78), "Shutdown", font=font_button, fill=0)
        if armed_admin_action:
            confirm_label = "REBOOT" if armed_admin_action == "reboot" else "SHUTDOWN"
            draw.text((8, 102), f"Tap CONFIRM at right ({armed_seconds_left}s)", font=font_button, fill=0)
            draw.text((8, 112), f"Armed: {confirm_label}", font=font_button, fill=0)
    else:
        y = 36
        for row in rows:
            draw.text((4, y), row, font=font_title if page == 2 else font_body, fill=0)
            y += 24 if page == 2 else 14
            if y > DISPLAY_HEIGHT - 4:
                break

    draw_sidebar(draw, font_button, show_confirm=(page == ADMIN_PAGE_INDEX and bool(armed_admin_action)))
    return image


def is_inside(rect, x, y):
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1


def raw_touch_to_landscape(raw_x, raw_y):
    # getbuffer() rotates landscape images by 270 degrees to panel space.
    # Inverse-map raw panel touch back into landscape display coordinates.
    return (DISPLAY_WIDTH - 1) - raw_y, (DISPLAY_HEIGHT - 1) - raw_x


def create_runtime(simulator, simulator_host, simulator_port):
    if simulator:
        return create_simulator_runtime(
            simulator_host,
            simulator_port,
            DISPLAY_WIDTH,
            DISPLAY_HEIGHT,
            UP_BUTTON,
            DOWN_BUTTON,
        )

    from TP_lib import epd2in13_V4, gt1151

    epd = epd2in13_V4.EPD()
    gt = gt1151.GT1151()
    gt_dev = gt1151.GT_Development()
    gt_old = gt1151.GT_Development()
    return epd, gt, gt_dev, gt_old, None


def trigger_admin_action(action):
    if action == "reboot":
        LOGGER.warning("Running: sudo reboot")
        subprocess.Popen(["sudo", "reboot"])
    elif action == "shutdown":
        LOGGER.warning("Running: sudo shutdown -h now")
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])


def run(simulator=False, simulator_host="127.0.0.1", simulator_port=8765):
    epd, gt, gt_dev, gt_old, sim_server = create_runtime(simulator, simulator_host, simulator_port)

    font_title = load_font(14)
    font_body = load_font(12)
    font_button = load_font(10)

    update_count = 0
    current_page = 0
    force_redraw = True
    next_update_at = 0.0
    last_page_touch = 0.0
    touch_latched = False
    armed_admin_action = ""
    armed_admin_expires_at = 0.0

    try:
        if simulator:
            LOGGER.info("Initializing simulator-backed display + touch")
        else:
            LOGGER.info("Initializing Waveshare 2.13 V4 display + touch")

        epd.init(epd.FULL_UPDATE)
        gt.GT_Init()
        epd.Clear(0xFF)

        base_image = build_frame(current_page, font_title, font_body, font_button)
        epd.displayPartBaseImage(epd.getbuffer(base_image))
        epd.init(epd.PART_UPDATE)
        next_update_at = time.monotonic()

        while True:
            now = time.monotonic()

            if now >= next_update_at or force_redraw:
                seconds_left = 0
                if armed_admin_action:
                    seconds_left = max(0, int(armed_admin_expires_at - now))
                image = build_frame(
                    current_page,
                    font_title,
                    font_body,
                    font_button,
                    armed_admin_action=armed_admin_action if current_page == ADMIN_PAGE_INDEX else "",
                    armed_seconds_left=seconds_left,
                )
                update_count += 1

                if update_count >= FULL_REFRESH_EVERY_N_UPDATES:
                    epd.init(epd.FULL_UPDATE)
                    epd.displayPartBaseImage(epd.getbuffer(image))
                    epd.init(epd.PART_UPDATE)
                    update_count = 0
                else:
                    epd.displayPartial_Wait(epd.getbuffer(image))

                next_update_at = now + UPDATE_INTERVAL_SECONDS
                force_redraw = False

            int_is_low = gt.digital_read(gt.INT) == 0
            if int_is_low:
                gt_dev.Touch = 1
                gt.GT_Scan(gt_dev, gt_old)
            else:
                touch_latched = False

            if gt_dev.TouchpointFlag:
                gt_dev.TouchpointFlag = 0
                raw_x = gt_dev.X[0]
                raw_y = gt_dev.Y[0]
                x, y = raw_touch_to_landscape(raw_x, raw_y)

                if (
                    current_page == ADMIN_PAGE_INDEX
                    and armed_admin_action
                    and x >= SIDEBAR_X0
                ):
                    touch_latched = True
                    if is_inside(ADMIN_CONFIRM_BUTTON, x, y) and now <= armed_admin_expires_at:
                        trigger_admin_action(armed_admin_action)
                    else:
                        LOGGER.warning("Admin action canceled (confirmation zone not tapped).")
                    armed_admin_action = ""
                    force_redraw = True
                    time.sleep(TOUCH_POLL_ACTIVE_SECONDS if int_is_low else TOUCH_POLL_IDLE_SECONDS)
                    continue

                if (
                    not touch_latched
                    and x >= SIDEBAR_X0
                    and (now - last_page_touch) > TOUCH_DEBOUNCE_SECONDS
                ):
                    if is_inside(UP_BUTTON, x, y):
                        current_page = (current_page - 1) % len(PAGES)
                        force_redraw = True
                        last_page_touch = now
                        touch_latched = True
                        armed_admin_action = ""
                    elif is_inside(DOWN_BUTTON, x, y):
                        current_page = (current_page + 1) % len(PAGES)
                        force_redraw = True
                        last_page_touch = now
                        touch_latched = True
                        armed_admin_action = ""

                if current_page == ADMIN_PAGE_INDEX and x < SIDEBAR_X0:
                    tapped_action = ""
                    if is_inside(ADMIN_REBOOT_BUTTON, x, y):
                        tapped_action = "reboot"
                    elif is_inside(ADMIN_SHUTDOWN_BUTTON, x, y):
                        tapped_action = "shutdown"

                    if tapped_action:
                        touch_latched = True
                        if (
                            armed_admin_action == tapped_action
                            and now <= armed_admin_expires_at
                        ):
                            trigger_admin_action(tapped_action)
                            armed_admin_action = ""
                            force_redraw = True
                        else:
                            armed_admin_action = tapped_action
                            armed_admin_expires_at = now + ADMIN_CONFIRM_WINDOW_SECONDS
                            LOGGER.warning(
                                "Admin action '%s' armed. Tap CONFIRM on the right within %.0fs.",
                                tapped_action,
                                ADMIN_CONFIRM_WINDOW_SECONDS,
                            )
                            force_redraw = True

            if armed_admin_action and now > armed_admin_expires_at:
                armed_admin_action = ""
                force_redraw = True

            time.sleep(TOUCH_POLL_ACTIVE_SECONDS if int_is_low else TOUCH_POLL_IDLE_SECONDS)
    except KeyboardInterrupt:
        LOGGER.info("Exiting...")
    finally:
        try:
            epd.init(epd.FULL_UPDATE)
            epd.Clear(0xFF)
            epd.sleep()
        finally:
            epd.Dev_exit()
            if sim_server is not None:
                sim_server.stop()


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Waveshare monitor display")
    parser.add_argument("--simulator", action="store_true", help="run without GPIO and serve localhost simulator")
    parser.add_argument("--simulator-port", type=int, default=8765, help="simulator HTTP port (default: 8765)")
    parser.add_argument("--simulator-host", default="127.0.0.1", help="simulator bind host (default: 127.0.0.1)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    run(
        simulator=args.simulator,
        simulator_host=args.simulator_host,
        simulator_port=args.simulator_port,
    )


if __name__ == "__main__":
    main()
