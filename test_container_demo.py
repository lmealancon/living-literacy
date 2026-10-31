"""Container opt-in keeps host/origin checks and the ordinary local default."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from prototype import app_server


class ContainerDemoTests(unittest.TestCase):
    def test_container_listener_is_explicit_and_default_remains_loopback(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'synthetic.sqlite'
            db.touch()
            for extra, expected in (([], '127.0.0.1'), (['--container-demo'], '0.0.0.0')):
                with self.subTest(extra=extra), \
                     patch('sys.argv', ['app_server', '--db', str(db)] + extra), \
                     patch.object(app_server, 'App'), \
                     patch('builtins.print'), \
                     patch.object(app_server, 'ThreadingHTTPServer') as server:
                    app_server.main()
                    self.assertEqual(server.call_args.args[0], (expected, 8765))
                    server.return_value.serve_forever.assert_called_once()

    def test_container_option_does_not_relax_host_and_origin_checks(self):
        handler_class = app_server.make_handler(None)
        handler = handler_class.__new__(handler_class)
        handler.server = SimpleNamespace(server_port=8765)
        handler.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765'}
        self.assertTrue(handler.valid_host())
        self.assertTrue(handler.valid_origin())
        for host, origin in [('evil.example:8765', 'http://127.0.0.1:8765'),
                             ('127.0.0.1:8765', 'https://evil.example'),
                             ('localhost:8765', 'http://localhost:8765')]:
            handler.headers = {'Host': host, 'Origin': origin}
            self.assertFalse(handler.valid_host() and handler.valid_origin())


if __name__ == '__main__':
    unittest.main()
