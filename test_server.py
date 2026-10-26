"""Offline protocol and transaction checks. Does not connect to the phone."""
import fcntl
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import threading
import unittest
from unittest.mock import patch, Mock

import server

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory(prefix='mirror-test-lock-')
        self.addCleanup(directory.cleanup)
        lock=patch.object(server,'LOCK_PATH',Path(directory.name)/'device.lock')
        lock.start()
        self.addCleanup(lock.stop)

    def request(self, method, params=None):
        request = {'jsonrpc':'2.0','id':1,'method':method}
        if params is not None:
            request['params'] = params
        return server.response(request)

    def test_version_fallback(self):
        result = self.request('initialize', {'protocolVersion':'future'})
        self.assertIn(result['result']['protocolVersion'],server.VERSIONS)

    def test_notification_has_no_response(self):
        self.assertIsNone(server.response({'jsonrpc':'2.0','method':'notifications/initialized'}))

    def test_tool_names_unique(self):
        tools = self.request('tools/list')['result']['tools']
        self.assertEqual(len(tools),len({tool['name'] for tool in tools}))

    def test_invalid_params(self):
        self.assertEqual(self.request('ping',[])['error']['code'],-32602)

    def test_invalid_coordinates_never_invoke_driver(self):
        for arguments in [{'x':float('nan'),'y':.5},{'x':True,'y':.5},{'x':1,'y':.5},{'x':.5},
                          {'x':.5,'y':.5,'unexpected':1}]:
            with self.subTest(arguments=arguments), patch.object(server,'run') as driver:
                result=self.request('tools/call',{'name':'mirror_tap','arguments':arguments})
                self.assertTrue(result['result']['isError'])
                driver.assert_not_called()

    def test_scroll_forwards_one_page_request(self):
        with patch.object(server,'run',return_value={'ok':True}) as driver, patch.object(server,'observe',return_value=([],[])):
            for dy in (-50,50):
                with self.subTest(dy=dy):
                    driver.reset_mock()
                    server.call('mirror_scroll',{'dy':dy})
                    driver.assert_called_once_with('scroll',dy)

    def test_scroll_rejects_magnitude_outside_one_page(self):
        with patch.object(server,'run') as driver:
            for dy in (-51,51,-2000,2000,0,-1,1,-49,49):
                with self.subTest(dy=dy):
                    result=self.request('tools/call',{'name':'mirror_scroll','arguments':{'dy':dy}})
                    self.assertTrue(result['result']['isError'])
            driver.assert_not_called()

    def test_unverified_key_never_invokes_driver(self):
        with patch.object(server,'run') as driver:
            result=self.request('tools/call',{'name':'mirror_key','arguments':{'key':'tab'}})
            self.assertTrue(result['result']['isError'])
            driver.assert_not_called()

    def test_consolidated_navigation(self):
        with patch.object(server,'run',return_value={'ok':True}) as driver, patch.object(server,'observe',return_value=([],[])):
            for destination in ('home','spotlight','app_switcher'):
                server.call('mirror_navigate',{'destination':destination})
                driver.assert_called_with(destination)

    def test_consolidated_input_routes(self):
        with patch.object(server,'run',return_value={'ok':True}) as driver, patch.object(server,'observe',return_value=([],[])):
            for arguments, expected in [
                ({'action':'text','text':'中文😀'},('text','中文😀')),
                ({'action':'text','text':'Hello','mode':'ascii','replace':True},('type','Hello','replace')),
                ({'action':'enter'},('key','return')),
            ]:
                server.call('mirror_input',arguments)
                driver.assert_called_with(*expected)

    def test_input_rejects_ambiguous_enter(self):
        with patch.object(server,'run') as driver:
            for arguments in ({'action':'text'},{'action':'enter','text':'hello'},{'action':'enter','replace':True}):
                self.assertTrue(self.request('tools/call',{'name':'mirror_input','arguments':arguments})['result']['isError'])
            driver.assert_not_called()

    def test_scroll_direction_routes(self):
        with patch.object(server,'run',return_value={'ok':True}) as driver, patch.object(server,'observe',return_value=([],[])):
            for direction, expected in [('up',('scroll',50)),('down',('scroll',-50)),('left',('scroll',50,'horizontal')),('right',('scroll',-50,'horizontal'))]:
                server.call('mirror_scroll',{'direction':direction})
                driver.assert_called_with(*expected)
            for arguments in ({},{'dy':50,'direction':'left'}):
                with self.assertRaises(ValueError):
                    server.call('mirror_scroll',arguments)

    def test_ambiguous_text_does_not_click(self):
        rows=[{'text':'Settings','x':.2,'y':.3},{'text':'Settings','x':.7,'y':.3}]
        with patch.object(server,'observe',return_value=([],rows)), patch.object(server,'run') as driver:
            result=self.request('tools/call',{'name':'mirror_tap_text','arguments':{'text':'Settings'}})
            self.assertTrue(result['result']['isError'])
            driver.assert_not_called()

    def test_busy_device_does_not_invoke_driver(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'LOCK_PATH',Path(directory)/'device.lock'):
            holder=subprocess.Popen([sys.executable,'-c',
                'import fcntl,sys; f=open(sys.argv[1],"w"); fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); sys.stdin.read()',
                str(server.LOCK_PATH)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(holder.stdout.readline().strip(),'locked')
                with patch.object(server,'run') as driver:
                    result=self.request('tools/call',{'name':'mirror_navigate','arguments':{'destination':'home'}})
                    self.assertIn('Device busy',result['result']['content'][0]['text'])
                    driver.assert_not_called()
            finally:
                holder.communicate(timeout=5)

    def test_parse_error_recovers(self):
        result=subprocess.run([sys.executable,str(Path(server.__file__))],input='{bad}\n'+json.dumps({'jsonrpc':'2.0','id':2,'method':'ping'})+'\n',capture_output=True,text=True,timeout=5)
        replies=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r.get('error',{}).get('code',r['id']) for r in replies],[-32700,2])

    def test_control_characters_never_reach_driver(self):
        with patch.object(server,'run') as driver:
            result=self.request('tools/call',{'name':'mirror_input','arguments':{'action':'text','text':'hello\n'}})
            self.assertTrue(result['result']['isError'])
            driver.assert_not_called()

    def test_unicode_event_boundaries_preserve_surrogate_pairs(self):
        source=ast.parse((Path(server.__file__).parent/'mirror_driver.py').read_text())
        function=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='unicode_chunks')
        namespace={}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'unicode_chunks','exec'),namespace)
        text='a'*15+'😀'+'中文'+'👨‍👩‍👧‍👦'+'b'*20
        chunks=list(namespace['unicode_chunks'](text))
        self.assertEqual(''.join(chunks),text)
        self.assertTrue(all(0<len(chunk.encode('utf-16-le'))//2<=16 for chunk in chunks))

    def test_observation_failure_preserves_submitted_action(self):
        submitted={'ok':True,'submission':'submitted','phone_effect_verified':False}
        with patch.object(server,'run',return_value=submitted) as driver, patch.object(server,'observe',side_effect=RuntimeError('capture unavailable')):
            reply=self.request('tools/call',{'name':'mirror_navigate','arguments':{'destination':'home'}})['result']
        self.assertFalse(reply['isError'])
        self.assertEqual(json.loads(reply['content'][0]['text']),submitted)
        self.assertFalse(json.loads(reply['content'][1]['text'])['retry_action'])
        driver.assert_called_once_with('home')

    def test_launcher_forwards_arguments_without_pyenv(self):
        with tempfile.TemporaryDirectory(prefix='mirror launch ') as directory:
            runtime=Path(directory)/'fake-python'
            runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            runtime.chmod(0o755)
            launcher=Path(server.__file__).parent/'mirror-driver'
            result=subprocess.run([str(launcher),'text','中文 with spaces'],
                env={'PATH':'/usr/bin:/bin','MIRROR_PYTHON':str(runtime)},capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.splitlines(),[str(launcher.parent/'mirror_driver.py'),'text','中文 with spaces'])

class ScrollDriverTests(unittest.TestCase):
    """Run the actual driver functions with no macOS event side effects."""

    def functions(self, names, namespace):
        tree = ast.parse((Path(server.__file__).parent / 'mirror_driver.py').read_text())
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'driver-under-test', 'exec'), namespace)
        return namespace

    def driver_main(self, enabled=True):
        baseline = {'front_pid': 10, 'keyboard_pid': 10, 'cursor': [20, 30]}
        namespace = {
            'target': lambda: (11, 12, {'X': 0, 'Y': 0, 'Width': 300, 'Height': 600}),
            'focus_state': lambda: dict(baseline),
            'Q': types.SimpleNamespace(CGPreflightPostEventAccess=lambda: True),
            'tempfile': tempfile, 'Path': Path,
            'read_text': lambda *args: [{'text': 'Settings'}],
            'os': types.SimpleNamespace(environ={'MIRROR_ENABLE_EXPERIMENTAL_INPUT': '1'} if enabled else {}),
            'internal_active': lambda pid: False,
            'threading': types.SimpleNamespace(Event=threading.Event, Thread=Mock()),
            'time': types.SimpleNamespace(sleep=lambda delay: None),
            'prime': Mock(), 'record': Mock(),
            'post_wheel_records': Mock(return_value=[0, 0]),
            'MAX_WHEEL_MAGNITUDE': 50, 'DEFAULT_SCHEME': 'a1',
            'WHEEL_RECORD_SETTLE_SECONDS': .65,
        }
        return self.functions({'main'}, namespace)

    def test_a1_scroll_never_primes_or_changes_activation(self):
        driver = self.driver_main()
        result = driver['main'](['scroll', '50'])
        driver['prime'].assert_not_called()
        driver['record'].assert_not_called()
        self.assertEqual(result['record_statuses'], [0, 0])
        self.assertFalse(result['phone_effect_verified'])
        self.assertEqual(driver['post_wheel_records'].call_args.args[2], 50)

    def test_invalid_scroll_does_not_send_or_prime(self):
        for value in ('0', '1', '-49', '51', '2000'):
            with self.subTest(value=value):
                driver = self.driver_main()
                with self.assertRaises(ValueError):
                    driver['main'](['scroll', value])
                driver['prime'].assert_not_called()
                driver['record'].assert_not_called()
                driver['post_wheel_records'].assert_not_called()

    def test_horizontal_scroll_selects_modifier_route_without_priming(self):
        driver = self.driver_main()
        driver['main'](['scroll','50','horizontal'])
        self.assertTrue(driver['post_wheel_records'].call_args.kwargs['horizontal'])
        driver['prime'].assert_not_called()
        driver['record'].assert_not_called()

    def test_horizontal_builder_keeps_two_records(self):
        namespace = {'WHEEL_RECORD_COUNT':2, 'wheel_record':Mock()}
        self.functions({'build_plain_wheel'},namespace)
        events = namespace['build_plain_wheel']('source',50,(1,2),True)
        self.assertEqual(len(events),2)
        self.assertEqual(namespace['wheel_record'].call_count,2)
        namespace['wheel_record'].assert_called_with('source',50,(1,2),True)

    def test_scroll_is_disabled_without_explicit_opt_in(self):
        driver = self.driver_main(enabled=False)
        with self.assertRaises(RuntimeError):
            driver['main'](['scroll', '50'])
        driver['post_wheel_records'].assert_not_called()

    def test_unpublished_scheme_is_rejected_before_input(self):
        driver = self.driver_main()
        driver['os'].environ['MIRROR_SCROLL_SCHEME'] = 'c2'
        with self.assertRaises(ValueError):
            driver['main'](['scroll', '50'])
        driver['prime'].assert_not_called()
        driver['post_wheel_records'].assert_not_called()

    def posting(self, current=None, covered=False):
        baseline = {'front_pid': 10, 'keyboard_pid': 10}
        point = (100, 200)
        source = object()
        events = [object(), object()]
        namespace = {
            'DEFAULT_SCHEME': 'a1',
            'uncovered_point': Mock(side_effect=RuntimeError('covered')) if covered else Mock(return_value=point),
            'Q': types.SimpleNamespace(CGEventSourceCreate=Mock(return_value=source)),
            'WINDOW_SERVER_CONNECTION': lambda: 9,
            'build_plain_wheel': Mock(return_value=events),
            'focus_state': lambda: current if current is not None else baseline,
            'EVENT_RECORD_POINTER': lambda event: event,
            'objc': types.SimpleNamespace(pyobjc_id=lambda event: event),
            'POST_WINDOW_RECORD': Mock(return_value=0),
            'time': types.SimpleNamespace(sleep=lambda delay: None),
            'WHEEL_RECORD_LENGTH': 0xf8, 'WHEEL_RECORD_INTERVAL_SECONDS': .04,
        }
        return self.functions({'post_wheel_records'}, namespace), baseline, source, point

    def test_a1_posts_two_records_and_preserves_direction(self):
        for delta in (-50, 50):
            with self.subTest(delta=delta):
                driver, baseline, source, point = self.posting()
                result = driver['post_wheel_records'](12, {}, delta, baseline)
                driver['build_plain_wheel'].assert_called_once_with(source, delta, point)
                self.assertEqual(result, [0, 0])
                self.assertEqual(driver['POST_WINDOW_RECORD'].call_count, 2)

    def test_covered_mirror_posts_nothing(self):
        driver, baseline, _, _ = self.posting(covered=True)
        with self.assertRaises(RuntimeError):
            driver['post_wheel_records'](12, {}, 50, baseline)
        driver['POST_WINDOW_RECORD'].assert_not_called()

    def test_focus_change_stops_before_posting(self):
        driver, baseline, _, _ = self.posting(current={'front_pid': 99, 'keyboard_pid': 99})
        with self.assertRaises(RuntimeError):
            driver['post_wheel_records'](12, {}, 50, baseline)
        driver['POST_WINDOW_RECORD'].assert_not_called()


if __name__=='__main__':
    unittest.main()
