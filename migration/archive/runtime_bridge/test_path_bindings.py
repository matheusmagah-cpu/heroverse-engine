import tempfile,unittest,hashlib
from pathlib import Path
from path_bindings import resolve_bound_file,LEGACY_ROOT
class BoundMigrationTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)/'project';self.root.mkdir();self.p=self.root/'output'/'video.mp4';self.p.parent.mkdir();self.p.write_bytes(b'exact original');self.hash=hashlib.sha256(self.p.read_bytes()).hexdigest()
 def test_legacy_path_resolves_only_identical_file(self):
  self.assertEqual(resolve_bound_file(self.root,str(LEGACY_ROOT/'output'/'video.mp4'),self.hash),self.p)
 def test_changed_file_rejected(self):
  self.p.write_bytes(b'changed')
  with self.assertRaises(PermissionError):resolve_bound_file(self.root,str(LEGACY_ROOT/'output'/'video.mp4'),self.hash)
 def test_wrong_legacy_root_rejected(self):
  with self.assertRaises(PermissionError):resolve_bound_file(self.root,r'C:\other\output\video.mp4',self.hash)
 def test_parent_traversal_rejected(self):
  with self.assertRaises(PermissionError):resolve_bound_file(self.root,str(LEGACY_ROOT/'..'/'secret'),self.hash)
 def test_symlink_escape_rejected(self):
  outside=Path(self.t.name)/'outside';outside.write_bytes(b'exact original');self.p.unlink();self.p.symlink_to(outside)
  with self.assertRaises(PermissionError):resolve_bound_file(self.root,'output/video.mp4',self.hash)
 def test_missing_input_remains_missing(self):
  with self.assertRaises(FileNotFoundError):resolve_bound_file(self.root,'output/missing.json',self.hash)
if __name__=='__main__':unittest.main()
