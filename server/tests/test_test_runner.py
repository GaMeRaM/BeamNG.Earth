"""Failure reporting must survive a Windows legacy console encoding."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class RunnerEncodingTest(unittest.TestCase):
    def test_unicode_failure_is_reported(self):
        runner = Path(__file__).resolve().parents[2] / 'tools' / 'run_tests.py'
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, '_fixture_unicode_failure.py').write_text(
                "import unittest\nclass F(unittest.TestCase):\n"
                " def test_failure(self): self.fail('Ошибка проверки')\n", encoding='utf-8')
            env = dict(os.environ, PYTHONPATH=tmp + os.pathsep + os.environ.get('PYTHONPATH', ''),
                       PYTHONIOENCODING='cp1252', PYTHONUTF8='0')
            result = subprocess.run([sys.executable, str(runner), '_fixture_unicode_failure',
                                     '--par', '1', '--timeout', '20', '--logs', str(Path(tmp, 'logs'))],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)
            output = result.stdout.decode('utf-8')
            self.assertEqual(result.returncode, 1, output)
            self.assertIn('Ошибка проверки', output)
            self.assertIn('AssertionError', output)
            self.assertNotIn('UnicodeEncodeError', output)
