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
