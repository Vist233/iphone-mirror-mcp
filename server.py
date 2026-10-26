#!/usr/bin/env python3
"""Model-independent MCP stdio server; protocol layer uses only stdlib."""
import base64
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
DRIVER = os.environ.get('MR_MIRRORCTL', str(ROOT/'mirror-driver'))
VERSIONS = ('2025-06-18', '2025-03-26', '2024-11-05')
LOCK_PATH = Path(os.environ.get('MIRROR_LOCK_PATH', f'/tmp/iphone-mirror-{os.getuid()}.lock'))

@contextmanager
def device_transaction():
    """Serialize entire action/observation pairs across copies of this server."""
    descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Device busy: another MCP transaction holds the phone. No action sent.')
        yield
    finally:
        os.close(descriptor)

def tool(name, description, properties=None, required=None):
    return {'name':name, 'description':description,
            'inputSchema':{'type':'object', 'properties':properties or {},
                           'required':required or [], 'additionalProperties':False}}

TOOLS = [
    tool('mirror_status', 'Read capabilities and actual WindowServer front/keyboard focus. No input.'),
    tool('mirror_observe', 'Read current phone as OCR text with normalized x/y centers. Default is text-only; no vision model needed. Read before each action.',
         {'image':{'type':'boolean'}}),
    tool('mirror_tap', 'Submit one normalized coordinate tap. Returns a fresh observation; submission alone is not proof of success.',
         {'x':{'type':'number','minimum':0,'exclusiveMaximum':1}, 'y':{'type':'number','minimum':0,'exclusiveMaximum':1}}, ['x','y']),
    tool('mirror_tap_text', 'Tap one unique visible OCR text match. Fails on zero or multiple matches. Re-read the result.',
         {'text':{'type':'string','minLength':1}}, ['text']),
    tool('mirror_navigate', 'Open phone Home, Spotlight, or App Switcher (recent apps), then observe. Inspect Spotlight results before opening an app.',
         {'destination':{'type':'string','enum':['home','spotlight','app_switcher']}}, ['destination']),
    tool('mirror_input', 'Input into a focused phone field. action=text uses Unicode by default; mode=ascii uses English-layout physical keys. replace=true replaces text. action=enter explicitly presses Return and may submit a message or form; use only with user authorization and a verified target. Text never implicitly submits.',
         {'action':{'type':'string','enum':['text','enter']}, 'text':{'type':'string','maxLength':200},
          'mode':{'type':'string','enum':['unicode','ascii']}, 'replace':{'type':'boolean'}}, ['action']),
    tool('mirror_scroll', 'Experimental bounded scroll; disabled unless MIRROR_ENABLE_EXPERIMENTAL_INPUT=1. Provide direction (content movement: up/down/left/right) OR legacy dy (-50 earlier, +50 later). Horizontal uses Shift+wheel and still needs device validation. Requires an uncovered mirror point. Inspect the returned observation; do not retry automatically.',
         {'dy':{'type':'integer','enum':[-50,50]},
          'direction':{'type':'string','enum':['up','down','left','right']}}),
]

def run(*arguments):
    result = subprocess.run([DRIVER,*map(str,arguments)],capture_output=True,text=True,timeout=25)
    lines = result.stdout.strip().splitlines()
    try:
        payload = json.loads(lines[-1]) if lines else {}
    except (ValueError, IndexError):
        raise RuntimeError('Driver returned invalid JSON.')
    if not isinstance(payload,dict):
        raise RuntimeError('Driver returned a non-object result.')
    if result.returncode or payload.get('ok') is not True:
        raise RuntimeError(payload.get('error','Driver failed without a valid result.'))
    return payload

def observe(include_image=False):
    with tempfile.TemporaryDirectory(prefix='mirror-observe-') as directory:
        path = str(Path(directory)/'screen.png')
        result = run('read',path)
        payload = {'windowID':result['windowID'], 'elements':result['rows'],
                   'coordinates':'normalized window coordinates, top-left origin',
                   'warning':'OCR can merge text; do not assume an action succeeded without checking the next observation.'}
        content = [{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        if include_image:
            content.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(path).read_bytes()).decode()})
        return content, result['rows']

def validate(name, arguments):
    if not isinstance(arguments,dict):
        raise ValueError('arguments must be an object.')
    definition = next((t for t in TOOLS if t['name']==name),None)
    if definition is None:
        raise ValueError('Unknown tool.')
    schema = definition['inputSchema']
    if set(arguments)-set(schema['properties']) or set(schema['required'])-set(arguments):
        raise ValueError('Unexpected or missing arguments.')
    for key,value in arguments.items():
        specification = schema['properties'][key]
        kind = specification['type']
        if kind == 'string' and (not isinstance(value,str) or not specification.get('minLength',0)<=len(value)<=specification.get('maxLength',10000)):
            raise ValueError(f'Invalid {key}.')
        if kind == 'boolean' and not isinstance(value,bool):
            raise ValueError(f'Invalid {key}.')
        if 'enum' in specification and value not in specification['enum']:
            raise ValueError(f'Unsupported {key}.')
        if kind in ('number','integer'):
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
                raise ValueError(f'Invalid {key}.')
            if kind == 'integer' and not isinstance(value,int):
                raise ValueError(f'{key} must be an integer.')
            if value<specification.get('minimum',-math.inf) or value>specification.get('maximum',math.inf) or value>=specification.get('exclusiveMaximum',math.inf):
                raise ValueError(f'{key} outside allowed range.')
    if name == 'mirror_input':
        if arguments['action'] == 'enter':
            if set(arguments) != {'action'}:
                raise ValueError('enter accepts only action; text options must be omitted.')
        elif 'text' not in arguments:
            raise ValueError('text is required for action=text.')
        elif any(ord(c)<32 or ord(c)==127 for c in arguments['text']):
            raise ValueError('Control characters are disabled; typing never implicitly submits.')
    if name == 'mirror_scroll' and len(arguments) != 1:
        raise ValueError('Provide exactly one of dy or direction.')

def call(name, arguments):
    with device_transaction():
        return call_locked(name, arguments)

def call_locked(name, arguments):
    validate(name,arguments)
    if name == 'mirror_status':
        return [{'type':'text','text':json.dumps(run('info'),ensure_ascii=False)}]
    if name == 'mirror_observe':
        return observe(arguments.get('image',False))[0]
    if name == 'mirror_tap_text':
        rows = observe()[1]
        matches = [row for row in rows if arguments['text'].casefold() in row['text'].casefold()]
        if len(matches)!=1:
            raise ValueError(f'Expected one text match, found {len(matches)}. Observe and choose a coordinate instead.')
        result = run('tap',matches[0]['x'],matches[0]['y'])
    elif name == 'mirror_tap':
        result = run('tap',arguments['x'],arguments['y'])
    elif name == 'mirror_navigate':
        result = run(arguments['destination'])
    elif name == 'mirror_input':
        if arguments['action'] == 'enter':
            result = run('key','return')
        else:
            result = run('type' if arguments.get('mode')=='ascii' else 'text',arguments['text'],*(['replace'] if arguments.get('replace',False) else []))
    elif name == 'mirror_scroll':
        if 'dy' in arguments:
            result = run('scroll',arguments['dy'])
        else:
            direction = arguments['direction']
            delta = 50 if direction in ('up','left') else -50
            result = run('scroll',delta,*(['horizontal'] if direction in ('left','right') else []))
    else:
        raise ValueError('Unknown tool.')
    content = [{'type':'text','text':json.dumps(result,ensure_ascii=False)}]
    try:
        content.extend(observe()[0])
    except Exception as error:
        content.append({'type':'text','text':json.dumps({
            'observation':'unavailable', 'phone_effect_verified':False,
            'retry_action':False, 'error':str(error),
            'warning':'The action was submitted but the next observation failed. Its phone effect is unknown. Observe again before deciding whether to repeat the action.'
        },ensure_ascii=False)})
    return content

def response(request):
    if not isinstance(request,dict):
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid Request'}}
    if 'id' not in request:
        return None
    rid = request['id']
    method = request.get('method')
    params = request.get('params',{})
    envelope = {'jsonrpc':'2.0','id':rid}
    if not isinstance(params,dict):
        return dict(envelope,error={'code':-32602,'message':'params must be an object'})
    if method == 'initialize':
        version = params.get('protocolVersion')
        return dict(envelope,result={'protocolVersion':version if version in VERSIONS else VERSIONS[0],
                                    'capabilities':{'tools':{}}, 'serverInfo':{'name':'iphone-mirror-local','version':'0.3.0'}})
    if method == 'ping':
        return dict(envelope,result={})
    if method == 'tools/list':
        return dict(envelope,result={'tools':TOOLS})
    if method == 'tools/call':
        try:
            content = call(params.get('name'),params.get('arguments',{}))
            return dict(envelope,result={'content':content,'isError':False})
        except Exception as error:
            return dict(envelope,result={'content':[{'type':'text','text':str(error)}],'isError':True})
    return dict(envelope,error={'code':-32601,'message':'Method not found'})

def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            result = response(request)
        except ValueError:
            result = {'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}
        if result is not None:
            print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
