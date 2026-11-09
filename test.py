"""Run test_xapian.py and test_xapian.cc against one or several Xapian installs.

Usage:

    python3 test.py [PREFIX ...]

Each PREFIX is a Xapian install prefix (the one given to ./configure --prefix),
for example /usr, /usr/local or ~/opt/xapian-2.1.0. It must contain
bin/xapian-config, and the Python bindings under lib*/python3*/site-packages.
Without PREFIX, the tests use the xapian module of the current interpreter and
the xapian-config found in PATH.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pprint import pprint

HERE = os.path.dirname(os.path.abspath(__file__))


def run(label, cmd, env=None):
    print(f'---- {label}: {" ".join(cmd)}', flush=True)
    returncode = subprocess.call(cmd, cwd=HERE, env=env)
    print(flush=True)
    return {0: 'ok', 1: 'BUG'}.get(returncode, f'error ({returncode})')


def python_env(prefix):
    env = dict(os.environ)
    if prefix is None:
        return env
    site = glob.glob(os.path.join(prefix, 'lib*', 'python3*', 'site-packages', 'xapian'))
    if not site:
        return None
    env['PYTHONPATH'] = os.path.dirname(site[0])
    env['LD_LIBRARY_PATH'] = os.pathsep.join(
        [os.path.join(prefix, 'lib'), os.path.join(prefix, 'lib64')])
    return env


def compile_cc(prefix, tmp):
    config = os.path.join(prefix, 'bin', 'xapian-config') if prefix else 'xapian-config'
    if not shutil.which(config):
        return None
    flags = subprocess.check_output([config, '--cxxflags', '--libs'], text=True).split()
    libdir = subprocess.check_output([config, '--libs'], text=True).split()
    libdir = [f[2:] for f in libdir if f.startswith('-L')]
    # /usr/local/include comes before /usr/include in the default include
    # path: link the headers of this install into a private directory
    includedir = subprocess.check_output([config, '--cxxflags'], text=True).split()
    includedir = [f[2:] for f in includedir if f.startswith('-I')]
    includedir = includedir[0] if includedir else os.path.join(prefix or '/usr', 'include')
    inc = os.path.join(tmp, 'include')
    os.makedirs(inc, exist_ok=True)
    for name in ('xapian.h', 'xapian'):
        os.symlink(os.path.join(includedir, name), os.path.join(inc, name))
    binary = os.path.join(tmp, 'test_xapian')
    cmd = ['g++', '-O2', '-std=c++17', '-I' + inc, '-o', binary,
           os.path.join(HERE, 'test_xapian.cc')] + flags
    cmd += ['-Wl,-rpath,' + d for d in libdir]
    print(f'---- compile: {" ".join(cmd)}', flush=True)
    subprocess.check_call(cmd)
    return binary


def main():
    prefixes = [os.path.expanduser(p) for p in sys.argv[1:]] or [None]
    results = {}
    for prefix in prefixes:
        name = prefix or 'default'
        print('=' * 72)
        print(name)
        print('=' * 72)
        results[name] = {}
        env = python_env(prefix)
        if env is None:
            results[name]['python'] = 'no bindings'
        else:
            results[name]['python'] = run('python', [sys.executable, 'test_xapian.py'], env)
        tmp = tempfile.mkdtemp(prefix='xapian_test_')
        try:
            binary = compile_cc(prefix, tmp)
            if binary is None:
                results[name]['c++'] = 'no xapian-config'
            else:
                results[name]['c++'] = run('c++', [binary])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print('=' * 72)
    pprint(results)
    return 1 if any('BUG' in r.values() for r in results.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
