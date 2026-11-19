"""Native backend maintenance safety; no real processes are changed by tests."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import psutil
import backend_process as backend


class BackendMaintenanceTests(unittest.TestCase):
    def connection(self,pid): return SimpleNamespace(status=psutil.CONN_LISTEN,laddr=SimpleNamespace(port=8000),pid=pid)
    def process(self,root,valid=True):
        return Mock(cmdline=Mock(return_value=[str(root/'.venv/Scripts/python.exe'),'main.py'] if valid else ['other.exe','main.py']),cwd=Mock(return_value=str(root)))

    def test_checks_all_owners_before_stopping_any(self):
        root=Path('test-backend').resolve()
        first,other=self.process(root),self.process(root,False)
        with patch.object(backend,'ROOT',root),patch.object(backend,'listeners',return_value={10,20}),patch('backend_process.psutil.Process',side_effect=lambda pid:first if pid==10 else other):
            with self.assertRaisesRegex(ValueError,'unrecognized service'): backend.maintenance('stop')
        first.terminate.assert_not_called(); other.terminate.assert_not_called()

    def test_same_name_in_wrong_directory_is_not_stopped(self):
        root=Path('test-backend').resolve(); process=self.process(root)
        process.cwd.return_value=str(root.parent)
        with patch.object(backend,'ROOT',root),patch.object(backend,'listeners',return_value={10}),patch('backend_process.psutil.Process',return_value=process):
            with self.assertRaisesRegex(ValueError,'unrecognized service'): backend.maintenance('stop')
        process.terminate.assert_not_called()

    def test_known_backend_stops_and_waits_for_exit(self):
        root=Path('test-backend').resolve(); process=self.process(root)
        with patch.object(backend,'ROOT',root),patch.object(backend,'listeners',return_value={10}),patch('backend_process.psutil.Process',return_value=process),patch('backend_process.psutil.wait_procs',return_value=([process],[])) as wait:
            self.assertEqual(backend.maintenance('stop'),{'was_running':True})
        process.terminate.assert_called_once(); wait.assert_called_once_with([process],timeout=10)

    def test_windows_access_denial_has_clear_message(self):
        with patch.object(backend,'listeners',side_effect=psutil.AccessDenied()):
            with self.assertRaisesRegex(ValueError,'same Windows user'): backend.maintenance('stop')

    def test_ipv4_ipv6_same_owner_is_counted_once(self):
        with patch('backend_process.psutil.net_connections',return_value=[self.connection(10),self.connection(10)]):
            self.assertEqual(backend.listeners(),{10})

    def test_unknown_owner_is_rejected(self):
        with patch('backend_process.psutil.net_connections',return_value=[self.connection(None)]):
            with self.assertRaisesRegex(ValueError,'Cannot identify'): backend.listeners()

    def test_start_refuses_occupied_port(self):
        with patch.object(backend,'listeners',return_value={10}),patch('backend_process.subprocess.Popen') as start:
            with self.assertRaisesRegex(ValueError,'already in use'): backend.maintenance('start')
        start.assert_not_called()

    def test_hidden_start_uses_fixed_executable_and_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); python=root/'.venv/Scripts/python.exe'
            python.parent.mkdir(parents=True); python.touch(); (root/'main.py').touch()
            with patch.object(backend,'ROOT',root),patch.object(backend,'listeners',return_value=set()),patch('backend_process.subprocess.Popen') as start:
                self.assertEqual(backend.maintenance('start'),{'started':True})
            arguments,options=start.call_args
            self.assertEqual(arguments[0],[str(python),'main.py'])
            self.assertEqual(options['cwd'],root)
            self.assertNotIn('shell',options)
            self.assertEqual(options['creationflags'],getattr(backend.subprocess,'CREATE_NO_WINDOW',0))


if __name__=='__main__': unittest.main()
