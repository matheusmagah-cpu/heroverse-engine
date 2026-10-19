#!/usr/bin/env python3
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import owned_feedback as f


def snapshot():
    return {'captured_at': '2026-10-16T12:00:00Z', 'owned_videos': [{'id': 'v',
        'snippet': {'publishedAt': '2026-10-10T00:00:00Z'}, 'statistics': {'viewCount': '0'},
        'status': {'privacyStatus': 'private'}}], 'owned_private': [{'video_id': 'v',
        'date_window': {'start': '2026-10-10', 'end_requested': '2026-10-16'},
        'basic': {'status': 'OBSERVED', 'rows': [{'views': 0, 'averageViewPercentage': 22.5}]},
        'retention': {'status': 'EMPTY_OR_DATA_LAG', 'rows': []}, 'reach': {'ctr': None}}]}


class Tests(unittest.TestCase):
    def build(self, snaps=None, **kw): return f.build_feedback(snaps or [snapshot()], {}, **kw)
    def test_zero_null(self):
        rows=self.build()['videos'][0]['observations'];pub=next(r for r in rows if r['kind']=='PUBLIC_LIFETIME')
        self.assertEqual(pub['metrics']['viewCount']['value'],0);self.assertIsNone(pub['metrics']['likeCount']['value'])
    def test_no_publication_inference(self):
        r=f.build_feedback([snapshot()],{'entries':{'x':{'video_id':'v','uploaded_at':'2026-10-10','slot':'2026-10-11'}}})['videos'][0]
        self.assertIsNone(r['ledger_events'][0]['proven_public_publication_at']);self.assertEqual(r['classification'],'INSUFFICIENT')
    def test_assignment_unknown(self): self.assertEqual(self.build()['videos'][0]['checkpoints'],[])
    def test_assignment_checkpoints_insufficient(self):
        r=self.build(structure_assignments={'v':{'structure_id':'s','structure_version':'v1'}})['videos'][0]
        self.assertEqual([x['key'] for x in r['checkpoints']],[['v','v1','48h'],['v','v1','7d']]);self.assertTrue(all(x['classification']=='INSUFFICIENT' for x in r['checkpoints']))
    def test_temporal_unknown(self):
        r=next(x for x in self.build()['videos'][0]['observations'] if x['kind']=='PRIVATE_REQUESTED_RANGE')
        self.assertFalse(r['coverage']['exact_checkpoint']);self.assertIsNone(r['coverage']['effective_end']);self.assertEqual(r['retention_status'],'UNKNOWN')
    def test_duplicate_identity(self):
        s=snapshot();s['owned_videos']*=2
        with self.assertRaises(ValueError):self.build([s])
    def test_nonfinite(self):
        s=snapshot();s['owned_private'][0]['basic']['rows'][0]['views']=float('nan')
        with self.assertRaises(ValueError):self.build([s])
    def test_duplicate_and_order(self):
        a=snapshot();b=copy.deepcopy(a);b['captured_at']='2026-10-17T12:00:00Z'
        self.assertEqual(self.build([a,b,a]),self.build([b,a]));self.assertEqual(self.build([a,b])['snapshot_count'],2)
    def test_no_mutation(self):
        s=snapshot();before=copy.deepcopy(s);self.build([s]);self.assertEqual(s,before)
    def test_conflict_same_capture(self):
        a=snapshot();b=copy.deepcopy(a);b['owned_videos'][0]['statistics']['viewCount']='1'
        self.assertEqual(len(self.build([a,b])['videos'][0]['conflicts']),1)
    def test_time_change_not_conflict(self):
        a=snapshot();b=copy.deepcopy(a);b['captured_at']='2026-10-17T12:00:00Z';b['owned_videos'][0]['statistics']['viewCount']='1'
        self.assertEqual(self.build([a,b])['videos'][0]['conflicts'],[])
    def test_hash_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';data=b'{ "a": 1 }\n';p.write_bytes(data);_,src=f.read_source(p)
            self.assertEqual(src['sha256'],hashlib.sha256(data).hexdigest());self.assertEqual(src['hash_method'],'EXACT_FILE_BYTES')
    def test_reach(self):
        receipt={'ctr_representation':'provider_raw_representation_unverified','target_observations':[{'video_id':'v','rows':[{'video_id':'v','date_normalized':'2026-10-12','report_id':'r','video_thumbnail_impressions':'175','video_thumbnail_impressions_ctr':'0.0057142857142857143'}],'aggregate_ctr':None}]}
        r=self.build(reach_receipt=receipt)['videos'][0]['reach'][0]
        self.assertEqual(r['rows'][0]['impressions']['value'],175);self.assertIsNone(r['aggregate_ctr']['value']);self.assertEqual(r['rows'][0]['ctr']['unit'],'source_unspecified')
        self.assertEqual(r['ctr_representation'],'provider_raw_representation_unverified')
        self.assertEqual(r['rows'][0]['ctr']['raw_value'],'0.0057142857142857143')
        receipt['target_observations'][0]['rows'][0]['video_id']='wrong'
        with self.assertRaises(ValueError): self.build(reach_receipt=receipt)
    def test_source_fingerprint_not_file_hash(self):
        d=self.build();ref=d['videos'][0]['observations'][0]['evidence'];r=d['source_records'][ref['source_id']];self.assertIsNone(r['sha256']);self.assertIn('content_fingerprint',r)
    def test_other_reach_rows_preserved(self):
        receipt={'other_video_rows':[{'video_id':'other','video_thumbnail_impressions':'1','video_thumbnail_impressions_ctr':'0','report_id':'r'}]}
        r=self.build(reach_receipt=receipt);v=next(v for v in r['videos'] if v['video_id']=='other')
        self.assertEqual(v['reach'][0]['rows'][0]['ctr']['value'],0)
    def test_source_duplicate_order(self):
        a=snapshot();srcs=[{'path':'b','sha256':'same'},{'path':'a','sha256':'same'}]
        self.assertEqual(self.build([a,a],sources={'snapshots':srcs}),self.build([a,a],sources={'snapshots':list(reversed(srcs))}))
    def test_source_identity_conflict(self):
        a=snapshot();b=copy.deepcopy(a);b['captured_at']='other'
        with self.assertRaises(ValueError):self.build([a,b],sources={'snapshots':[{'sha256':'same'},{'sha256':'same'}]})
    def test_source_error_not_promoted(self):
        s=snapshot();s['owned_private'][0]['basic']['status']='ERROR'
        r=next(o for o in self.build([s])['videos'][0]['observations'] if o['kind']=='PRIVATE_REQUESTED_RANGE')
        self.assertEqual(r['basic_status'],'UNKNOWN')
        self.assertEqual(r['basic_rows'][0]['views']['status'],'SOURCE_REPORTED_UNVERIFIED')
        self.assertEqual(r['basic_rows'][0]['subscribersGained']['status'],'UNKNOWN')
    def test_cli_source_overwrite_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source';p.write_text('{}');before=p.read_bytes()
            with self.assertRaises(ValueError):f.main([str(p),str(p),str(p),str(p)])
            self.assertEqual(p.read_bytes(),before)
    def test_no_network_imports(self):
        import ast
        tree=ast.parse(Path(f.__file__).read_text());names=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.update(x.name.split('.')[0] for x in node.names)
            elif isinstance(node,ast.ImportFrom):names.add(node.module.split('.')[0])
        self.assertLessEqual(names,{'copy','hashlib','gzip','json','math','pathlib','sys'})

    def test_gzip_cli_is_deterministic_and_lossless(self):
        import gzip
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a.json';l=root/'l.json';r=root/'r.json';a.write_text(json.dumps(snapshot()));l.write_text('{}');r.write_text('{}')
            out=root/'out.json.gz';again=root/'again.json.gz'
            for p in (out,again):f.main([str(p),str(l),str(r),str(a)])
            self.assertEqual(out.read_bytes(),again.read_bytes());report=json.loads(gzip.decompress(out.read_bytes()))
            ref=report['videos'][0]['observations'][0]['evidence'];source=report['source_records'][ref['source_id']]
            self.assertEqual(source['sha256'],hashlib.sha256(a.read_bytes()).hexdigest())
            node=json.loads(a.read_text())
            for key in ref['json_pointer'].strip('/').split('/'):node=node[int(key)] if isinstance(node,list) else node[key]
            self.assertEqual(node['video_id'],'v')

    def test_actual_sources(self):
        root=Path(__file__).resolve().parents[1];paths=[root/'evidence'/p for p in ('20261013-official-observations.json','observer-38581303747.json','observer-38749052276.json','observer-38911991729.json')]
        pairs=[f.read_source(p) for p in paths];ledger,ls=f.read_source(root/'publish/ledger.json');reach,rs=f.read_source(root/'evidence/owned-reach-two-report-receipt.json')
        r=f.build_feedback([p[0] for p in pairs],ledger,reach_receipt=reach,sources={'snapshots':[p[1] for p in pairs],'ledger':ls,'reach':rs})
        self.assertEqual(r['snapshot_count'],4);self.assertTrue(all(v['classification']=='INSUFFICIENT' for v in r['videos']));self.assertTrue(any(v['reach'] for v in r['videos']))


if __name__=='__main__':unittest.main()
