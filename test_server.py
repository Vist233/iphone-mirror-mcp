"""Offline protocol and transaction checks. Does not connect to the phone."""
import fcntl
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_zero_scroll_preserved(self):
        with patch.object(server,'run',return_value={'ok':True}) as driver, patch.object(server,'observe',return_value=([],[])):
            server.call('mirror_scroll',{'dy':0})
            driver.assert_called_once_with('scroll',0)

    def test_unverified_key_never_invokes_driver(self):
        with patch.object(server,'run') as driver:
            result=self.request('tools/call',{'name':'mirror_key','arguments':{'key':'tab'}})
            self.assertTrue(result['result']['isError'])
            driver.assert_not_called()

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
                    result=self.request('tools/call',{'name':'mirror_home','arguments':{}})
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
            result=self.request('tools/call',{'name':'mirror_type','arguments':{'text':'hello\n'}})
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
            reply=self.request('tools/call',{'name':'mirror_home','arguments':{}})['result']
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

if __name__=='__main__':
    unittest.main()
