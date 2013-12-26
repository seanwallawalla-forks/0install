#!/usr/bin/env python
import locale
locale.setlocale(locale.LC_ALL, 'C')
import sys, tempfile, os, shutil, imp
import unittest, subprocess
import logging
import warnings
if sys.version_info[0] > 2:
	from io import StringIO, BytesIO
else:
	from StringIO import StringIO
	BytesIO = StringIO
warnings.filterwarnings("ignore", message = 'The CObject type')

# Catch silly mistakes...
os.environ['HOME'] = '/home/idontexist'
os.environ['LANGUAGE'] = 'C'
os.environ['LANG'] = 'C'

if 'ZEROINSTALL_CRASH_LOGS' in os.environ: del os.environ['ZEROINSTALL_CRASH_LOGS']

sys.path.insert(0, '..')
from zeroinstall import support

def skipIf(condition, reason):
	def wrapped(underlying):
		if condition:
			if hasattr(underlying, 'func_name'):
				print("Skipped %s: %s" % (underlying.func_name, reason))	# Python 2
			else:
				print("Skipped %s: %s" % (underlying.__name__, reason))		# Python 3
			def run(self): pass
			return run
		else:
			return underlying
	return wrapped

dpkgdir = os.path.join(os.path.dirname(__file__), 'dpkg')

mydir = os.path.dirname(__file__)
ocaml_0install = os.path.join(mydir, '..', 'build', 'ocaml', '0install')

class ExecMan(Exception):
	def __init__(self, args):
		self.man_args = args
		Exception.__init__(self, 'ExecMan')

# Catch us trying to run the GUI and return a dummy string instead
old_execvp = os.execvp
def test_execvp(prog, args):
	if prog == sys.executable and args[1].endswith('/0launch-gui'):
		prog = os.path.join(mydir, 'test-gui')
	if prog == 'man':
		raise ExecMan(args)
	return old_execvp(prog, args)

os.execvp = test_execvp

class TestConfig:
	freshness = 0
	help_with_testing = False
	key_info_server = None
	auto_approve_keys = False
	mirror = None

class BaseTest(unittest.TestCase):
	def setUp(self):
		warnings.resetwarnings()

		self.config_home = tempfile.mktemp()
		self.cache_home = tempfile.mktemp()
		self.cache_system = tempfile.mktemp()
		self.data_home = tempfile.mktemp()
		self.gnupg_home = tempfile.mktemp()
		os.environ['GNUPGHOME'] = self.gnupg_home
		os.environ['XDG_CONFIG_HOME'] = self.config_home
		os.environ['XDG_CONFIG_DIRS'] = ''
		os.environ['XDG_CACHE_HOME'] = self.cache_home
		os.environ['XDG_CACHE_DIRS'] = self.cache_system
		os.environ['XDG_DATA_HOME'] = self.data_home
		os.environ['XDG_DATA_DIRS'] = ''
		if 'ZEROINSTALL_PORTABLE_BASE' in os.environ:
			del os.environ['ZEROINSTALL_PORTABLE_BASE']

		os.mkdir(self.config_home, 0o700)
		os.mkdir(self.cache_home, 0o700)
		os.mkdir(self.cache_system, 0o500)
		os.mkdir(self.gnupg_home, 0o700)

		if 'DISPLAY' in os.environ:
			del os.environ['DISPLAY']

		self.config = TestConfig()

		logging.getLogger().setLevel(logging.WARN)

		self.old_path = os.environ['PATH']
		os.environ['PATH'] = self.config_home + ':' + dpkgdir + ':' + self.old_path

	def tearDown(self):
		shutil.rmtree(self.config_home)
		support.ro_rmtree(self.cache_home)
		shutil.rmtree(self.cache_system)
		shutil.rmtree(self.gnupg_home)

		os.environ['PATH'] = self.old_path

	def run_ocaml(self, args, stdin = None, stderr = subprocess.PIPE, binary = False):
		child = subprocess.Popen([ocaml_0install] + args,
				stdin = subprocess.PIPE if stdin is not None else None,
				stdout = subprocess.PIPE, stderr = stderr, universal_newlines = not binary)
		out, err = child.communicate(stdin)
		status = child.wait()
		if status:
			msg = "Exit status: %d\n" % status
			if binary:
				msg = msg.encode('utf-8')
			err += msg
		return out, err
