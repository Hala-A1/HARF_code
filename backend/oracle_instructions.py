"""Native Oracle instruction history, reusing the existing save/restore safeguards."""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
from pathlib import Path

from fastapi import HTTPException

from instruction_versions import InstructionVersionRepository
from oracle_mapping import canonical
from oracle_runtime import transaction,text,Row

FIELDS=('channel_id','module_id','version','content','checksum','created_at','actor_name','actor_email',
        'actor_role','action','note','restored_from','characters','words','lines')
SELECT="""SELECT channel_id,module_id,version_no,content_md,checksum,
    TO_CHAR(created_at,'YYYY-MM-DD"T"HH24:MI:SS.FF6TZH:TZM'),actor_name,actor_email,
    actor_role,change_action,change_note,restored_from,character_count,word_count,line_count
    FROM genai_harf_instruction_versions """


def as_row(values):
    if values is None: return None
    values=[text(v) for v in values]
    values[10]=values[10] or ''
    return Row(FIELDS,values)


def latest(db,channel,module):
    with db.cursor() as cursor:
        cursor.execute(SELECT+'WHERE channel_id=:channel AND module_id=:module ORDER BY version_no DESC FETCH FIRST 1 ROW ONLY',channel=channel,module=module)
        return as_row(cursor.fetchone())


def append_version(db,channel,module,path,content,actor,action,note='',restored_from=None):
    import oracledb
    import access_control
    from oracle_migration import insert_rows
    current=latest(db,channel,module)
    version=current['version']+1 if current else 1
    now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
    checksum=hashlib.sha256(content.encode('utf-8')).hexdigest()
    info=access_control.INSTRUCTION_MODULES.get(module,{})
    filename=Path(path).name
    kind='guide' if 'guide' in filename.lower() else 'system' if 'system' in filename.lower() else 'template' if 'template' in filename.lower() else 'reference'
    with db.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM genai_harf_instructions WHERE channel_id=:channel AND module_id=:module',channel=channel,module=module)
        exists=bool(cursor.fetchone()[0])
    if not exists:
        insert_rows(db,'genai_harf_instructions',[dict(channel_id=channel,module_id=module,file_name=filename,
            display_name=info.get('name',filename),instruction_kind=kind,is_active=1,current_version=version,checksum=checksum,
            content_md=content,metadata_json=canonical(dict(file_name=filename,module_id=module)),updated_at=now)])
    else:
        with db.cursor() as cursor:
            cursor.setinputsizes(content=oracledb.DB_TYPE_CLOB)
            cursor.execute('UPDATE genai_harf_instructions SET current_version=:version,checksum=:checksum,content_md=:content,updated_at=SYSTIMESTAMP WHERE channel_id=:channel AND module_id=:module',
                           version=version,checksum=checksum,content=content,channel=channel,module=module)
    insert_rows(db,'genai_harf_instruction_versions',[dict(channel_id=channel,module_id=module,version_no=version,
        content_md=content,checksum=checksum,created_at=now,actor_name=actor['name'],actor_email=actor.get('email'),
        actor_role=actor['role'],change_action=action,change_note=note,restored_from=restored_from,
        character_count=len(content),word_count=len(content.split()),line_count=len(content.splitlines()))])
    return latest(db,channel,module)


class OracleInstructionVersions(InstructionVersionRepository):
    def __init__(self,source_path):
        self.source_path=Path(source_path)

    @contextmanager
    def transaction(self):
        with transaction() as db:
            with db.cursor() as cursor:
                # Serialize version allocation even when no first version exists yet.
                cursor.execute('LOCK TABLE genai_harf_instructions IN EXCLUSIVE MODE WAIT 10')
            yield db

    @staticmethod
    def _latest(db,channel,module): return latest(db,channel,module)

    def _append(self,db,channel,module,content,actor,action,note='',restored_from=None):
        return append_version(db,channel,module,self.source_path,content,actor,action,note,restored_from)

    def list(self,channel,module,path,offset=0,limit=20):
        with self.transaction() as db:
            current=self._sync(db,channel,module,path)
            with db.cursor() as cursor:
                # History lists never fetch the potentially huge Markdown CLOB.
                projection=SELECT.replace('version_no,content_md,checksum','version_no,NULL,checksum')
                cursor.execute(projection+'WHERE channel_id=:channel AND module_id=:module ORDER BY version_no DESC OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY',
                               channel=channel,module=module,offset=offset,limit=limit)
                rows=[self.public(as_row(v)) for v in cursor]
            return dict(versions=rows,current_version=current['version'],total=current['version'],offset=offset,limit=limit)

    def get(self,channel,module,path,version):
        with self.transaction() as db:
            self._sync(db,channel,module,path)
            with db.cursor() as cursor:
                cursor.execute(SELECT+'WHERE channel_id=:channel AND module_id=:module AND version_no=:version',channel=channel,module=module,version=version)
                row=as_row(cursor.fetchone())
            if row is None: raise HTTPException(status_code=404,detail='Instruction version was not found.')
            return dict(row)
