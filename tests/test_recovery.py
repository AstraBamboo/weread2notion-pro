import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from weread2notionpro.sync_policy import eligible_duration
from weread2notionpro.notion_compat import DatabaseAdapter, PageAdapter
from weread2notionpro import book, read_time
from weread2notionpro.weread_api import WeReadApi
from weread2notionpro.notion_helper import NotionHelper
import yaml


class RecoveryTests(unittest.TestCase):
    def test_duration_boundary(self):
        for value in [None, True, False, '501', -1, 0, 499, 500, float('nan'), float('inf')]:
            self.assertFalse(eligible_duration(value), repr(value))
        for value in [500.1, 501, 1000]:
            self.assertTrue(eligible_duration(value))

    def test_both_writers_reject_before_any_notion_call(self):
        for module in [book, read_time]:
            with patch.object(module, 'notion_helper', Mock()) as helper:
                for duration in [None, 499, 500, '501', float('nan')]:
                    args = [None, 1704067200, duration]
                    if module is book:
                        args.append('book-page')
                    module.insert_to_notion(*args)
                self.assertEqual(helper.mock_calls, [])

    def test_book_writer_preserves_numeric_units(self):
        with patch.object(book, 'notion_helper', Mock()) as helper:
            book.insert_to_notion(None, 1704067200, 501, 'book-page')
            self.assertEqual(helper.client.pages.create.call_args.kwargs['properties']['时长'], {'number':501})

    def test_existing_disqualified_record_is_not_updated_or_deleted(self):
        helper = Mock()
        helper.query_all_by_book.return_value = [{'id':'existing', 'properties':{
            '时间戳': {'number':1704067200}, '时长': {'number':900}}}]
        with patch.object(book, 'notion_helper', helper):
            book.insert_read_data('book-page', {1704067200:500})
        helper.client.pages.update.assert_not_called()
        helper.client.pages.create.assert_not_called()

    def test_data_source_query_and_cache(self):
        client=Mock()
        client.databases.retrieve.return_value={'data_sources':[{'id':'source'}]}
        adapter=DatabaseAdapter(client)
        adapter.query('database', page_size=100)
        adapter.query('database', start_cursor='next')
        client.databases.retrieve.assert_called_once_with(database_id='database')
        client.data_sources.query.assert_called_with(data_source_id='source', start_cursor='next')

    def test_ambiguous_data_source_fails_closed(self):
        client=Mock()
        client.databases.retrieve.return_value={'data_sources':[{'id':'a'},{'id':'b'}]}
        with self.assertRaises(RuntimeError):
            DatabaseAdapter(client).query('database')
        client.data_sources.query.assert_not_called()

    def test_page_parent_and_readback(self):
        client, databases = Mock(), Mock()
        databases.resolve.return_value='source'
        client.pages.create.return_value={'id':'page'}
        client.pages.retrieve.return_value={'properties':{'时长':{'number':501}}}
        PageAdapter(client, databases).create({'database_id':'database'}, properties={'时长':{'number':501}})
        self.assertEqual(client.pages.create.call_args.kwargs['parent'], {'type':'data_source_id','data_source_id':'source'})
        client.pages.retrieve.assert_called_once_with(page_id='page')

    def test_readback_mismatch_fails(self):
        client=Mock()
        client.pages.update.return_value={'id':'page'}
        client.pages.retrieve.return_value={'properties':{'时长':{'number':500}}}
        with self.assertRaises(RuntimeError):
            PageAdapter(client,Mock()).update('page',properties={'时长':{'number':501}})

    def test_preserve_note_blocks(self):
        helper=NotionHelper.__new__(NotionHelper)
        helper.client=Mock()
        helper.delete_block('old-note')
        self.assertEqual(helper.client.mock_calls, [])

    def test_gateway_never_logs_response_body(self):
        api=WeReadApi.__new__(WeReadApi)
        api.session=Mock()
        api.session.post.return_value.ok=False
        api.session.post.return_value.status_code=401
        api.session.post.return_value.text='SENSITIVE'
        with self.assertRaises(RuntimeError) as exc:
            api.request('/shelf/sync')
        self.assertNotIn('SENSITIVE', str(exc.exception))

    def test_daily_uses_daily_not_month_buckets(self):
        api=WeReadApi.__new__(WeReadApi)
        api.request=Mock(return_value={'readTimes':{'1704038400':99999}, 'dailyReadTimes':{'1704124800':501}})
        with patch.dict(os.environ, {'YEAR':'2024'}):
            self.assertEqual(api.get_api_data(), {'readTimes':{'1704124800':501}})

    def test_missing_book_daily_detail_is_not_success(self):
        api=WeReadApi.__new__(WeReadApi)
        with patch.dict(os.environ, {'WEREAD_COOKIE':''}):
            with self.assertRaisesRegex(RuntimeError, '逐书逐日'):
                api.get_read_info('book')

    def test_schedule_and_local_install(self):
        for path in Path('.github/workflows').glob('*.yml'):
            data=yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            self.assertEqual(data['on']['schedule'], [{'cron':'0 5,15 * * 0'}])
            self.assertEqual(data['permissions']['contents'],'read')
            self.assertEqual(data['concurrency']['cancel-in-progress'],'false')
        self.assertIn('-e .',Path('requirements.txt').read_text())
        self.assertNotIn('github-heatmap',Path('requirements.txt').read_text())

if __name__ == '__main__':
    unittest.main()
