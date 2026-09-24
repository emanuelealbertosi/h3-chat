import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    def test_console_follows_appended_unicode_logs_until_server_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp);log=data/'server.log';log.write_bytes(b'Server pronto\n')
            ticks=iter([True,True,False,False])
            def health(*args):
                alive=next(ticks)
                if not alive:raise OSError('stopped')
                with log.open('ab') as out:out.write('Errore: metà del contesto\n'.encode('utf-8'))
                return {'instance':launcher.INSTANCE}
            output=io.StringIO()
            with patch.object(launcher,'DATA',data),patch.object(launcher,'get',side_effect=health),patch.object(launcher.time,'sleep'),patch.object(launcher.time,'monotonic',side_effect=range(0,100,3)),contextlib.redirect_stdout(output):
                launcher.follow_logs(8787)
            text=output.getvalue()
            self.assertIn('Server pronto',text)
            self.assertEqual(text.count('Errore: metà del contesto'),2)
            self.assertIn('non è più in esecuzione',text)

    def test_existing_server_reuses_process_and_keeps_log_view_open(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp);(data/'port.json').write_text(json.dumps(8790))
            with patch.object(launcher,'DATA',data),patch.object(launcher,'get',return_value={'app':'h3-chat','instance':launcher.INSTANCE}),patch.object(launcher.subprocess,'Popen') as spawn,patch.object(launcher,'follow_logs') as follow,patch.object(launcher.sys,'argv',['launcher.py','--logs-only']):
                launcher.main()
            spawn.assert_not_called()
            follow.assert_called_once_with(8790)

    def test_stop_does_not_open_a_console_monitor(self):
        with tempfile.TemporaryDirectory() as temp:
            values=[{'app':'h3-chat','instance':launcher.INSTANCE},{'token':'test-token'}]
            with patch.object(launcher,'DATA',Path(temp)),patch.object(launcher,'get',side_effect=values),patch.object(launcher.urllib.request,'urlopen') as request,patch.object(launcher,'follow_logs') as follow,patch.object(launcher.sys,'argv',['launcher.py','--stop']):
                launcher.main()
            self.assertEqual(request.call_args.args[0].full_url,'http://127.0.0.1:8787/api/shutdown')
            follow.assert_not_called()
