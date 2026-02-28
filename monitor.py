#!/usr/bin/python3
# -*- coding:utf-8 -*-
import datetime
import fcntl
import logging
import os
import socket
import struct
import sys
import time

from PIL import Image, ImageDraw, ImageFont

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
fontdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "pic")
if os.path.exists(libdir):
    sys.path.append(libdir)

from TP_lib import epd2in13_V4

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 5
FULL_REFRESH_EVERY_N_UPDATES = 30


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


def load_font(size):
    for name in ("Roboto-Regular.ttf", "Font.ttc"):
        path = os.path.join(fontdir, name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_frame(epd, font_title, font_body):
    image = Image.new("1", (epd.height, epd.width), 255)
    draw = ImageDraw.Draw(image)

    now = datetime.datetime.now()
    draw.text((6, 4), "Network Monitor", font=font_title, fill=0)
    draw.line((6, 24, epd.height - 6, 24), fill=0, width=1)
    draw.text((6, 28), now.strftime("Updated: %Y-%m-%d %H:%M:%S"), font=font_body, fill=0)

    y = 48
    for ifname, ip in get_non_loopback_ipv4():
        draw.text((6, y), f"{ifname}: {ip}", font=font_body, fill=0)
        y += 18
        if y > epd.width - 16:
            break

    if y == 48:
        draw.text((6, y), "No non-loopback IPv4 addresses", font=font_body, fill=0)

    return image


def main():
    epd = epd2in13_V4.EPD()
    font_title = load_font(18)
    font_body = load_font(14)
    update_count = 0

    try:
        LOGGER.info("Initializing Waveshare 2.13 V4 display")
        epd.init(epd.FULL_UPDATE)
        epd.Clear(0xFF)

        base_image = build_frame(epd, font_title, font_body)
        epd.displayPartBaseImage(epd.getbuffer(base_image))
        epd.init(epd.PART_UPDATE)

        while True:
            time.sleep(UPDATE_INTERVAL_SECONDS)
            image = build_frame(epd, font_title, font_body)
            update_count += 1

            if update_count >= FULL_REFRESH_EVERY_N_UPDATES:
                epd.init(epd.FULL_UPDATE)
                epd.displayPartBaseImage(epd.getbuffer(image))
                epd.init(epd.PART_UPDATE)
                update_count = 0
            else:
                epd.displayPartial_Wait(epd.getbuffer(image))
    except KeyboardInterrupt:
        LOGGER.info("Exiting...")
    finally:
        epd.sleep()
        epd.Dev_exit()


if __name__ == "__main__":
    main()
