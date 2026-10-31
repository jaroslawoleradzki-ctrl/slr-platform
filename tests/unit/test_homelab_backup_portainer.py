"""Disposable, standard-library regression checks for Portainer backups."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'backup_homelab.py'
spec = importlib.util.spec_from_file_location('homelab_backup', SCRIPT)
backup = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backup
spec.loader.exec_module(backup)


class PortainerBackupTests(unittest.TestCase):
    def test_defaults_do_not_depend_on_removed_deployment_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            config = backup._config_from_environment()
        self.assertEqual(config.compose_project, 'slr-platform')
        self.assertIsNone(config.compose_file)
        self.assertIsNone(config.env_file)
        self.assertEqual(config.portainer_stack_id, 18)

    def test_private_token_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'token'
            p.write_text('test-token-never-print')
            p.chmod(0o644)
            with self.assertRaises(backup.BackupError):
                backup._read_private_file(p)
            p.chmod(0o600)
            self.assertEqual(backup._read_private_file(p), 'test-token-never-print')
            link = Path(tmp) / 'link'
            link.symlink_to(p)
            with self.assertRaises(backup.BackupError):
                backup._read_private_file(link)

    def test_api_configuration_is_self_contained_and_private(self):
        with patch.dict(os.environ, {}, clear=True):
            config = backup._config_from_environment()
        compose = json.dumps({'services': {'slr-platform': {
            'image': 'slr-platform:v0.7.9-fix',
            'environment': {'FIXTURE_SECRET': 'fixture-only'},
        }}})
        replies = [
            {'Id': 18, 'Name': 'slr-platform', 'EndpointId': 3, 'Type': 2,
             'Status': 1, 'WorkflowID': 0},
            {'StackFileContent': compose},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch.object(backup, '_portainer_get', side_effect=replies):
                backup._save_portainer_configuration(config, directory)
            self.assertEqual((directory / 'compose.prod.yaml').read_text(), compose)
            self.assertEqual((directory / 'compose.prod.yaml').stat().st_mode & 0o777, 0o600)
            self.assertNotIn('fixture-only', (directory / 'stack-metadata.json').read_text())
            self.assertNotIn('test-token', (directory / 'stack-metadata.json').read_text())

    def test_rejects_another_stack_or_git_deployment(self):
        config = backup._config_from_environment()
        for obj in [
            {'Name': 'another-stack', 'EndpointId': 3, 'Type': 2, 'Status': 1},
            {'Name': 'slr-platform', 'EndpointId': 3, 'Type': 2, 'Status': 1, 'WorkflowID': 1},
        ]:
            with tempfile.TemporaryDirectory() as tmp:
                with patch.object(backup, '_portainer_get', return_value=obj):
                    with self.assertRaises(backup.BackupError):
                        backup._save_portainer_configuration(config, Path(tmp))

    def test_command_errors_never_include_secret_stderr(self):
        import subprocess
        error = subprocess.CalledProcessError(1, ['docker'], stderr='FIXTURE_SECRET=must-not-leak')
        with patch.object(backup.subprocess, 'run', side_effect=error):
            with self.assertRaises(backup.BackupError) as cm:
                backup._run(['docker', 'compose', 'config'])
        self.assertNotIn('must-not-leak', str(cm.exception))

    def test_tls_pin_failure_sends_no_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            token, pin = Path(tmp) / 'token', Path(tmp) / 'pin'
            token.write_text('fixture-token')
            pin.write_text('0' * 64)
            token.chmod(0o600)
            pin.chmod(0o600)
            config = replace(backup._config_from_environment(),
                             portainer_token_file=token, portainer_pin_file=pin)
            with patch.object(backup.http.client, 'HTTPSConnection') as factory:
                conn = factory.return_value
                conn.sock.getpeercert.return_value = b'untrusted-certificate'
                with self.assertRaises(backup.BackupError):
                    backup._portainer_get(config, '/stacks/18')
                conn.request.assert_not_called()

    def test_saved_compose_cannot_silently_restore_different_environment(self):
        config = backup._config_from_environment()
        service = {'image': 'slr-platform:v0.7.9-fix',
                   'environment': {'KEY': 'restored-different'},
                   'restart': 'unless-stopped', 'ulimits': {},
                   'command': ['server'], 'working_dir': '/app',
                   'volumes': [], 'ports': [], 'networks': {'default': {}}}
        current = {'Config': {'Image': service['image'], 'Env': ['KEY=original'],
                             'Cmd': ['server'], 'WorkingDir': '/app'},
                   'HostConfig': {'PortBindings': {}, 'Ulimits': [], 'LogConfig': {'Type': 'json-file', 'Config': {}},
                                  'RestartPolicy': {'Name': 'unless-stopped'}},
                   'Mounts': [], 'NetworkSettings': {'Networks': {'slr-platform_default': {}}}}
        rendered = {'services': {'slr-platform': service},
                    'networks': {'default': {'name': 'slr-platform_default'}}}
        with patch.object(backup, '_run', side_effect=[json.dumps(rendered), json.dumps([current])]):
            with self.assertRaises(backup.BackupError) as cm:
                backup._validate_saved_configuration(config, Path('/disposable'))
        self.assertNotIn('original', str(cm.exception))
        self.assertNotIn('restored-different', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
