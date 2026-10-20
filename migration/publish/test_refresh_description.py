import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import refresh_description as r
DESIRED='Night prayer\n\nChapters\n0:00 Good evening\n0:39 Gratitude\n'
def video(description=None):
 return {'id':r.VIDEO,'etag':'fixture-v1','snippet':{'channelId':r.CHANNEL,'title':'Night Prayer','categoryId':'29',
 'description':description or r.old_description(DESIRED),'tags':['night'],'defaultLanguage':'en','defaultAudioLanguage':'en'},
 'status':{'privacyStatus':'public','license':'youtube'}}
class Session:
 def __init__(self,v):self.v=copy.deepcopy(v);self.writes=[]
 def get(self,*a,**kw):return {'items':[copy.deepcopy(self.v)]}
 def put(self,*a,**kw):
  self.writes.append(kw);self.v['snippet'].update(kw['json']['snippet']);return copy.deepcopy(self.v)
class Tests(unittest.TestCase):
 def test_exact_write_and_idempotence(self):
  s=Session(video());before=copy.deepcopy(s.v);out=r.refresh(s,DESIRED,'Night Prayer',lambda response,label:response)
  self.assertEqual(s.writes[0]['headers'],{'If-Match':'fixture-v1'});self.assertTrue(out['applied']);self.assertEqual(len(s.writes),1);self.assertEqual(s.writes[0]['params'],{'part':'snippet'})
  self.assertEqual(set(s.writes[0]['json']),{'id','snippet'});self.assertEqual(s.v['status'],before['status'])
  self.assertFalse(r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)['applied']);self.assertEqual(len(s.writes),1)
 def test_conflicts_never_write(self):
  for key,value in [('id','other'),('channelId','other'),('title','changed'),('description','human edited')]:
   v=video();(v if key=='id' else v['snippet'])[key]=value;s=Session(v)
   with self.assertRaises(ValueError):r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)
   self.assertEqual(s.writes,[])
 def test_malformed_desired(self):
  for text in ('empty',DESIRED+'0:00 Good evening\n',DESIRED+'0:00 Good morning\n'):
   with self.assertRaises(ValueError):r.old_description(text)
 def test_verification_failure(self):
  s=Session(video())
  def put(*a,**kw):s.writes.append(kw);return s.v
  s.put=put
  with self.assertRaisesRegex(ValueError,'VERIFY_DESCRIPTION'):r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)
  self.assertEqual(len(s.writes),1)
 def test_missing_or_changed_etag_cannot_overwrite(self):
  v=video();v.pop('etag');s=Session(v)
  with self.assertRaisesRegex(ValueError,'MISSING_ETAG'):r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)
  self.assertEqual(s.writes,[])
  s=Session(video())
  def reject(*a,**kw):
   self.assertEqual(kw['headers'],{'If-Match':'fixture-v1'})
   raise RuntimeError('HTTP_412')
  s.put=reject
  with self.assertRaisesRegex(RuntimeError,'HTTP_412'):r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)
  self.assertEqual(s.v['snippet']['description'],r.old_description(DESIRED))
 def test_read_error_has_no_write(self):
  s=Session(video())
  def fail(*a,**kw):raise OSError('offline')
  s.get=fail
  with self.assertRaises(OSError):r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)
  self.assertEqual(s.writes,[])
 def test_status_and_missing_metadata_fail(self):
  s=Session(video());original=s.put
  def put(*a,**kw):
   result=original(*a,**kw);s.v['status']['privacyStatus']='private';return result
  s.put=put
  with self.assertRaisesRegex(ValueError,'VERIFY_STATUS'):r.refresh(s,DESIRED,'Night Prayer',lambda x,y:x)
  v=video();v.pop('status')
  with self.assertRaises(ValueError):r.prepare(v,DESIRED,'Night Prayer')
 def test_real_inputs_and_bounded_workflow(self):
  root=Path(__file__).resolve().parents[2]
  package=r.inputs(root/'migration/production/pilot-012',root/'migration/publish/receipts/pilot-012-39312563293.json')
  self.assertIn('0:00 Good evening',package['description'])
  workflow=(root/'.github/workflows/description-refresh.yml').read_text()
  self.assertNotIn('publish_video.py',workflow)
  self.assertNotIn('publish.yml',workflow)
  self.assertNotIn('inputs:',workflow)
  self.assertIn('group: heroverse-publish',workflow)
  self.assertLess(workflow.index('test_refresh_description.py'),workflow.index('HERO_YT_AUTHORIZED_USER_JSON'))
if __name__=='__main__':unittest.main()
