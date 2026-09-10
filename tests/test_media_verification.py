import base64
import hashlib
import unittest
from unittest.mock import MagicMock, patch

from draft_tool.media_verification import verified_image
from draft_tool.security import MAX_IMAGE_BYTES


class MediaVerificationTests(unittest.TestCase):
    def test_content_not_filename_establishes_identity(self):
        digest = hashlib.sha256(b'expected').hexdigest()
        cache = {}
        wrong = {'title':'same.png','src':'data:image/png;base64,'+base64.b64encode(b'wrong').decode()}
        correct = {'title':'different.png','src':'data:image/png;base64,'+base64.b64encode(b'expected').decode()}
        self.assertFalse(verified_image(wrong,digest,cache))
        self.assertTrue(verified_image(correct,digest,cache))
        self.assertFalse(verified_image({**correct,'loaded':False},digest,cache))

    @patch('draft_tool.security.build_opener')
    def test_network_content_check_is_cached_and_cookie_free(self, opener):
        response = MagicMock()
        response.geturl.return_value='https://cbu01.alicdn.com/sku.png'
        response.headers={'Content-Type':'image/png'}
        response.read.return_value=b'expected'
        opener.return_value.open.return_value.__enter__.return_value=response
        record={'src':response.geturl.return_value}; digest=hashlib.sha256(b'expected').hexdigest(); cache={}
        self.assertTrue(verified_image(record,digest,cache))
        self.assertTrue(verified_image(record,digest,cache))
        opener.return_value.open.assert_called_once()
        request=opener.return_value.open.call_args.args[0]
        self.assertFalse(request.has_header('Cookie'))
        self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],3)

    @patch('draft_tool.security.build_opener')
    def test_untrusted_urls_are_never_requested(self, opener):
        for url in ('file:///etc/passwd','https://127.0.0.1/x','https://alicdn.com.evil.test/x','http://cbu01.alicdn.com/x'):
            self.assertFalse(verified_image({'src':url},'not-a-digest',{}))
        opener.assert_not_called()

    def test_oversized_inline_image_is_rejected(self):
        self.assertFalse(verified_image({'src':'data:image/png;base64,'+'A'*(MAX_IMAGE_BYTES*4//3+8)},'x',{}))

    @patch('draft_tool.security.build_opener')
    def test_temporary_network_failure_can_recover_on_next_readback(self, opener):
        response=MagicMock()
        response.geturl.return_value='https://cbu01.alicdn.com/sku.png'
        response.headers={'Content-Type':'image/png'}
        response.read.return_value=b'expected'
        manager=MagicMock(); manager.__enter__.return_value=response
        opener.return_value.open.side_effect=[TimeoutError('processing'),manager]
        cache={}; record={'src':response.geturl.return_value}; digest=hashlib.sha256(b'expected').hexdigest()
        self.assertFalse(verified_image(record,digest,cache))
        self.assertTrue(verified_image(record,digest,cache))
