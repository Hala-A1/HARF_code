"""Manage only this checkout's backend through native process APIs.

No PowerShell script or execution-policy changes are required. Every listener is
validated before any process is stopped; unrelated services are left untouched.
"""
from pathlib import Path
import subprocess

import psutil

ROOT=Path(__file__).resolve().parent


def listeners():
    owners=set()
    for item in psutil.net_connections(kind='tcp'):
        if item.status==psutil.CONN_LISTEN and item.laddr and item.laddr.port==8000:
            if item.pid is None: raise ValueError('Cannot identify the service on port 8000. No process was changed.')
            owners.add(item.pid)
    return owners


def verified_processes():
    expected_python=(ROOT/'.venv/Scripts/python.exe').resolve()
    processes=[]
    for pid in listeners():
        try:
            process=psutil.Process(pid)
            arguments=process.cmdline()
            directory=Path(process.cwd()).resolve()
            if (len(arguments)!=2 or Path(arguments[0]).resolve()!=expected_python or directory!=ROOT.resolve()
                    or (directory/arguments[1]).resolve()!=(ROOT/'main.py').resolve()):
                raise ValueError('Port 8000 belongs to an unrecognized service. No process was stopped.')
            processes.append(process)
        except psutil.NoSuchProcess:
            continue
    return processes


def maintenance(action):
    try:
        if action=='stop':
            processes=verified_processes()
            for process in processes:
                try: process.terminate()
                except psutil.NoSuchProcess: pass
            _,alive=psutil.wait_procs(processes,timeout=10)
            if alive: raise ValueError('The backend did not stop within 10 seconds. Keep the original stores intact and retry after closing its workers.')
            return {'was_running':bool(processes)}
        if action!='start': raise ValueError('Unknown backend maintenance action.')
        if listeners(): raise ValueError('Port 8000 is already in use. No additional backend was started.')
        python=ROOT/'.venv/Scripts/python.exe'
        if not python.is_file() or not (ROOT/'main.py').is_file():
            raise ValueError('The backend executable or entry point is missing.')
        with (ROOT/'server.out.log').open('wb') as output,(ROOT/'server.err.log').open('wb') as error:
            subprocess.Popen([str(python),'main.py'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=output,stderr=error,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return {'started':True}
    except psutil.AccessDenied:
        raise ValueError('Windows did not allow access to the backend process. Run the migration as the same Windows user that started the application.') from None
