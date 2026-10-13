import copy,json,tempfile,unittest,shutil,sys,os
from pathlib import Path
from rebuild_cloud_readiness import adapt,partial_channel_audit
SOURCE=Path(os.environ.get('HEROVERSE_NATIVE_SOURCE_ROOT',str(Path(__file__).resolve().parents[2]/'source/extracted/project')))
class CloudContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.t=tempfile.TemporaryDirectory();cls.root=Path(cls.t.name)/'project';shutil.copytree(SOURCE,cls.root);cls.overlay=adapt(cls.root)
 @classmethod
 def tearDownClass(cls):cls.t.cleanup()
 def test_cloud_flow_and_linux_mirror_are_explicit_without_scope_expansion(self):
  c=json.loads((self.root/'schemas/youtube_connection_receipt.schema.json').read_text());m=json.loads((self.root/'schemas/oauth_token_mirror_receipt.schema.json').read_text())
  self.assertIn('WEB_SERVER_AUTHORIZATION_CODE',c['properties']['authorization']['properties']['oauth_flow']['enum'])
  self.assertIn('LINUX_TASK_SECRET_OUTSIDE_WORKSPACE',m['properties']['destination_class']['enum'])
  self.assertEqual(m['properties']['required_scopes']['maxItems'],4)
  self.assertEqual(m['properties']['destination_outside_workspace']['const'],True)
 def test_wrong_identity_never_builds_partial_channel_audit(self):
  with self.assertRaises(PermissionError):partial_channel_audit({'id':'foreign'},'2026-10-13T22:18:00Z',{'identity_verified_after_refresh':True})
 def test_partial_channel_does_not_turn_unknown_ypp_or_branding_into_pass(self):
  channel={'id':'UCuMF6pJQkyMzaVoAxFL86yA','statistics':{'subscriberCount':'263','videoCount':'23','viewCount':'2677'},'snippet':{'description':'Christian reflection'}}
  r=partial_channel_audit(channel,'2026-10-13T22:18:00Z',{'identity_verified_after_refresh':True,'receipt_id':'qualified'})
  self.assertFalse(r['publication_gate']['auto_publish_permitted']);self.assertIsNone(r['measurements']['qualified_ypp_watch_hours']);self.assertIsNone(r['measurements']['returning_viewers']);self.assertEqual(r['gates'][0]['status'],'PASS');self.assertTrue(r['publication_gate']['critical_open_gates'])
 def test_overlay_rejects_changed_source(self):
  p=self.root/'hero_engine/oauth_token_mirror.py';original=p.read_bytes();p.write_bytes(b'altered')
  try:
   with self.assertRaises(PermissionError):adapt(self.root)
  finally:p.write_bytes(original)
if __name__=='__main__':unittest.main()
