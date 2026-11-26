"""补的回归：换稿窗口内的开条、续播、迟报与重开语义。

原有回归（tests/ 下既有用例与 incident_cutover.py 的两个故障窗口）保持不变，
这里只补原用例未直接钉住的不变量。
"""
import json
import sqlite3

from tests.support import HTTPCase, event, example


class TestCutoverWindow(HTTPCase):
    def test_tail_keeps_opening_draft_through_preload(self):
        # 即便尾段在首段点亮后做过预取，仍按该条首段的实显稿续播。
        old, new = self.open_example()
        self.advance('C17', 1)
        self.get('/preview', **self.binding, cue='C17', segment=2)
        self.correct(new)
        tail = self.advance('C17', 2)
        self.assertEqual((tail['revision'], tail['lines']), (old, ['请入座']))
        self.assertEqual(self.events(), [event(1, 'C17', 1, old), event(2, 'C17', 2, old)])

    def test_unopened_cue_waits_and_sends_nothing_while_pending(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        self.screen.hidden_cutovers.add(self.first_correction)
        self.correct(new, expected=202)
        # 已开条的 C17 尾段按原稿续播；未开条的 C18 在勘误未查实时等待，
        # 屏端不会留下任何指令或实显。
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.advance('C18', 1, 202)
        self.assertIsNone(self.screen.outcomes.find_segment('S7', 'P1', 'C18', 1))
        self.assertEqual(self.events(), [
            event(1, 'C17', 1, old), event(2, 'C17', 2, old),
        ])
        # 查实后重送同一请求号，C18 从新稿开播。
        self.screen.hidden_cutovers.remove(self.first_correction)
        opening = self.correct(new)
        self.assertEqual(opening['status'], 'confirmed')
        lit = self.advance('C18', 1)
        self.assertEqual((lit['revision'], lit['lines']), (new, ['右侧入']))
        self.assertEqual(self.events(), [
            event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, new),
        ])

    def test_cutover_before_first_light_restarts_cue_on_new_draft(self):
        old, new = self.open_example()
        # 首段从未点亮时换稿先落实，该条直接从新稿开始，首段实显稿号即新稿。
        self.correct(new)
        first = self.advance('C17', 1)
        self.assertEqual((first['revision'], first['lines']), (new, ['请稍候']))
        tail = self.advance('C17', 2)
        self.assertEqual((tail['revision'], tail['lines']), (new, ['请就座']))
        self.assertEqual(self.events(), [
            event(1, 'C17', 1, new), event(2, 'C17', 2, new),
        ])

    def test_switching_back_to_same_revision_keeps_stale_command_dead(self):
        old, new = self.open_example()
        self.screen.paused_segments.add(self.first_segment)
        # 旧的开条指令（纪元 0）在链路中滞留。
        self.advance('C17', 1, 202)
        self.correct(new)                       # 纪元推进到 1
        self.correct(old, request='Q2')        # 稿号回到 R1，但纪元为 2
        with self.assertRaisesRegex(Exception, 'opening command has expired'):
            self.screen.release_segment(self.first_segment)
        self.assertEqual(self.events(), [])
        # 重开后的新指令带当前纪元，稿号虽同为 R1 仍可正常点亮。
        lit = self.advance('C17', 1)
        self.assertEqual((lit['revision'], lit['sequence']), (old, 1))
        self.assertEqual(self.events(), [event(1, 'C17', 1, old)])

    def test_superseded_cutover_still_confirms_from_screen_history(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        # Q1 在屏端落实但领播端暂时查不到；随后 Q2 落实并成为当前活动稿。
        self.screen.hidden_cutovers.add(self.first_correction)
        self.correct(new, expected=202)
        third_data = example('amendment')
        third_data['cues'][1]['segments'] = ['中间入']
        newest = self.publish(third_data)['revision']
        self.correct(newest, request='Q2')
        # 补查通道恢复后重放 Q1：屏端历史记着它落实过，确认但不回滚活动稿。
        self.screen.hidden_cutovers.remove(self.first_correction)
        first = self.status()
        self.assertEqual((first['status'], first['revision']), ('confirmed', new))
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.assertEqual(self.advance('C18', 1)['lines'], ['中间入'])
        self.assertEqual(self.events(), [
            event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, newest),
        ])

    def test_duplicate_reports_do_not_rewrite_history(self):
        old, _ = self.open_example()
        self.screen.hidden_segments.add(self.first_segment)
        self.advance('C17', 1, 202)
        first = self.screen.outcomes.find_segment(*self.first_segment)
        self.screen.hidden_segments.remove(self.first_segment)
        # 同一条实显回报送达两次：账本只认第一次，历史不变。
        self.app.receive_display(first)
        self.app.receive_display(first)
        ledger = self.app.ledger.list_for_screen('S7', 'P1')
        self.assertEqual([(event.sequence, event.cue, event.segment) for event in ledger], [(1, 'C17', 1)])
        self.assertEqual(self.advance('C17', 1)['sequence'], 1)
        self.assertEqual(self.events(), [event(1, 'C17', 1, old)])


class TestScreenSchemaMigration(HTTPCase):
    def test_legacy_screen_database_recovers_without_losing_draft_pinning(self):
        old, new = self.open_example()
        self.advance('C17', 1)
        self.screen.hidden_cutovers.add(self.first_correction)
        self.correct(new, expected=202)
        self.stop_server()

        # 手工造一个修复前的旧版屏端库：无 cutover_epoch / applied 列，
        # cutovers 行的存在即代表旧版“已准备”。
        display_db = self.directory / 'display.sqlite3'
        payloads = {}
        with sqlite3.connect(display_db) as connection:
            for revision, payload in connection.execute(
                'SELECT revision, payload FROM screen_editions'
            ):
                payloads[revision] = payload
        display_db.unlink()
        with sqlite3.connect(display_db) as connection:
            connection.executescript('''
                CREATE TABLE screen_editions (
                    revision TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE sessions (
                    show TEXT NOT NULL,
                    screen TEXT NOT NULL,
                    initial_revision TEXT NOT NULL REFERENCES screen_editions(revision),
                    active_revision TEXT NOT NULL REFERENCES screen_editions(revision),
                    closed INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (show, screen)
                );
                CREATE TABLE lit_events (
                    show TEXT NOT NULL,
                    screen TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    cue TEXT NOT NULL,
                    segment INTEGER NOT NULL,
                    revision TEXT NOT NULL REFERENCES screen_editions(revision),
                    lines TEXT NOT NULL,
                    PRIMARY KEY (show, screen, sequence),
                    UNIQUE (show, screen, cue, segment),
                    FOREIGN KEY (show, screen) REFERENCES sessions(show, screen)
                );
                CREATE TABLE cutovers (
                    show TEXT NOT NULL,
                    screen TEXT NOT NULL,
                    request TEXT NOT NULL,
                    revision TEXT NOT NULL REFERENCES screen_editions(revision),
                    epoch INTEGER NOT NULL,
                    PRIMARY KEY (show, screen, request),
                    UNIQUE (show, screen, epoch),
                    FOREIGN KEY (show, screen) REFERENCES sessions(show, screen)
                );
            ''')
            connection.executemany('INSERT INTO screen_editions VALUES (?, ?)', payloads.items())
            connection.execute(
                'INSERT INTO sessions VALUES (?, ?, ?, ?, ?)',
                ('S7', 'P1', old, old, 0),
            )
            connection.execute(
                'INSERT INTO lit_events VALUES (?, ?, ?, ?, ?, ?, ?)',
                ('S7', 'P1', 1, 'C17', 1, old, json.dumps(['稍候', '开灯'], ensure_ascii=False)),
            )
            connection.execute(
                'INSERT INTO cutovers (show, screen, request, revision, epoch) VALUES (?, ?, ?, ?, ?)',
                ('S7', 'P1', 'Q1', new, 1),
            )

        # 重开服务时旧库自动补列；旧的“已准备”行迁移后 applied=0，仍视为未落实，
        # 故查询保持待定，重放原请求号同参后才确认。
        self.start_server()
        self.status(expected=202)
        # C17 尾段仍按首段的 R1 续播；C18 未开条，继续等待。
        self.assertEqual(self.advance('C17', 2)['revision'], old)
        self.advance('C18', 1, 202)
        self.assertEqual(self.correct(new)['revision'], new)
        lit = self.advance('C18', 1)
        self.assertEqual((lit['revision'], lit['lines']), (new, ['右侧入']))
        self.assertEqual(self.events(), [
            event(1, 'C17', 1, old), event(2, 'C17', 2, old), event(3, 'C18', 1, new),
        ])
