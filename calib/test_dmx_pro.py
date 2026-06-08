#!/usr/bin/env python3
"""Pure-software tests for dmx_pro.py — no hardware, no DMX output, no pytest.

Covers: label-6 packet bytes/length, frame-file round-trip, and stdout-grammar
parity with dmx_open.py (the orchestrator string-matches '(all zero)' and parses
_fmt, so the two drivers MUST agree byte-for-byte on those strings).

Run: calib/.venv/bin/python calib/test_dmx_pro.py
"""
import importlib.util, pathlib, tempfile, os, sys

HERE = pathlib.Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pro = _load("dmx_pro")
opn = _load("dmx_open")


def test_blackout_packet():
    pkt = pro.build_dmx_packet(bytearray(512))
    assert pkt[0] == 0x7E
    assert pkt[1] == 6                        # label = Send DMX
    assert pkt[2] == 0x01 and pkt[3] == 0x02  # len 513, little-endian
    assert pkt[4] == 0x00                     # DMX start code
    assert pkt[5:5 + 512] == bytes(512)       # 512 zero channels
    assert pkt[-1] == 0xE7
    assert len(pkt) == 518                    # 4 hdr + 513 body + 1 end


def test_set_frame_packet():
    frame = bytearray(512); frame[0] = 220; frame[7] = 20
    pkt = pro.build_dmx_packet(frame)
    assert len(pkt) == 518
    assert pkt[4] == 0x00                      # start code unchanged
    assert pkt[5 + 0] == 220                   # CH1 -> body index 0 (after start code)
    assert pkt[5 + 7] == 20                    # CH8 -> body index 7
    assert pkt[5 + 1] == 0                     # untouched channel


def test_short_frame_padded():
    pkt = pro.build_dmx_packet(bytearray([255, 128]))
    assert len(pkt) == 518
    assert pkt[5] == 255 and pkt[6] == 128 and pkt[7] == 0


def test_find_enttec_frame_with_leading_junk():
    raw = b"\x00junk" + bytes([0x7E, 3, 5, 0, 0x2C, 0x01, 9, 1, 40, 0xE7])
    label, payload, frame = pro.find_enttec_frame(raw, expected_label=3)
    assert label == 3
    assert payload == bytes([0x2C, 0x01, 9, 1, 40])
    assert frame == raw[5:]


def test_find_enttec_frame_waits_for_complete_frame():
    raw = bytes([0x7E, 3, 5, 0, 0x2C])
    assert pro.find_enttec_frame(raw, expected_label=3) is None


def test_frame_io_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        old_fp, old_wd = pro.FRAME_PATH, pro.WATCHDOG_PATH
        pro.FRAME_PATH = os.path.join(d, "frame.bin")
        pro.WATCHDOG_PATH = os.path.join(d, "hb")
        try:
            b = bytearray(512); b[0] = 220; b[7] = 20
            pro.save_frame(b)
            assert pro.load_frame() == b
            assert os.path.exists(pro.WATCHDOG_PATH)   # save touches watchdog
        finally:
            pro.FRAME_PATH, pro.WATCHDOG_PATH = old_fp, old_wd


def test_persist_blackout_frame_does_not_touch_watchdog():
    with tempfile.TemporaryDirectory() as d:
        old_fp, old_wd = pro.FRAME_PATH, pro.WATCHDOG_PATH
        pro.FRAME_PATH = os.path.join(d, "frame.bin")
        pro.WATCHDOG_PATH = os.path.join(d, "hb")
        try:
            pro.write_frame_file(bytearray([9]) + bytearray(511))
            pro.persist_blackout_frame()
            assert pro.load_frame() == bytearray(512)
            assert not os.path.exists(pro.WATCHDOG_PATH)
        finally:
            pro.FRAME_PATH, pro.WATCHDOG_PATH = old_fp, old_wd


class FakeSerial:
    def __init__(self, fail_write=False):
        self.fail_write = fail_write
        self.writes = []
        self.closed = False

    def write(self, packet):
        if self.fail_write:
            raise OSError("write failed")
        self.writes.append(bytes(packet))

    def flush(self):
        pass

    def close(self):
        self.closed = True


def test_blackout_best_effort_existing_serial_persists_zero():
    with tempfile.TemporaryDirectory() as d:
        old_fp, old_wd = pro.FRAME_PATH, pro.WATCHDOG_PATH
        pro.FRAME_PATH = os.path.join(d, "frame.bin")
        pro.WATCHDOG_PATH = os.path.join(d, "hb")
        fake = FakeSerial()
        try:
            pro.write_frame_file(bytearray([255]) + bytearray(511))
            ok, msg = pro.push_blackout_best_effort("/dev/fake", existing_ser=fake, reopen_attempts=0)
            assert ok, msg
            assert fake.writes == [pro._ZERO_PACKET]
            assert pro.load_frame() == bytearray(512)
        finally:
            pro.FRAME_PATH, pro.WATCHDOG_PATH = old_fp, old_wd


def test_blackout_best_effort_reopens_after_existing_failure():
    with tempfile.TemporaryDirectory() as d:
        old_fp, old_wd = pro.FRAME_PATH, pro.WATCHDOG_PATH
        old_open = pro._open_port
        pro.FRAME_PATH = os.path.join(d, "frame.bin")
        pro.WATCHDOG_PATH = os.path.join(d, "hb")
        reopened = FakeSerial()
        try:
            pro._open_port = lambda *_args, **_kwargs: reopened
            ok, msg = pro.push_blackout_best_effort(
                "/dev/fake",
                existing_ser=FakeSerial(fail_write=True),
                reopen_attempts=1,
            )
            assert ok, msg
            assert reopened.writes == [pro._ZERO_PACKET]
            assert pro.load_frame() == bytearray(512)
        finally:
            pro._open_port = old_open
            pro.FRAME_PATH, pro.WATCHDOG_PATH = old_fp, old_wd


def test_fmt_grammar_matches_open():
    b = bytearray(512); b[0] = 220; b[7] = 20; b[18] = 5
    assert pro._fmt(b) == opn._fmt(b)          # identical CH{n}={v} grammar
    assert pro._fmt(bytearray(512)) == ""      # empty -> show prints "(all zero)"


def test_base_matches_open():
    assert pro.BASE == opn.BASE


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
