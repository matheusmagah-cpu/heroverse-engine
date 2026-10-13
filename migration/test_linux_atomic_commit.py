import multiprocessing
from pathlib import Path
import tempfile
import unittest
from linux_atomic_commit import commit_new

def contender(source, target, results):
    try:
        commit_new(source, target)
        results.put('COMMITTED')
    except FileExistsError:
        results.put('REFUSED')

class CommitTests(unittest.TestCase):
    def test_racing_writers_preserve_one_winner_and_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b, dst = root/'a', root/'b', root/'receipt'
            a.write_bytes(b'first'); b.write_bytes(b'second')
            results = multiprocessing.Queue()
            children = [multiprocessing.Process(target=contender,args=(src,dst,results)) for src in (a,b)]
            for p in children: p.start()
            for p in children:
                p.join(5)
                self.assertFalse(p.is_alive())
                self.assertEqual(p.exitcode,0)
            self.assertEqual(sorted(results.get(timeout=2) for _ in children), ['COMMITTED','REFUSED'])
            self.assertIn(dst.read_bytes(), (b'first', b'second'))
            self.assertEqual(a.read_bytes(), b'first'); self.assertEqual(b.read_bytes(), b'second')

    def test_existing_receipt_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; dst=root/'receipt'
            source.write_bytes(b'new'); dst.write_bytes(b'frozen')
            with self.assertRaises(FileExistsError): commit_new(source,dst)
            self.assertEqual(dst.read_bytes(),b'frozen')

    def test_symlink_destination_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; dst=root/'receipt'
            source.write_bytes(b'new'); dst.symlink_to(source)
            with self.assertRaises(ValueError): commit_new(source,dst)

if __name__ == '__main__': unittest.main()
