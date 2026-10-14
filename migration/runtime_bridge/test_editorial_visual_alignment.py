import unittest
from editorial_visual_alignment import require_alignment
class EditorialAlignmentTests(unittest.TestCase):
    def music(self):
        return {'voice_required':True,'recipe':{'editorial':{'title':'Rest Is Not Giving Up | A Christian Reflection + Quiet Piano for Prayer'}}}
    def test_real_historical_wrong_treatment_is_rejected(self):
        with self.assertRaisesRegex(PermissionError,'EDITORIAL_VISUAL_PROMISE_MISMATCH'):
            require_alignment(self.music(),{'layout':{'title':'One Faithful Step Under Pressure'}})
    def test_coherent_visual_is_not_a_publication_approval(self):
        result=require_alignment(self.music(),{'layout':{'title':'Rest Is Not Giving Up'}})
        self.assertFalse(result['quality_authorized']);self.assertFalse(result['publication_authorized'])
    def test_missing_visual_cannot_borrow_an_audio_title(self):
        for value in ({},{'layout':{'title':''}},{'layout':{'title':None}}):
            with self.assertRaises(PermissionError):require_alignment(self.music(),value)
if __name__=='__main__':unittest.main()
