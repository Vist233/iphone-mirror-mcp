"""Local iPhone driver. No model, Codex API, global input or foreground fallback.

Uses the existing local PyObjC environment. SkyLight entry points are private;
their presence and successful submission are not proof of a phone-side action.
"""
import ctypes
import json
import math
import objc
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time

import AppKit
import ApplicationServices as AX
import Quartz as Q
import Vision
from Foundation import NSURL

SKY = ctypes.CDLL('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
AS = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')

class PSN(ctypes.Structure):
    _fields_ = [('high', ctypes.c_uint32), ('low', ctypes.c_uint32)]

class Point(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]

def bind(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function

GET_PSN = bind(AS, 'GetProcessForPID', [ctypes.c_int32, ctypes.c_void_p], ctypes.c_int32)
GET_PID = bind(AS, 'GetProcessPID', [ctypes.c_void_p, ctypes.c_void_p], ctypes.c_int32)
GET_FRONT = bind(SKY, '_SLPSGetFrontProcess', [ctypes.c_void_p], ctypes.c_int32)
GET_KEY = bind(SKY, 'SLPSGetKeyFocusProcess', [ctypes.c_void_p, ctypes.c_void_p], ctypes.c_int32)
POST_RECORD = bind(SKY, 'SLPSPostEventRecordTo', [ctypes.c_void_p, ctypes.c_void_p], ctypes.c_int32)
POST_WINDOW_RECORD = bind(SKY, 'SLSPostEventRecord', [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32], ctypes.c_int32)
WINDOW_SERVER_CONNECTION = bind(SKY, 'SLSMainConnectionID', [], ctypes.c_uint32)
EVENT_RECORD_POINTER = bind(SKY, 'SLEventRecordPointer', [ctypes.c_void_p], ctypes.c_void_p)

# A posted wheel record is a fixed 0xf8-byte struct. WindowServer reads the
# target global point from offset 0x10, which is how it performs the window
# hit test that CGEventPostToPid skips.
WHEEL_RECORD_LENGTH = 0xf8
WHEEL_RECORD_LENGTH_OFFSET = 4
WHEEL_RECORD_POINT_OFFSET = 0x10
WHEEL_RECORD_COUNT = 2
WHEEL_RECORD_INTERVAL_SECONDS = 0.04
WHEEL_RECORD_SETTLE_SECONDS = 0.65

# Only +/-50 was repeatedly measured. Treat each request as a bounded step;
# do not infer a proportional distance or a magnitude ceiling from that study.
MAX_WHEEL_MAGNITUDE = 50

def target():
    apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_('com.apple.ScreenContinuity')
    if not apps:
        raise RuntimeError('Open and connect iPhone Mirroring manually.')
    pid = apps[0].processIdentifier()
    windows = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionAll, 0) or []
    candidates = [w for w in windows if w.get('kCGWindowOwnerPID') == pid
                  and w.get('kCGWindowLayer') == 0
                  and w['kCGWindowBounds']['Height'] > 400
                  and w['kCGWindowBounds']['Height'] > 1.3 * w['kCGWindowBounds']['Width']]
    if not candidates:
        raise RuntimeError('No portrait mirror window; connection is not confirmed.')
    window = max(candidates, key=lambda w: w['kCGWindowBounds']['Width'] * w['kCGWindowBounds']['Height'])
    bounds = window['kCGWindowBounds']
    return pid, int(window['kCGWindowNumber']), bounds

def focus_state():
    result = {}
    for name, function in [('front_pid', GET_FRONT), ('keyboard_pid', GET_KEY)]:
        serial = PSN()
        connection = (ctypes.c_uint64 * 2)()
        error = function(ctypes.byref(serial)) if name == 'front_pid' else function(ctypes.byref(serial), ctypes.byref(connection))
        pid = ctypes.c_int32()
        if error or GET_PID(ctypes.byref(serial), ctypes.byref(pid)):
            raise RuntimeError('Could not verify WindowServer focus.')
        result[name] = pid.value
    result['cursor'] = list(Q.CGEventGetLocation(Q.CGEventCreate(None)))
    return result

def internal_active(pid):
    error, value = AX.AXUIElementCopyAttributeValue(AX.AXUIElementCreateApplication(pid), 'AXFrontmost', None)
    if error:
        raise RuntimeError('Could not read target internal activation state.')
    return bool(value)

def record(pid, window_id, kind, state=None, point=None):
    serial = PSN()
    if GET_PSN(pid, ctypes.byref(serial)):
        raise RuntimeError('Could not resolve mirror process.')
    data = (ctypes.c_uint8 * 0xf8)()
    data[4] = 0xf8
    data[8] = kind
    struct.pack_into('<I', data, 0x3c, window_id)
    if state is not None:
        data[0x8a] = state
    else:
        data[0x3a] = 0x10
        if point is None:
            for i in range(0x20, 0x30):
                data[i] = 0xff
        else:
            gx, gy, lx, ly = point
            struct.pack_into('<dd', data, 0x10, gx, gy)
            struct.pack_into('<dd', data, 0x20, lx, ly)
    error = POST_RECORD(ctypes.byref(serial), ctypes.byref(data))
    if error:
        raise RuntimeError(f'Window event submission refused: {error}')

def prime(pid, window_id):
    record(pid, window_id, 0x0d, state=1)
    time.sleep(0.12)
    for kind in (1, 2):
        record(pid, window_id, kind)
    time.sleep(0.12)

def post_key(pid, window_id, code, down, flags=0):
    # Match the independently repeated system-search trials. No global HID post.
    event = Q.CGEventCreateKeyboardEvent(None, code, down)
    if event is None:
        raise RuntimeError('Keyboard event creation failed.')
    Q.CGEventSetFlags(event, flags)
    Q.CGEventPostToPid(pid, event)
    time.sleep(0.035)

KEYS = dict(zip('asdfhgzxcvbqweryt1234659780', [0,1,2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,23,25,26,28,29]))
KEYS.update(dict(zip('ouip ljnkm'.replace(' ', ''), [31,32,34,35,37,38,45,40,46])))
KEYS.update({' ':49, '-':27, '=':24, '[':33, ']':30, ';':41, "'":39, ',':43, '.':47, '/':44, '\\':42, '`':50})
SPECIAL = {'return':36, 'enter':36, 'tab':48, 'delete':51, 'escape':53, 'left':123, 'right':124, 'up':126, 'down':125, 'space':49}
MODIFIERS = {'cmd':(55,Q.kCGEventFlagMaskCommand), 'shift':(56,Q.kCGEventFlagMaskShift), 'ctrl':(59,Q.kCGEventFlagMaskControl), 'alt':(58,Q.kCGEventFlagMaskAlternate)}

def chord(pid, window_id, code, modifiers=()):
    flags = 0
    held = []
    try:
        for modifier in modifiers:
            key, flag = MODIFIERS[modifier]
            flags |= flag
            post_key(pid, window_id, key, True, flags)
            held.append((key, flag))
        try:
            post_key(pid, window_id, code, True, flags)
        finally:
            post_key(pid, window_id, code, False, flags)
    finally:
        for key, flag in reversed(held):
            flags &= ~flag
            post_key(pid, window_id, key, False, flags)

def unicode_chunks(text, max_units=16):
    """Keep each Python Unicode scalar intact at UTF-16 event boundaries."""
    chunk = ''
    units = 0
    for character in text:
        size = len(character.encode('utf-16-le'))//2
        if units+size>max_units:
            yield chunk
            chunk = ''
            units = 0
        chunk += character
        units += size
    if chunk:
        yield chunk

def type_unicode(pid, text):
    for chunk in unicode_chunks(text):
        units = len(chunk.encode('utf-16-le'))//2
        for down in (True,False):
            event = Q.CGEventCreateKeyboardEvent(None,0,down)
            if event is None:
                raise RuntimeError('Unicode event creation failed.')
            Q.CGEventSetFlags(event,0)
            Q.CGEventKeyboardSetUnicodeString(event,units,chunk)
            Q.CGEventPostToPid(pid,event)
            time.sleep(.035)

def uncovered_point(window_id, bounds):
    """Return a point inside the mirror that no other window covers.

    WindowServer routes a posted wheel record by the point inside it, so an
    occluded mirror has nowhere to deliver. Refusing here is safer than
    posting at a point that belongs to some other app.
    """
    onscreen = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly, 0)
    for fraction in (0.5, 0.4, 0.6):
        point = (bounds['X'] + bounds['Width'] * 0.5,
                 bounds['Y'] + bounds['Height'] * fraction)
        for window in onscreen:
            rect = window['kCGWindowBounds']
            if not (window.get('kCGWindowLayer') == 0
                    and rect['X'] <= point[0] < rect['X'] + rect['Width']
                    and rect['Y'] <= point[1] < rect['Y'] + rect['Height']):
                continue
            if window['kCGWindowNumber'] == window_id:
                return point
            break
    raise RuntimeError('The mirror is covered by another window; no scroll sent. '
                       'Bring the mirror to an uncovered part of the desktop and retry.')


DEFAULT_SCHEME = 'a1'


def build_plain_wheel(source, dy, point):
    return [wheel_record(source, dy, point) for _ in range(WHEEL_RECORD_COUNT)]


def wheel_record(source, delta, point):
    """Build one pixel-wheel record aimed at a point inside the mirror.

    The returned event owns the record's memory, so the caller must keep it
    referenced until after the record has been posted.
    """
    event = Q.CGEventCreateScrollWheelEvent(source, Q.kCGScrollEventUnitPixel, 1, delta)
    if event is None:
        raise RuntimeError('Scroll event creation failed.')
    record = EVENT_RECORD_POINTER(objc.pyobjc_id(event))
    if not record:
        raise RuntimeError('Scroll event produced no record.')
    length = struct.unpack_from('<I', (ctypes.c_uint8*WHEEL_RECORD_LENGTH).from_address(record),
                                WHEEL_RECORD_LENGTH_OFFSET)[0]
    if length != WHEEL_RECORD_LENGTH:
        raise RuntimeError(f'Unexpected wheel record layout: {length:#x}.')
    struct.pack_into('<dd', (ctypes.c_uint8*WHEEL_RECORD_LENGTH).from_address(record),
                     WHEEL_RECORD_POINT_OFFSET, *point)
    return event


def post_wheel_records(window_id, bounds, dy, before, scheme_name=DEFAULT_SCHEME):
    """Post the scroll records, aborting if Mac focus or coverage changes.

    Returns the per-record WindowServer status codes.
    """
    if scheme_name != DEFAULT_SCHEME:
        raise ValueError('Only the measured a1 scroll scheme is published.')
    point = uncovered_point(window_id, bounds)
    source = Q.CGEventSourceCreate(1)
    connection = WINDOW_SERVER_CONNECTION()
    events = build_plain_wheel(source, dy, point)
    statuses = []
    for event in events:
        current = focus_state()
        if any(current[key] != before[key] for key in ('front_pid', 'keyboard_pid')):
            raise RuntimeError('Mac focus changed; scroll stopped before posting.')
        if uncovered_point(window_id, bounds) != point:
            raise RuntimeError('Mirror coverage changed; scroll stopped before posting.')
        record = EVENT_RECORD_POINTER(objc.pyobjc_id(event))
        status = POST_WINDOW_RECORD(connection, record, WHEEL_RECORD_LENGTH, 0)
        statuses.append(status)
        if status:
            raise RuntimeError(f'WindowServer rejected the scroll record: {status}.')
        time.sleep(WHEEL_RECORD_INTERVAL_SECONDS)
    return statuses


def capture(window_id, path):
    subprocess.run(['/usr/sbin/screencapture', '-l', str(window_id), '-x', '-o', '-t', 'png', path], check=True, timeout=10, capture_output=True)
    if Path(path).stat().st_size < 100:
        raise RuntimeError('Window capture was empty.')

def read_text(window_id, path, bounds):
    capture(window_id, path)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLanguages_(['zh-Hans', 'en-US'])
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(path), None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f'OCR failed: {error}')
    rows = []
    for observation in request.results() or []:
        candidate = observation.topCandidates_(1)
        if candidate:
            box = observation.boundingBox()
            rows.append({'text':str(candidate[0].string()), 'confidence':float(candidate[0].confidence()),
                         'x':box.origin.x + box.size.width/2, 'y':1-box.origin.y-box.size.height/2})
    return rows

def coordinate(value, size):
    number = float(value[3:]) if value.startswith('px:') else float(value) * size
    if not math.isfinite(number) or not 0 <= number < size:
        raise ValueError('Coordinate outside window.')
    return number

def main(arguments):
    command, *args = arguments
    pid, window_id, bounds = target()
    before = focus_state()
    if command == 'info':
        return {'ok':True, 'pid':pid, 'windowID':window_id, 'rect':[bounds[k] for k in ['X','Y','Width','Height']],
                'focus':before, 'trusted_post_event':bool(Q.CGPreflightPostEventAccess()),
                'capabilities':{'capture':True, 'ocr':True, 'tap':'partial_device_verification',
                                'ascii_type':'enabled_physical_keys_english_layout', 'unicode_type':True,
                                'navigation_keys':['return','enter'],
                                'scroll':('experimental_a1_enabled' if os.environ.get('MIRROR_ENABLE_EXPERIMENTAL_INPUT') == '1' else 'disabled_by_default')}}
    if command in ('capture', 'read'):
        path = args[0]
        if command == 'read':
            rows = read_text(window_id, path, bounds)
            return {'ok':True, 'rows':rows, 'path':path, 'windowID':window_id}
        capture(window_id, path)
        return {'ok':True, 'path':path, 'windowID':window_id, 'bytes':Path(path).stat().st_size}
    if not Q.CGPreflightPostEventAccess():
        raise RuntimeError('Input permission is unavailable; no event sent.')
    with tempfile.TemporaryDirectory(prefix='mirror-preflight-') as temporary:
        rows = read_text(window_id, str(Path(temporary)/'screen.png'), bounds)
    visible = ' '.join(row['text'] for row in rows).lower()
    blocked = ['iphone in use', 'lock your iphone', 'connect to your iphone', 'connection lost',
               '连接已断开', 'iphone正在使用', 'iphone 正在使用', '锁定 iphone', '输入密码']
    if not rows or any(message in visible for message in blocked):
        raise RuntimeError('Mirror not ready or screen unreadable; reconnect manually. No event sent.')
    verified_key = command == 'key' and args in (['return'], ['enter'])
    if command not in ('tap', 'home', 'spotlight', 'type', 'text') and not verified_key and os.environ.get('MIRROR_ENABLE_EXPERIMENTAL_INPUT') != '1':
        raise RuntimeError('This input route has not passed noninterference verification and is disabled.')
    if command == 'type' and (len(args[0])>200 or any(c.lower() not in KEYS for c in args[0])):
        raise ValueError('Unsupported physical key. Use the Unicode text command for non-ASCII text.')
    if command == 'text' and (len(args[0])>200 or any(ord(c)<32 or ord(c)==127 for c in args[0])):
        raise ValueError('Text must be <=200 characters without control characters; no implicit Return/submit.')
    if command == 'scroll':
        delta = int(args[0])
        if delta not in (-MAX_WHEEL_MAGNITUDE, MAX_WHEEL_MAGNITUDE):
            raise ValueError('Scroll dy must be -50 or 50; only these steps were measured.')
        scheme_name = os.environ.get('MIRROR_SCROLL_SCHEME', DEFAULT_SCHEME)
        if scheme_name != DEFAULT_SCHEME:
            raise ValueError('Only MIRROR_SCROLL_SCHEME=a1 is published; other schemes remain local research.')
    needs_priming = command not in ('home', 'spotlight', 'scroll')
    was_active = internal_active(pid)
    samples = [before]
    stop_monitor = threading.Event()
    def monitor():
        while not stop_monitor.wait(.025):
            try:
                samples.append(focus_state())
            except Exception:
                samples.append({'measurement_error':True})
    watcher = threading.Thread(target=monitor,daemon=True)
    watcher.start()
    try:
        if needs_priming:
            prime(pid, window_id)
            primed = focus_state()
            if any(primed[key] != before[key] for key in ('front_pid','keyboard_pid')):
                raise RuntimeError('Input priming changed system focus; no text or scroll sent.')
        if command in ('tap', 'longpress'):
            if command == 'longpress':
                raise ValueError('Long press is not verified.')
            x, y = coordinate(args[0], bounds['Width']), coordinate(args[1], bounds['Height'])
            point = (bounds['X']+x, bounds['Y']+y, x, y)
            try:
                record(pid, window_id, 1, point=point)
                time.sleep(0.06)
            finally:
                record(pid, window_id, 2, point=point)
        elif command in ('home', 'spotlight'):
            code = 18 if command == 'home' else 20
            held = []
            try:
                for key in (55, code):
                    event = Q.CGEventCreateKeyboardEvent(None, key, True)
                    Q.CGEventSetFlags(event, Q.kCGEventFlagMaskCommand)
                    Q.CGEventPostToPid(pid, event)
                    held.append(key)
                    time.sleep(0.04)
            finally:
                for key in reversed(held):
                    event = Q.CGEventCreateKeyboardEvent(None, key, False)
                    Q.CGEventSetFlags(event, Q.kCGEventFlagMaskCommand if key != 55 else 0)
                    Q.CGEventPostToPid(pid, event)
        elif command in ('type','text'):
            if len(args)>1 and args[1]=='replace':
                chord(pid, window_id, KEYS['a'], ['cmd'])
                chord(pid, window_id, SPECIAL['delete'])
            if command=='text':
                type_unicode(pid,args[0])
            else:
                for character in args[0]:
                    chord(pid, window_id, KEYS[character.lower()], ['shift'] if character.isupper() else [])
        elif command == 'key':
            name = args[0].lower()
            code = SPECIAL.get(name, KEYS.get(name))
            if code is None or any(m not in MODIFIERS for m in args[1:]):
                raise ValueError('Unsupported key or modifier.')
            chord(pid, window_id, code, args[1:])
        elif command == 'scroll':
            statuses = post_wheel_records(window_id, bounds, delta, before, scheme_name)
            time.sleep(WHEEL_RECORD_SETTLE_SECONDS)
        else:
            raise ValueError('Unsupported command; no foreground fallback.')
        time.sleep(0.2)
    finally:
        try:
            if not was_active and needs_priming:
                record(pid, window_id, 0x0d, state=2)
        finally:
            stop_monitor.set()
            watcher.join(timeout=2)
    after = focus_state()
    samples.append(after)
    result = {'ok':True, 'submission':'submitted', 'phone_effect_verified':False, 'before':before, 'after':after,
            'sample_count':len(samples),
            'focus_unchanged':all(all(sample.get(key)==before[key] for key in ('front_pid','keyboard_pid')) for sample in samples),
            'cursor_same_at_samples':all(sample.get('cursor')==before['cursor'] for sample in samples)}
    if command == 'scroll':
        result['record_statuses'] = statuses
        result['interpretation'] = (
            'Event submission is not proof of scrolling. No movement can mean a list '
            'boundary, an input failure, or an observation problem. Inspect the '
            'fresh screen before deciding on another action; do not retry automatically.')
    return result

if __name__ == '__main__':
    try:
        print(json.dumps(main(sys.argv[1:]),ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False))
        sys.exit(1)
