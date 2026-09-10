import unittest

from draft_tool.browser_actions import record_sku_image_block


class MediaStageReportTests(unittest.TestCase):
    def test_indeterminate_image_marks_unstarted_detail_and_weight(self):
        report = {'fields': {}}
        reason = record_sku_image_block(report, {'indeterminate': True, 'safe_to_continue': True})
        self.assertEqual(reason, 'blocked_sku_image_transaction')
        self.assertEqual(report['result'], reason)
        for name in ('description', 'package_dimensions'):
            self.assertEqual(report['fields'][name]['status'], 'not_started')
            self.assertEqual(report['fields'][name]['blocked_by'], 'sku_images')
            self.assertEqual(report['fields'][name]['reason'], reason)
        self.assertFalse(report['fields']['description']['saved'])

    def test_confirmed_image_does_not_mark_later_stages_blocked(self):
        report = {'fields': {}}
        self.assertIsNone(record_sku_image_block(report, {'status': 'confirmed'}))
        self.assertEqual(report, {'fields': {}})

    def test_existing_stage_results_are_preserved(self):
        report = {'fields': {'description': {'saved': True, 'status': 'confirmed'}}}
        record_sku_image_block(report, {'safe_to_continue': False})
        self.assertEqual(report['fields']['description'], {'saved': True, 'status': 'confirmed'})
