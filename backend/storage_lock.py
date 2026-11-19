"""Existing application critical sections also become Oracle units of work."""
from functools import wraps
import sys
from threading import RLock,local

from storage_backend import oracle_enabled


class StorageLock:
    def __init__(self):
        self.lock=RLock()
        self.state=local()
    def __enter__(self):
        self.lock.acquire()
        context=None
        try:
            if oracle_enabled():
                from oracle_runtime import transaction,_unit
                if getattr(_unit,'db',None) is None:
                    context=transaction()
                    db=context.__enter__()
                    with db.cursor() as cursor:
                        cursor.execute("SELECT revision FROM genai_harf_runtime_state WHERE state_id='access' FOR UPDATE WAIT 10")
                        if cursor.fetchone() is None: raise RuntimeError('Oracle runtime state is missing.')
            if not hasattr(self.state,'stack'): self.state.stack=[]
            self.state.stack.append(context)
            return self
        except BaseException:
            if context is not None: context.__exit__(*sys.exc_info())
            self.lock.release()
            raise
    def __exit__(self,kind,value,traceback):
        context=self.state.stack.pop()
        try:
            if context is not None: return context.__exit__(kind,value,traceback)
        finally:
            self.lock.release()


def atomic_change(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        from access_control import DATA_LOCK
        with DATA_LOCK:
            return function(*args,**kwargs)
    return wrapped
