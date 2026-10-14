BEGIN TRANSACTION;
CREATE TABLE composed_quota_reservations (
    reservation_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    effect_id TEXT NOT NULL,
    attempt_count INTEGER NOT NULL CHECK(attempt_count >= 1),
    channel_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    general_units INTEGER NOT NULL CHECK(general_units > 0),
    general_preventive_floor INTEGER NOT NULL CHECK(general_preventive_floor >= 0),
    upload_preventive_floor INTEGER NOT NULL CHECK(upload_preventive_floor >= 0),
    general_debit_id TEXT NOT NULL UNIQUE,
    upload_debit_id TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN ('RESERVED','CONSUMED')),
    quota_day_start TEXT NOT NULL,
    quota_day_end TEXT NOT NULL,
    observation_archive_path TEXT NOT NULL,
    observation_sha256 TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    observation_observed_at TEXT NOT NULL,
    reserved_at TEXT NOT NULL,
    effect_started_at TEXT,
    consumed_at TEXT,
    confirmation_id TEXT,
    confirmation_sha256 TEXT
);
CREATE TABLE general_quota_debits (
    debit_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    operation_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    attempt_count INTEGER NOT NULL CHECK(attempt_count >= 1),
    channel_id TEXT NOT NULL,
    units INTEGER NOT NULL CHECK(units > 0),
    state TEXT NOT NULL CHECK(state IN ('RESERVED','CONSUMED')),
    quota_day_start TEXT NOT NULL,
    quota_day_end TEXT NOT NULL,
    effective_before INTEGER NOT NULL CHECK(effective_before >= 0),
    effective_after INTEGER NOT NULL CHECK(effective_after >= 0),
    reserved_at TEXT NOT NULL,
    consumed_at TEXT
, requested_effective_before INTEGER NOT NULL DEFAULT 0, preventive_floor INTEGER NOT NULL DEFAULT 12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-bd9ddb2a93cf64edca49a48c','phase6-owned-metrics:job-767c0bc06ca29c2bab013494:attempt-1','phase6_owned_metrics_checkpoint','job-767c0bc06ca29c2bab013494',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2000,2002,'2026-09-05T18:48:40.697492Z','2026-09-05T18:48:44.697492Z',2000,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-dd4034ca22f34897ed089dec','phase6-owned-metrics:job-b667849e9aa9ec8ec2b2d143:attempt-1','phase6_owned_metrics_checkpoint','job-b667849e9aa9ec8ec2b2d143',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2002,2004,'2026-09-05T21:14:55.690378Z','2026-09-05T21:15:00.690378Z',2002,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-67aa3a4c877d424339396645','phase6-owned-metrics:job-38b6e4d84f418ea590e61467:attempt-1','phase6_owned_metrics_checkpoint','job-38b6e4d84f418ea590e61467',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2004,2006,'2026-09-05T23:15:54.284910Z','2026-09-05T23:15:57.284910Z',2004,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-b7c072a518f7ffd6efbab610','phase6-owned-metrics:job-76fb188fdee7590077d5bccc:attempt-1','phase6_owned_metrics_checkpoint','job-76fb188fdee7590077d5bccc',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2006,2008,'2026-09-06T02:42:19.256457Z','2026-09-06T02:42:21.256457Z',2006,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-2cee8b8edbb596a851a709a3','phase6-owned-metrics:job-c8be4efa07c8fec14595020d:attempt-1','phase6_owned_metrics_checkpoint','job-c8be4efa07c8fec14595020d',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2008,2010,'2026-09-06T04:43:21.215252Z','2026-09-06T04:43:31.215252Z',2008,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-41bc46a00de237f4c3592b9b','phase6-owned-metrics:job-26a303252643c3f9b4d68533:attempt-1','phase6_owned_metrics_checkpoint','job-26a303252643c3f9b4d68533',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2010,2012,'2026-09-06T06:43:52.420857Z','2026-09-06T06:43:54.420857Z',2010,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-46ffb3a3d50b465bac121023','phase6-owned-metrics:job-17a74560777d18302336bd13:attempt-1','phase6_owned_metrics_checkpoint','job-17a74560777d18302336bd13',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-05T07:00:00Z','2026-09-06T07:00:00Z',2012,2014,'2026-09-06T06:47:34.536145Z','2026-09-06T06:47:36.536145Z',2012,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-505836317f0364562f8015a5','phase6-owned-metrics:job-3e31f902930a97067968c9d2:attempt-1','phase6_owned_metrics_checkpoint','job-3e31f902930a97067968c9d2',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-07T07:00:00Z','2026-09-08T07:00:00Z',2000,2002,'2026-09-07T18:48:18.372812Z','2026-09-07T18:48:20.372812Z',2000,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-b0f09dec620d06bef85576b9','phase6-owned-metrics:job-3daf096d38c3ba453900396e:attempt-1','phase6_owned_metrics_checkpoint','job-3daf096d38c3ba453900396e',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-07T07:00:00Z','2026-09-08T07:00:00Z',2002,2004,'2026-09-07T20:58:19.722424Z','2026-09-07T20:58:21.722424Z',2002,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-a3127f52f5cc0fd4d2b054cc','oauth-incident-20260908T114058Z-recovery-v2','oauth_incident_channel_identity_recovery','oauth-incident-20260908T114058Z-recovery-v2',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-09-08T07:00:00Z','2026-09-09T07:00:00Z',2000,2001,'2026-09-08T12:38:39.157359Z','2026-09-08T12:38:41.033197Z',2000,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-130d2c0092a648703120277e','phase6-owned-metrics:job-b76994afa3ef3651a0de9123:attempt-1','phase6_owned_metrics_checkpoint','job-b76994afa3ef3651a0de9123',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-15T07:00:00Z','2026-09-16T07:00:00Z',2000,2002,'2026-09-15T19:48:17.945483Z','2026-09-15T19:48:19.945483Z',2000,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-549b13ce1e7dce70c1533b79','phase6-owned-metrics:job-f804bd7e55f42bf6268f1453:attempt-1','phase6_owned_metrics_checkpoint','job-f804bd7e55f42bf6268f1453',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'CONSUMED','2026-09-18T07:00:00Z','2026-09-19T07:00:00Z',2000,2002,'2026-09-18T21:50:29.000462Z','2026-09-18T21:50:31.000462Z',2000,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-7a82774183919ef0565c7e22','audio-owned-metrics:job-96b2fc989c8df99a2b5a9d02','phase6_owned_metrics_checkpoint','job-96b2fc989c8df99a2b5a9d02',1,'UCuMF6pJQkyMzaVoAxFL86yA',2,'RESERVED','2026-10-12T07:00:00Z','2026-10-13T07:00:00Z',2000,2002,'2026-10-12T18:58:36.848133Z',NULL,2000,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-79deef3c9dafb13b6863e0a4','cloud-evidence-38476824992:owned-channel','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2001,2002,'2026-10-13T22:18:13.515466Z','2026-10-13T22:18:13.520433Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-e8d9d9ec50585a3c59e9fb69','cloud-evidence-38476824992:reference-channels','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2002,2003,'2026-10-13T22:18:13.668587Z','2026-10-13T22:18:13.670989Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-8d636ac4099781cd281dc090','cloud-evidence-38476824992:uploads-UCuMF6pJQkyMzaVoAxFL86yA','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2003,2004,'2026-10-13T22:18:13.792379Z','2026-10-13T22:18:13.794666Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-8a54570467d57559ba8494b4','cloud-evidence-38476824992:uploads-UCTdc_zl40D9wa0_LH9yaGZA','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2004,2005,'2026-10-13T22:18:14.151562Z','2026-10-13T22:18:14.153783Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-3872c7ced5d1e75a641331d4','cloud-evidence-38476824992:uploads-UC0JWi59lgJMCapfqr6_P15g','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2005,2006,'2026-10-13T22:18:14.503838Z','2026-10-13T22:18:14.506279Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-91c453ac8daabba1e7eb986e','cloud-evidence-38476824992:uploads-UC2d7chxFUVEurYmI4yfmTlQ','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2006,2007,'2026-10-13T22:18:14.736028Z','2026-10-13T22:18:14.738287Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-29ccf539c9f02d78bf263191','cloud-evidence-38476824992:uploads-UC5spXp9tnfnAuRQKgZgw2tg','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2007,2008,'2026-10-13T22:18:14.920968Z','2026-10-13T22:18:14.923368Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-e36129c08c1f1d3054189446','cloud-evidence-38476824992:uploads-UC_h1E8wccvaX1gTtx4VsYXw','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2008,2009,'2026-10-13T22:18:15.130101Z','2026-10-13T22:18:15.132393Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-8709a7b6ec32170e721d7e07','cloud-evidence-38476824992:uploads-UCsDKqJJISkMyvjFowNT_Sdg','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2009,2010,'2026-10-13T22:18:15.271980Z','2026-10-13T22:18:15.274320Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-508c46e76e9b5005ecea0545','cloud-evidence-38476824992:videos-0','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2010,2011,'2026-10-13T22:18:15.900156Z','2026-10-13T22:18:15.903431Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-cf197a62e0e874ee64fc3563','cloud-evidence-38476824992:videos-1','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2011,2012,'2026-10-13T22:18:16.231637Z','2026-10-13T22:18:16.233909Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-ab0297557bd9c24665ed9da0','cloud-evidence-38476824992:videos-2','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2012,2013,'2026-10-13T22:18:16.412979Z','2026-10-13T22:18:16.415369Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-a1053cb4c76640a6bffcc4ea','cloud-evidence-38476824992:videos-3','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2013,2014,'2026-10-13T22:18:16.646572Z','2026-10-13T22:18:16.648784Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-8e50431489826fa611a05359','cloud-evidence-38476824992:videos-4','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2014,2015,'2026-10-13T22:18:16.905690Z','2026-10-13T22:18:16.908197Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-a7ccb72476e10401bee3f4cc','cloud-evidence-38476824992:videos-5','cloud-evidence-38476824992','cloud-evidence-38476824992',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2015,2016,'2026-10-13T22:18:17.178741Z','2026-10-13T22:18:17.181416Z',2001,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-34febc788cdef06da4dc84bf','native-cloud-readiness:38485393901','native-cloud-readiness:38485393901','native-cloud-readiness:38485393901',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2016,2017,'2026-10-13T23:37:58.885424Z','2026-10-13T23:37:58.888775Z',2016,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-f4e98b4034eccb729f65dc96','native-cloud-readiness:38487465939','native-cloud-readiness:38487465939','native-cloud-readiness:38487465939',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2017,2018,'2026-10-13T23:59:05.117872Z','2026-10-13T23:59:05.121099Z',2016,12);
INSERT INTO "general_quota_debits" VALUES('quota-debit-63069a7868d359cb36c8d1ea','cloud-evidence-38495958336:owned-channel','cloud-evidence-38495958336','cloud-evidence-38495958336',1,'UCuMF6pJQkyMzaVoAxFL86yA',1,'CONSUMED','2026-10-13T07:00:00Z','2026-10-14T07:00:00Z',2018,2019,'2026-10-14T01:29:15.265317Z','2026-10-14T01:29:15.268868Z',2001,12);
CREATE TABLE public_av_reservations(
                key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                day TEXT NOT NULL, seconds INTEGER NOT NULL,
                state TEXT NOT NULL, receipt_path TEXT, receipt_hash TEXT);
INSERT INTO "public_av_reservations" VALUES('public-av:e97971dbdd5a525bd43c96be2b0dc0ac522a1262a79a5f0547f545fdc9111700','48b027a3c3aadca70ef81066e83c6ab206c1c23aed6b8cc75f795f96657808b8','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-e97971dbdd5a525bd43c96be2b0dc0ac522a1262a79a5f0547f545fdc9111700.json','971e2d80bf5621963fb907c9bbb1e86bb58f89f3c33eae299b1596b3040d8844');
INSERT INTO "public_av_reservations" VALUES('public-av:1616712c2661dffdb80c0bba2fcd4b5140fb32150bacd41082c92c159e63ef42','00ad74fd71586e397d04dfaddcf71b764eeec084570866aa0357005ae7da8afd','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-1616712c2661dffdb80c0bba2fcd4b5140fb32150bacd41082c92c159e63ef42.json','ea9814a9fe73f4537f7fc26f0c68fc8c6d3499a03b43f74ac2bba38e4917fe3d');
INSERT INTO "public_av_reservations" VALUES('public-av:7fa5e24f8726da79a91bdd3e91b0979dd38fa265f8abecfb7a8ce856178972a2','f2295c9c0b1fc687eac9eaef8d2fcf0368c2caf2235548cce4db6184ac6a6bb8','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-7fa5e24f8726da79a91bdd3e91b0979dd38fa265f8abecfb7a8ce856178972a2.json','414572975fff5b1ca1a24b7685c957e90dc69486ebca27d73a272087a346d0dc');
INSERT INTO "public_av_reservations" VALUES('public-av:a914e3fd845290c8f1fd5efba0733731bfcd241e547f0d6ee0078f8c44d037a7','95f8b6e373dfb55e88f0d7412100965b8d33736fa35e321180011c8c632d0fd3','2026-10-14',0,'COMPLETED','migration/evidence/public-av-a914e3fd845290c8f1fd5efba0733731bfcd241e547f0d6ee0078f8c44d037a7.json','52b7dbf7d84046f5d9b3297ba6ad752d2e9c349265864b9ab4a15139d51c7409');
INSERT INTO "public_av_reservations" VALUES('public-av:75a9681804e82d50e16951718f912d953f46cad4828b037c79ce2242d0c0830d','ac6c106d65951de0fcdaaa8e585d27963483dfcb5447d28609623ed35a795810','2026-10-14',10,'COMPLETED','migration/evidence/public-av-75a9681804e82d50e16951718f912d953f46cad4828b037c79ce2242d0c0830d.json','7fd1266a0170b3ac5a3c7864f649d4b75f69eb51f8bc461377ae17c663c35506');
INSERT INTO "public_av_reservations" VALUES('public-av:4faf27d15efc8fcc0fe6c153ebb515b672b4e8c920e0500ab075abb05b2d8f7f','1578de4ad869129d6a38db3a33a0e6b08a1486fe977db847deb9dfe16d03d75a','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-4faf27d15efc8fcc0fe6c153ebb515b672b4e8c920e0500ab075abb05b2d8f7f.json','e2a31922fabc85368fd59091b3a70bb515ffa7a7b019c80cbe66596618224425');
INSERT INTO "public_av_reservations" VALUES('public-av:7b38b466cad2150e278ca73fc27ae3732affa93174003a23626edbe3a4f4799e','6a21fb4ff3566b7b02a9d86b2b5bb64caa27905e78159cff11bdc494ceed4332','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-7b38b466cad2150e278ca73fc27ae3732affa93174003a23626edbe3a4f4799e.json','7d75df1dead919a2c3c74f3d7da1a7f7e90d986943ff1807755e8a3e90d529fe');
INSERT INTO "public_av_reservations" VALUES('public-av:ca469f52518ba6218745fd05863e52bd60c9d6fc7c5b19d2b3f6c4b4081270e9','391e97aa644450bbc1d10d35a195c2c5dd999d775018b6d224e1a25e65ec9c14','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-ca469f52518ba6218745fd05863e52bd60c9d6fc7c5b19d2b3f6c4b4081270e9.json','072179f43f18e0710925d3e61cbdd419e10062bcdbf54184bfa893b19120737b');
INSERT INTO "public_av_reservations" VALUES('public-av:3821dcc0acfdff6f0f87cb855c4732bc52e3a62cac44536ae0f6b55d81305989','4c527da9a05457a2de8fb559eae79ae222b29151bf5d0f6865bd921d8a56cb36','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-3821dcc0acfdff6f0f87cb855c4732bc52e3a62cac44536ae0f6b55d81305989.json','15e5a062b1739d69080186ae7102bb2e38d38bd0c09cb4bdce4b6c5a5b0eebc8');
INSERT INTO "public_av_reservations" VALUES('public-av:f8cf678e70f7b859e15f1d40fc2d305cd8b8c4a7a677ccc96898c98e6a02dcb0','f759d8c67c1bc4942bc22f2cf6899447b5f067eee3a30e856a6ae4dbdd640b6b','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-f8cf678e70f7b859e15f1d40fc2d305cd8b8c4a7a677ccc96898c98e6a02dcb0.json','aa4559889cda1ddf5cba2ef93148bd6da505c41f5ba8b25ac462bf413d6d396b');
INSERT INTO "public_av_reservations" VALUES('public-av:ead98bbe7d0211cf896c6f2ffc48837dc02c49552b3aa23f76bdb8469e4f6aa3','97778f5fe355a56b6a9e8f91c34d6867461df5e528b3dd0bf13f741374b358d2','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-ead98bbe7d0211cf896c6f2ffc48837dc02c49552b3aa23f76bdb8469e4f6aa3.json','dd90b113d500b65acadbfdc72927214b63f4131a096e9ceed09b9c77029cf95d');
INSERT INTO "public_av_reservations" VALUES('public-av:874026d4bbdd9eb55e265f2f3a4962f4dddfdca76fbbe52b4ca5b17bd4ce1682','0dbdd16350a93c121bc6be12a4549436d5c06b06dde169fb558e8b987534b1e5','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-874026d4bbdd9eb55e265f2f3a4962f4dddfdca76fbbe52b4ca5b17bd4ce1682.json','45cfe012cb64c1c54d7e430ec991c453c359620cf0e41db1bb78a492d11f3856');
INSERT INTO "public_av_reservations" VALUES('public-av:6a60172d19005ccc0662f2dbde66bb991481f249a9750458f5a718279bf3d9c0','c41c6809a9e5347e0fd5ee0fa649c6996266949d94d289834433d8bab7f79971','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-6a60172d19005ccc0662f2dbde66bb991481f249a9750458f5a718279bf3d9c0.json','96ff61bf27edc86b8e6325aab4c77da77456bca6222abdd54b096c85306b6b87');
INSERT INTO "public_av_reservations" VALUES('public-av:e21f872b09917369ea9d8b4965e57f2e7195a85549fea6af91c7fccbc39962fa','8755896fbf0eee78390af6414b07a467738c3cfb1f5069dcf8877b277e2ac745','2026-10-14',1178,'COMPLETED','migration/evidence/public-av-e21f872b09917369ea9d8b4965e57f2e7195a85549fea6af91c7fccbc39962fa.json','5e8b5762f1f0a4ec97314bb23869d3e0987d9b5b7457201754726b9514ad45f0');
CREATE TABLE upload_quota_debits (
    debit_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    effect_id TEXT NOT NULL,
    attempt_count INTEGER NOT NULL CHECK(attempt_count >= 1),
    channel_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    units INTEGER NOT NULL CHECK(units = 1),
    state TEXT NOT NULL CHECK(state IN ('RESERVED','CONSUMED')),
    quota_day_start TEXT NOT NULL,
    quota_day_end TEXT NOT NULL,
    effective_before INTEGER NOT NULL CHECK(effective_before >= 0),
    effective_after INTEGER NOT NULL CHECK(effective_after >= 0),
    observation_sha256 TEXT NOT NULL,
    observation_observed_at TEXT NOT NULL,
    reserved_at TEXT NOT NULL,
    consumed_at TEXT,
    confirmation_id TEXT,
    confirmation_sha256 TEXT
);
CREATE INDEX idx_general_quota_day
ON general_quota_debits(quota_day_start, quota_day_end, reserved_at);
CREATE INDEX idx_upload_quota_day
ON upload_quota_debits(quota_day_start, quota_day_end, reserved_at);
CREATE INDEX idx_composed_quota_day
ON composed_quota_reservations(quota_day_start, quota_day_end, reserved_at);
COMMIT;
