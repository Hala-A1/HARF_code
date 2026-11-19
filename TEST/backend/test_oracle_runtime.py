"""Runtime repository contracts using a transaction-capable SQL test double.

Oracle server validation remains a separate local deployment check. The double
adapts Oracle syntax only; application SQL, permissions and workflow run unchanged.
"""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

import access_control
import admin
import feedback
from main import app
import oracle_runtime as runtime
import oracle_migration as migration
from oracle_mapping import build_rows,canonical
from oracle_recovery import export_snapshot,materialize,recovery_fingerprint,restore_local
from request_limits import RequestLimits
from test_oracle_migration import fixture,NOW
from oracle_connection import configure_fetch,json_text_handler

JSON_FIELDS={'config_json','profile_json','review_languages','metadata_json','payload_json','quality_report',
             'snapshot_json','instruction_manifest','access_json','snapshot'}


class Lob:
    def __init__(self,value): self.value=value
    def read(self): return self.value


class Cursor:
    def __init__(self,db): self.db=db; self.cursor=db.sqlite.cursor()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def close(self): self.cursor.close()
    @property
    def description(self): return self.cursor.description
    @property
    def rowcount(self): return self.cursor.rowcount
    def setinputsizes(self,**kwargs): pass
    def execute(self,sql,parameters=None,**kwargs):
        if sql.startswith(('LOCK TABLE ','SET TRANSACTION ')): return self
        if 'FROM nls_database_parameters' in sql:
            self.cursor.execute("SELECT 'AL32UTF8'"); return self
        if 'FROM user_objects' in sql:
            self.cursor.execute('SELECT 0'); return self
        sql=re.sub(r"TO_TIMESTAMP_TZ\((:\w+), '[^']*'\)",r'\1',sql)
        sql=re.sub(r"TO_CHAR\((\w+),\s*'[^']*'\)",r'\1',sql)
        sql=re.sub(r' FOR UPDATE(?: WAIT \d+)?','',sql)
        sql=re.sub(r'OFFSET (:\w+|\d+) ROWS FETCH NEXT (:\w+|\d+) ROWS ONLY',r'LIMIT \2 OFFSET \1',sql)
        sql=re.sub(r'FETCH FIRST (\d+) ROW ONLY',r'LIMIT \1',sql)
        sql=sql.replace('SYSTIMESTAMP',"'2026-10-18T12:00:00.000000+00:00'")
        sql=sql.replace('JSON_VALUE(','json_extract(')
        if sql.startswith('MERGE INTO '):
            table=re.search(r'MERGE INTO (\w+)',sql)[1]
            pairs=re.findall(r'(:p\d+) AS (\w+)',sql)
            keys=re.findall(r't\.(\w+)=s\.\1',sql.split('WHEN')[0])
            names=[c for _,c in pairs]
            sql='INSERT INTO '+table+' ('+','.join(names)+') VALUES ('+','.join(p for p,_ in pairs)+') ON CONFLICT('+','.join(keys)+') '
            # The source SELECT and ON keys fully specify Oracle MERGE semantics.
            original=self.db.last_sql
            if 'WHEN MATCHED' in original:
                sql+='DO UPDATE SET '+','.join(c+'=excluded.'+c for c in names if c not in keys)
            else: sql+='DO NOTHING'
        if isinstance(parameters, (tuple, list)) and re.search(r':\d+\b',sql):
            parameters = {str(index+1):value for index,value in enumerate(parameters)}
        self.cursor.execute(sql,parameters if parameters is not None else kwargs)
        return self
    @property
    def arraysize(self): return 100
    def var(self,type_code,**kwargs): return {'type_code':type_code,**kwargs}
    def convert(self,values):
        if values is None: return None
        import oracledb
        converted=[]
        for column,value in zip(self.description,values):
            if column[0].lower() in JSON_FIELDS and value is not None:
                handler=self.db.outputtypehandler
                metadata=SimpleNamespace(is_json=True,type_code=oracledb.DB_TYPE_CLOB)
                # Real python-oracledb returns objects for IS JSON CLOBs unless
                # the documented output type handler requests legacy LOB fetching.
                value=Lob(value) if handler and handler(self,metadata) is not None else json.loads(value)
            converted.append(value)
        return tuple(converted)
    def fetchone(self): return self.convert(self.cursor.fetchone())
    def fetchall(self): return [self.convert(row) for row in self.cursor.fetchall()]
    def __iter__(self): return (self.convert(row) for row in self.cursor)


class Database:
    def __init__(self):
        self.sqlite=sqlite3.connect(':memory:',check_same_thread=False)
        self.outputtypehandler=None
        self.fail_commit=False
        self.commits=0; self.rollbacks=0
        schema=(Path(__file__).resolve().parents[2]/'database/oracle/01_create_tables.sql').read_text(encoding='utf-8')
        for table,body in re.findall(r'CREATE TABLE (genai_harf_\w+)\s*\((.*?)\n\);',schema,re.S|re.I):
            definitions=[]
            for line in body.splitlines():
                m=re.match(r'\s*(\w+)\s+(VARCHAR2\([^)]*\)|CLOB|NUMBER(?:\([^)]*\))?|TIMESTAMP\(6\) WITH TIME ZONE)(.*)',line,re.I)
                if not m: continue
                definition='"'+m[1]+'"'
                if 'PRIMARY KEY' in m[3]: definition+=' PRIMARY KEY'
                default=re.search(r"DEFAULT ('[^']*'|\d+)",m[3])
                if default: definition+=' DEFAULT '+default[1]
                definitions.append(definition)
            key=re.search(r'CONSTRAINT \w+ PRIMARY KEY \(([^)]+)\)',body)
            if key: definitions.append('PRIMARY KEY ('+key[1]+')')
            self.sqlite.execute('CREATE TABLE '+table+' ('+','.join(definitions)+')')
        self.sqlite.execute('CREATE TABLE genai_harf_migration_snapshots(migration_id PRIMARY KEY,snapshot_sha256,snapshot_json,imported_at,rolled_back_at,migration_status)')
        self.sqlite.execute('CREATE TABLE genai_harf_runtime_state(state_id PRIMARY KEY,revision,migration_id,baseline_at,access_json,updated_at)')
        for version in ('001','002','003'):
            self.sqlite.execute('INSERT INTO genai_harf_schema_versions(version_id,description) VALUES(?,?)',(version,'test'))
        self.sqlite.execute('''CREATE VIEW rw_feedback_legacy AS SELECT feedback_id AS id,channel_id,workspace_name AS workspace,
            user_email,user_name,fingerprint,rating,reason_text AS reason,snapshot_json AS snapshot,instruction_manifest,
            created_at,updated_at,review_status AS status,admin_note,reviewed_by,reviewed_at FROM genai_harf_feedback''')
        self.sqlite.execute('CREATE VIEW rw_channel_limits_legacy AS SELECT channel_id AS channel,monthly_limit FROM genai_harf_channel_limits')
        self.sqlite.execute('CREATE VIEW rw_user_limits_legacy AS SELECT channel_id AS channel,principal_id AS principal,monthly_limit FROM genai_harf_user_limits')
        self.sqlite.execute('''CREATE VIEW rw_request_usage_legacy AS SELECT request_id AS id,channel_id AS channel,principal_id AS principal,
            month_key AS month,request_state AS state,(julianday(expires_at)-julianday('1970-01-01'))*86400 AS expires,created_at FROM genai_harf_request_usage''')
        self.sqlite.commit()
    def cursor(self):
        cursor=Cursor(self)
        original=cursor.execute
        def execute(sql,*args,**kwargs): self.last_sql=sql; return original(sql,*args,**kwargs)
        cursor.execute=execute
        return cursor
    def commit(self):
        if self.fail_commit:
            self.fail_commit=False
            raise RuntimeError('simulated commit failure')
        self.sqlite.commit(); self.commits+=1
    def rollback(self): self.sqlite.rollback(); self.rollbacks+=1


class Pool:
    def __init__(self,db): self.db=db
    def acquire(self): return self.db
    def release(self,db): pass


class OracleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.snapshot=fixture(self.root)
        self.snapshot['access']['channels'].append({'id':'b2b','name':'B2B'})
        self.snapshot['access']['users'] += [
            dict(email='admin@example.test',name='Admin',role='channel_admin',channel_id='b2c'),
            dict(email='other@example.test',name='Other admin',role='channel_admin',channel_id='b2b'),
            dict(email='super@example.test',name='Super',role='super_admin',channel_id=None),
            dict(email='reviewer@example.test',name='Reviewer',role='approval_admin',approval_layer=1,review_languages=['en'],channel_id='b2c'),
        ]
        (self.root/'backend/access-control.json').write_text(canonical(self.snapshot['access']),encoding='utf-8')
        self.db=configure_fetch(Database()); self.addCleanup(self.db.sqlite.close)
        runtime._access_cache.update(revision=None,data=None)
        self.addCleanup(lambda: runtime._access_cache.update(revision=None,data=None))
        with patch.object(migration,'require_stopped'):
            migration.migrate(self.db,self.snapshot,self.root)
        # A fresh pooled session must configure its own fetch behaviour too.
        self.db.outputtypehandler=None
        self.patchers=[patch.object(runtime,'pool',return_value=Pool(self.db)),
            patch.dict('os.environ',{'REWRITE_STORAGE_BACKEND':'oracle'}),
            patch.object(access_control,'DATA_FILE',self.root/'backend/access-control.json'),
            patch.object(access_control,'CHANNEL_PROMPT_DIR',self.root/'instructions/channels'),
            patch.object(admin,'CHANNEL_PROMPT_DIR',self.root/'instructions/channels'),
            patch.object(feedback,'manifest',return_value={'files':[]})]
        for p in self.patchers: p.start(); self.addCleanup(p.stop)
        self.client=TestClient(app)
    def headers(self,who='test'): return {'X-User-Email':who+'@example.test'}

    def test_user_edit_saved_to_oracle_not_local_file(self):
        original=access_control.DATA_FILE.read_bytes()
        data=access_control.load_access_data(); data['users'][0]['name']='Updated name'
        access_control.save_access_data(data)
        self.assertEqual(access_control.load_access_data()['users'][0]['name'],'Updated name')
        self.assertEqual(self.db.sqlite.execute("SELECT display_name FROM genai_harf_users WHERE email='test@example.test'").fetchone()[0],'Updated name')
        self.assertEqual(original,access_control.DATA_FILE.read_bytes())

    def test_deployment_registers_cx_pack_and_keeps_oracle_edits_on_repeat(self):
        from directory_provisioning import apply_deployment_updates
        source = access_control.CHANNEL_PROMPT_DIR / 'cx-comms'
        source.mkdir(parents=True)
        for module in ('CX_COMMS_SYSTEM','CX_COMMS_TEMPLATES','CX_COMMS_USER_GUIDE'):
            (source / access_control.INSTRUCTION_MODULES[module]['filename']).write_text('CX instructions '+module,encoding='utf-8')
        with patch('directory_auth.enabled', return_value=False): apply_deployment_updates()
        self.assertEqual(self.db.sqlite.execute("SELECT COUNT(*) FROM genai_harf_channels WHERE channel_id='cx-comms'").fetchone()[0],1)
        self.assertEqual(self.db.sqlite.execute("SELECT COUNT(*) FROM genai_harf_instructions WHERE channel_id='cx-comms'").fetchone()[0],3)
        self.db.sqlite.execute("UPDATE genai_harf_instructions SET content_md='Edited in Oracle' WHERE channel_id='cx-comms' AND module_id='CX_COMMS_SYSTEM'")
        self.db.sqlite.commit()
        with patch('directory_auth.enabled', return_value=False): apply_deployment_updates()
        self.assertEqual(self.db.sqlite.execute("SELECT content_md FROM genai_harf_instructions WHERE channel_id='cx-comms' AND module_id='CX_COMMS_SYSTEM'").fetchone()[0],'Edited in Oracle')
        self.assertEqual(self.db.sqlite.execute("SELECT COUNT(*) FROM genai_harf_instruction_versions WHERE channel_id='cx-comms'").fetchone()[0],3)

    def test_ldap_admin_deployment_rolls_back_all_accounts_and_cx_on_failure(self):
        from directory_provisioning import apply_deployment_updates
        original = deepcopy(access_control.load_access_data())
        source = access_control.CHANNEL_PROMPT_DIR / 'cx-comms'
        source.mkdir(parents=True)
        for module in ('CX_COMMS_SYSTEM','CX_COMMS_TEMPLATES','CX_COMMS_USER_GUIDE'):
            (source / access_control.INSTRUCTION_MODULES[module]['filename']).write_text('CX deployment rules',encoding='utf-8')
        def person(username): return dict(username=username,email=username+'@example.test',name=username,directory_id='ldap:'+username)
        self.db.fail_commit = True
        with patch('directory_auth.enabled',return_value=True), patch('directory_auth.find_user',side_effect=person), \
                patch.dict('os.environ',{'LDAP_SUPER_ADMIN_USERNAMES':'bmahrouseh,selkhiat,mohmay,haamir'}):
            with self.assertRaises(Exception): apply_deployment_updates()
        self.assertEqual(access_control.load_access_data(), original)
        self.assertEqual(self.db.sqlite.execute("SELECT COUNT(*) FROM genai_harf_channels WHERE channel_id='cx-comms'").fetchone()[0],0)

    def test_concurrent_stale_save_does_not_overwrite(self):
        first=access_control.load_access_data(); second=access_control.load_access_data()
        first['users'][0]['name']='First update'; access_control.save_access_data(first)
        second['users'][0]['name']='Stale update'
        with self.assertRaises(HTTPException) as error: access_control.save_access_data(second)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(access_control.load_access_data()['users'][0]['name'],'First update')

    def test_activity_ids_do_not_shift_when_new_event_inserted(self):
        data=access_control.load_access_data()
        event=dict(actor='Test',actor_email='test@example.test',action='Test action',timestamp=NOW,channel_id='b2c')
        data['activity']=[event]; access_control.save_access_data(data)
        identity=self.db.sqlite.execute('SELECT activity_id FROM genai_harf_activity').fetchone()[0]
        data=access_control.load_access_data(); data['activity'].insert(0,{**event,'action':'New action'})
        access_control.save_access_data(data)
        self.assertEqual(self.db.sqlite.execute("SELECT activity_id FROM genai_harf_activity WHERE event_action='Test action'").fetchone()[0],identity)

    def test_shared_unit_of_work_rolls_back_access_and_quota_together(self):
        user=access_control.load_access_data()['users'][0]
        with self.assertRaises(RuntimeError):
            with access_control.DATA_LOCK:
                data=access_control.load_access_data(); data['users'][0]['name']='Will roll back'
                access_control.save_access_data(data)
                RequestLimits().set_user('b2c',user,5)
                raise RuntimeError('abort')
        self.assertEqual(access_control.load_access_data()['users'][0]['name'],'Test')
        self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_user_limits').fetchone()[0],0)

    def test_quota_allocation_reservation_completion_and_release(self):
        user=access_control.load_access_data()['users'][0]
        store=RequestLimits(); store.set_user('b2c',user,1)
        request=store.reserve('b2c',user)
        with self.assertRaises(HTTPException) as error: store.reserve('b2c',user)
        self.assertEqual(error.exception.status_code,429)
        store.finish(request,False)
        request=store.reserve('b2c',user); store.finish(request,True)
        summary=store.summary('b2c',[user],user)
        self.assertEqual(summary['mine']['used'],1)
        self.assertEqual(summary['mine']['remaining'],0)

    def test_ldap_link_preserves_usage_and_allocation(self):
        user=access_control.load_access_data()['users'][0]
        store=RequestLimits(); store.set_user('b2c',user,3)
        request=store.reserve('b2c',user); store.finish(request,True)
        store.link_identity(user['email'],'directory-id-1')
        summary=store.summary('b2c',[{**user,'directory_id':'directory-id-1'}],user)
        self.assertEqual(summary['users'][0]['used'],1)
        self.assertEqual(summary['users'][0]['limit'],3)
        store.release_allocation('b2c',{**user,'directory_id':'directory-id-1'})
        self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_user_limits').fetchone()[0],0)

    def test_feedback_snapshot_scope_listing_and_review(self):
        snapshot=dict(channel_id='b2c',source_text='Original source',output_text='نص عربي',language='ar',instructions='Keep facts')
        response=self.client.post('/api/feedback',headers=self.headers(),json={'snapshot':snapshot,'rating':'down','reason':'Needs clarity'})
        self.assertEqual(response.status_code,200,response.text)
        identity=response.json()['id']
        self.assertEqual(self.client.get('/api/feedback/'+identity,headers=self.headers('other')).status_code,404)
        listing=self.client.get('/api/feedback',params={'channel_id':'b2c','search':'clarity'},headers=self.headers('admin'))
        self.assertEqual(listing.status_code,200,listing.text)
        self.assertEqual(listing.json()['stats']['negative'],1)
        detail=self.client.get('/api/feedback/'+identity,headers=self.headers('admin')).json()
        self.assertEqual(detail['snapshot']['output_text'],'نص عربي')
        review=self.client.patch('/api/feedback/'+identity,headers=self.headers('admin'),json={'status':'reviewed','admin_note':'Updated guidance','expected_updated_at':detail['updated_at']})
        self.assertEqual(review.status_code,200,review.text)
        self.assertEqual(self.client.get('/api/feedback/'+identity,headers=self.headers('admin')).json()['admin_note'],'Updated guidance')
        self.assertEqual(self.client.get('/api/feedback/'+identity,headers=self.headers('super')).status_code,403)
        self.assertGreater(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_notifications').fetchone()[0],0)

    def test_approval_persists_and_enforces_reviewer_language(self):
        moved=self.client.post('/api/approvals/batch1/move',headers=self.headers(),json={})
        self.assertEqual(moved.status_code,200,moved.text)
        approved=self.client.post('/api/approvals/batch1/decision',headers=self.headers('reviewer'),json={'action':'approve','language':'en','note':'English checked'})
        self.assertEqual(approved.status_code,200,approved.text)
        self.assertEqual(self.db.sqlite.execute('SELECT language_code FROM genai_harf_language_approvals').fetchone()[0],'en')
        denied=self.client.post('/api/approvals/batch1/decision',headers=self.headers('reviewer'),json={'action':'approve','language':'ar','note':''})
        self.assertIn(denied.status_code,[403,409])
        self.assertEqual(access_control.load_access_data()['approval_batches'][0]['status'],'pending_layer_1')

    def test_instruction_save_history_cache_and_restore(self):
        from instruction_versions import version_repository
        path=access_control.CHANNEL_PROMPT_DIR/'b2c/01_B2C_SYSTEM_INSTRUCTIONS.md'
        repository=version_repository(path)
        original=path.read_text(encoding='utf-8')
        self.assertEqual(repository.current('b2c','B2C_SYSTEM',path)['version'],1)
        saved=repository.save('b2c','B2C_SYSTEM',path,path,'New Arabic rules: قواعد عربية',{'name':'Admin','email':'admin@example.test','role':'channel_admin'},1,'Update')
        self.assertEqual(saved['version'],2)
        history=repository.list('b2c','B2C_SYSTEM',path)
        self.assertEqual(len(history['versions']),2)
        self.assertNotIn('content',history['versions'][0])
        path.write_text('Out of date cache',encoding='utf-8')
        access_control.instruction_path('B2C_SYSTEM','b2c')
        self.assertEqual(path.read_text(encoding='utf-8'),'New Arabic rules: قواعد عربية')
        first=repository.get('b2c','B2C_SYSTEM',path,1)
        repository.save('b2c','B2C_SYSTEM',path,path,first['content'],{'name':'Admin','role':'channel_admin'},2,'Restore',1)
        self.assertEqual(path.read_text(encoding='utf-8'),original)
        self.assertEqual(repository.current('b2c','B2C_SYSTEM',path)['version'],3)

    def test_oracle_outage_does_not_fall_back_to_local_users(self):
        with patch.object(runtime,'pool',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError): access_control.load_access_data()
            response=self.client.get('/api/health/storage')
            self.assertEqual(response.status_code,503)

    def test_recovery_contains_new_outputs_and_detects_later_changes(self):
        data=access_control.load_access_data(); data['approval_batches'][0]['items'][0]['generated']['ar']='النص الأحدث'
        access_control.save_access_data(data)
        snapshot=export_snapshot(self.db)
        self.assertEqual(snapshot['access']['approval_batches'][0]['items'][0]['generated']['ar'],'النص الأحدث')
        exported=materialize(snapshot,self.root)
        migration.load_backup(exported)
        data=access_control.load_access_data(); data['users'][0]['name']='Later change'; access_control.save_access_data(data)
        self.assertNotEqual(recovery_fingerprint(snapshot),recovery_fingerprint(export_snapshot(self.db)))

    def test_reverse_restore_preserves_new_content_and_database_stores(self):
        data=access_control.load_access_data(); data['approval_batches'][0]['items'][0]['generated']['ar']='نسخة جديدة بعد الانتقال'
        access_control.save_access_data(data)
        user=data['users'][0]
        RequestLimits().set_user('b2c',user,9)
        snapshot=export_snapshot(self.db)
        exported=materialize(snapshot,self.root)
        with patch.object(migration,'require_stopped'),patch('oracle_recovery.configure') as configure:
            previous=restore_local(exported,self.root)
        self.assertTrue((previous/'manifest.json').is_file())
        configure.assert_called_once_with('local')
        restored=json.loads(access_control.DATA_FILE.read_text(encoding='utf-8'))
        self.assertEqual(restored['approval_batches'][0]['items'][0]['generated']['ar'],'نسخة جديدة بعد الانتقال')
        with closing(sqlite3.connect(self.root/'backend/request-limits.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT monthly_limit FROM user_limits').fetchone()[0],9)

    def test_feedback_notification_failure_rolls_back_feedback(self):
        payload={'snapshot':{'channel_id':'b2c','output_text':'Test output'},'rating':'up'}
        with patch.object(feedback,'notify_admins',side_effect=RuntimeError('notification failed')):
            with self.assertRaises(RuntimeError): self.client.post('/api/feedback',headers=self.headers(),json=payload)
        self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_feedback').fetchone()[0],0)

    def test_old_layout_backup_restores_into_current_instruction_folder(self):
        configure_fetch(self.db)
        snapshot = export_snapshot(self.db)
        snapshot['source_files'] = {
            key.replace('instructions/', 'Copywriter/backend/prompt/', 1): value
            for key, value in snapshot['source_files'].items()
        }
        exported = materialize(snapshot, self.root)
        with patch.object(migration, 'require_stopped'), patch('oracle_recovery.configure'):
            restore_local(exported, self.root)
        for relative, content in snapshot['source_files'].items():
            current = relative.replace('Copywriter/backend/prompt/', 'instructions/', 1)
            self.assertEqual((self.root / current).read_text(encoding='utf-8'), content)
        self.assertFalse((self.root / 'Copywriter').exists())

    def test_instruction_commit_failure_restores_cache_and_history(self):
        from instruction_versions import version_repository
        path=access_control.CHANNEL_PROMPT_DIR/'b2c/01_B2C_SYSTEM_INSTRUCTIONS.md'
        original=path.read_text(encoding='utf-8')
        self.db.fail_commit=True
        with self.assertRaises(RuntimeError):
            version_repository(path).save('b2c','B2C_SYSTEM',path,path,'Change that must roll back',{'name':'Admin','role':'channel_admin'},1)
        self.assertEqual(path.read_text(encoding='utf-8'),original)
        self.assertEqual(self.db.sqlite.execute('SELECT MAX(version_no) FROM genai_harf_instruction_versions').fetchone()[0],1)

    def test_new_channel_has_only_its_own_three_instruction_files(self):
        response=self.client.post('/api/access/channels',headers=self.headers('super'),json={'name':'New team'})
        self.assertEqual(response.status_code,200,response.text)
        channel=response.json()['id']
        rows=self.db.sqlite.execute('SELECT file_name,content_md FROM genai_harf_instructions WHERE channel_id=?',(channel,)).fetchall()
        self.assertEqual(len(rows),3)
        self.assertEqual({r[0] for r in rows},{'01_SYSTEM_INSTRUCTIONS.md','02_CHANNEL_TEMPLATE_INSTRUCTIONS.md','03_USER_AND_ADMIN_GUIDE.md'})
        self.assertTrue(all('Keep facts. العربية سليمة.' not in r[1] for r in rows))

    def test_access_cache_returns_independent_copies_and_no_uncommitted_updates(self):
        first=access_control.load_access_data(); first['users'][0]['name']='Unsaved edit'
        self.assertEqual(access_control.load_access_data()['users'][0]['name'],'Test')
        with self.assertRaises(RuntimeError):
            with access_control.DATA_LOCK:
                data=access_control.load_access_data(); data['users'][0]['name']='Uncommitted'
                access_control.save_access_data(data)
                self.assertEqual(access_control.load_access_data()['users'][0]['name'],'Uncommitted')
                raise RuntimeError('abort')
        self.assertEqual(access_control.load_access_data()['users'][0]['name'],'Test')

    def test_quota_channel_updates_and_feedback_repeated_vote_sql(self):
        RequestLimits().set_channel('b2c',150)
        self.assertEqual(self.db.sqlite.execute('SELECT monthly_limit FROM genai_harf_channel_limits').fetchone()[0],150)
        payload={'snapshot':{'channel_id':'b2c','output_text':'Full generated output'},'rating':'up'}
        first=self.client.post('/api/feedback',headers=self.headers(),json=payload)
        self.assertEqual(first.status_code,200,first.text)
        payload.update(rating='down',reason='Changed feedback')
        second=self.client.post('/api/feedback',headers=self.headers(),json=payload)
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json()['id'],first.json()['id'])
        mine=self.client.get('/api/feedback/mine',params={'channel_id':'b2c','fingerprint':first.json()['fingerprint']},headers=self.headers())
        self.assertEqual(mine.json()['feedback']['reason'],'Changed feedback')

    def test_paging_and_storage_health(self):
        response=self.client.get('/api/feedback',params={'channel_id':'b2c','page':2},headers=self.headers('admin'))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['items'],[])
        self.assertEqual(self.client.get('/api/health/storage').json(),{'status':'ok','storage':'oracle'})

    def test_real_sql_probe_logic_rolls_back_every_fictional_record(self):
        from oracle_probe import validate_runtime_sql
        empty=Database()
        self.addCleanup(empty.sqlite.close)
        validate_runtime_sql(empty,self.root)
        self.assertEqual(empty.sqlite.execute('SELECT COUNT(*) FROM genai_harf_users').fetchone()[0],0)
        self.assertEqual(empty.sqlite.execute('SELECT COUNT(*) FROM genai_harf_runtime_state').fetchone()[0],0)

    def test_recovery_refuses_unsynchronized_direct_database_changes(self):
        self.db.sqlite.execute("UPDATE genai_harf_outputs SET output_text='Direct database edit' WHERE language_code='en'")
        self.db.sqlite.commit()
        configure_fetch(self.db)
        with self.assertRaisesRegex(ValueError,'verification failed') as error: export_snapshot(self.db)
        self.assertIn('output_text',str(error.exception))
        self.assertNotIn('Direct database edit',str(error.exception))

    def test_driver_json_fetch_mismatch_reproduced_and_handler_restores_exact_text(self):
        with self.db.cursor() as cursor:
            cursor.execute("SELECT config_json FROM genai_harf_channels WHERE channel_id='b2c'")
            self.assertIsInstance(cursor.fetchone()[0],dict)
        configure_fetch(self.db)
        with self.db.cursor() as cursor:
            cursor.execute("SELECT config_json FROM genai_harf_channels WHERE channel_id='b2c'")
            value=cursor.fetchone()[0]
            self.assertIsInstance(value,Lob)
            self.assertEqual(value.read(),canonical(self.snapshot['access']['channels'][0]))

    def test_output_handler_preserves_lob_type_arraysize_and_nonjson_columns(self):
        import oracledb
        cursor=SimpleNamespace(arraysize=80,var=Mock(return_value='native LOB variable'))
        self.assertEqual(json_text_handler(cursor,SimpleNamespace(is_json=True,type_code=oracledb.DB_TYPE_CLOB)),'native LOB variable')
        cursor.var.assert_called_once_with(oracledb.DB_TYPE_CLOB,arraysize=80)
        cursor.var.reset_mock()
        self.assertIsNone(json_text_handler(cursor,SimpleNamespace(is_json=False,type_code=oracledb.DB_TYPE_NUMBER)))
        cursor.var.assert_not_called()


    def test_input_policy_and_usage_logs_preserve_saved_work(self):
        from contextlib import contextmanager
        from datetime import datetime, timezone
        from llm_rate_limits import channel_scope
        from input_tokens import enforce
        from token_usage import record
        from platform_policy import settings, run_retention
        env = self.root/'policy.env'
        env.write_text('USER_LOG_RETENTION_DAYS=180\nLLM_MAX_INPUT_TOKENS=64000\n',encoding='utf8')
        before = deepcopy(access_control.load_access_data()['approval_batches'])
        with patch.dict('os.environ',{'PLATFORM_POLICY_ENV_FILE':str(env)}),channel_scope('b2c'):
            enforce([{'role':'user','content':'Fictional input'}], 'gpt-4o')
            record({'input_tokens':40,'output_tokens':10,'total_tokens':50})
            self.assertEqual(settings()['default_max_input_tokens'],64000)
            self.assertEqual(sum(row['total_tokens'] for row in access_control.load_access_data()['token_usage']['channels']['b2c'].values()),50)
            with access_control.DATA_LOCK:
                data=access_control.load_access_data()
                data['activity'].append(dict(timestamp='2020-01-01T00:00:00+00:00',actor='Test',actor_email='test@example.test',action='Old event',detail='Expired log',channel_id='b2c'))
                access_control.save_access_data(data)
            with RequestLimits().transaction() as db:
                db.execute('INSERT INTO request_usage VALUES(?,?,?,?,?,?,?)',('old-request','b2c','local:test@example.test','2020-01','completed',0,'2020-01-01T00:00:00+00:00'))
            @contextmanager
            def rate_state(*args): yield {}
            with patch('llm_rate_limits.LLMRateLimits.state',rate_state):
                result=run_retention(force=True,now=datetime.now(timezone.utc))
            self.assertEqual(result['activity'],1)
            self.assertEqual(result['request_usage'],1)
            self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_activity').fetchone()[0],0)
            self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_request_usage').fetchone()[0],0)
            self.assertEqual(access_control.load_access_data()['approval_batches'],before)


if __name__=='__main__': unittest.main()
