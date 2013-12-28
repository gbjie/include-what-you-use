#!/usr/bin/python

##===--- run_iwyu_tests.py - include-what-you-use test framework driver ----===##
#
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.
#
##===-----------------------------------------------------------------------===##

"""A test harness for IWYU testing."""

__author__ = 'dsturtevant@google.com (Dean Sturtevant)'

import glob
import os
import re
import sys
import unittest
import logging
logging.basicConfig(level=logging.INFO)
class Flags(object):
   def __init__(self): self.test_files = []
FLAGS = Flags()
import iwyu_test_util


TEST_ROOTDIR = 'tests'


def CheckAlsoExtension(extension):
  """Return a suitable iwyu flag for checking files with the given extension."""
  return '--check_also="%s"' % os.path.join(TEST_ROOTDIR, '*' + extension)


def MappingFile(filename):
  """Return a suitable iwyu flag for adding the given mapping file."""
  return '--mapping_file=%s' % os.path.join(TEST_ROOTDIR, filename)


class OneIwyuTest(unittest.TestCase):
  """Superclass for tests.  A subclass per test-file is created at runtime."""

  def setUp(self):
    # Iwyu flags for specific tests.
    # Map from filename to flag list. If any test requires special
    # iwyu flags to run properly, add an entry to the map with
    # key=cc-filename (relative to TEST_ROOTDIR), value=list of flags.
    flags_map = {
      'backwards_includes.cc': [CheckAlsoExtension('-d*.h')],
      'badinc.cc': [MappingFile('badinc.imp')],
      'check_also.cc': [CheckAlsoExtension('-d1.h')],
      'implicit_ctor.cc': [CheckAlsoExtension('-d1.h')],
      'iwyu_stricter_than_cpp.cc': [CheckAlsoExtension('-autocast.h'),
                                    CheckAlsoExtension('-fnreturn.h'),
                                    CheckAlsoExtension('-typedefs.h'),
                                    CheckAlsoExtension('-d2.h')],
      'keep_mapping.cc': [CheckAlsoExtension('-public.h'), 
                          MappingFile('keep_mapping.imp')],
      'macro_location.cc': [CheckAlsoExtension('-d2.h')],
      'non_transitive_include.cc': [CheckAlsoExtension('-d*.h'),
                                    '--transitive_includes_only'],
      'no_h_includes_cc.cc': [CheckAlsoExtension('.c')],
      'overloaded_class.cc': [CheckAlsoExtension('-i1.h')],
      'prefix_header_includes_add.cc': ['--prefix_header_includes=add'],
      'prefix_header_includes_keep.cc': ['--prefix_header_includes=keep'],
      'prefix_header_includes_remove.cc': ['--prefix_header_includes=remove'],
    }
    prefix_headers = ['-include', 'tests/prefix_header_includes-d1.h',
                      '-include', 'tests/prefix_header_includes-d2.h',
                      '-include', 'tests/prefix_header_includes-d3.h',
                      '-include', 'tests/prefix_header_includes-d4.h']
    clang_flags_map = {
      'auto_type_within_template.cc': ['-std=c++11'],
      'conversion_ctor.cc': ['-std=c++11'],
      'ms_inline_asm.cc': ['-fms-extensions'],
      'prefix_header_includes_add.cc': prefix_headers,
      'prefix_header_includes_keep.cc': prefix_headers,
      'prefix_header_includes_remove.cc': prefix_headers,
    }
    # Internally, we like it when the paths start with TEST_ROOTDIR.
    self._iwyu_flags_map = dict((os.path.join(TEST_ROOTDIR, k), v)
                                for (k,v) in flags_map.items())
    self._clang_flags_map = dict((os.path.join(TEST_ROOTDIR, k), v)
                                 for (k,v) in clang_flags_map.items())

  def RunOneTest(self, filename):
    logging.info('Testing iwyu on %s', filename)
    # Split full/path/to/foo.cc into full/path/to/foo and .cc.
    (all_but_extension, _) = os.path.splitext(filename)
    (dirname, basename) = os.path.split(all_but_extension)
    # Generate diagnostics on all foo-* files (well, not other
    # foo-*.cc files, which is not kosher but is legal), in addition
    # to foo.h (if present) and foo.cc.
    all_files = (glob.glob('%s-*' % all_but_extension) +
                 glob.glob('%s/*/%s-*' % (dirname, basename)) +
                 glob.glob('%s.h' % all_but_extension) +
                 glob.glob('%s/*/%s.h' % (dirname, basename)))
    files_to_check = [f for f in all_files if not f.endswith('.cc')]
    files_to_check.append(filename)

    # IWYU emits summaries with canonicalized filepaths, where all the
    # directory separators are set to '/'. In order for the testsuite to
    # correctly match up file summaries, we must canonicalize the filepaths
    # in the same way here.
    files_to_check = [f.replace(os.sep, '/') for f in files_to_check]

    iwyu_flags = self._iwyu_flags_map.get(filename, None)
    if iwyu_flags:
      logging.info('%s: Using iwyu flags %s', filename, str(iwyu_flags))

    clang_flags = self._clang_flags_map.get(filename, None)
    if clang_flags:
      logging.info('%s: Using clang flags %s', filename, str(clang_flags))

    iwyu_test_util.TestIwyuOnRelativeFile(self, filename, files_to_check,
                                          iwyu_flags, clang_flags, verbose=True)


def RegisterFilesForTesting():
  """Create a test-class for every .cc file in TEST_ROOTDIR."""
  module = sys.modules[__name__]
  filenames = []
  for (dirpath, dirs, files) in os.walk(TEST_ROOTDIR):
    filenames.extend(os.path.join(dirpath, f) for f in files
                     if f.endswith('.cc'))
  if not filenames:
    sys.exit('No tests found in %s!' % os.path.abspath(TEST_ROOTDIR))
  for filename in filenames:
    basename = os.path.basename(filename[:-len('.cc')])
    class_name = re.sub('[^0-9a-zA-Z_]', '_', basename)  # python-clean
    if class_name[0].isdigit():            # classes can't start with a number
      class_name = '_' + class_name
    while class_name in module.__dict__:   # already have a class with that name
      class_name += '2'                    # just append a suffix :-)

    logging.info('Registering %s to test %s', class_name, filename)
    test_class = type(class_name,          # class name
                      (OneIwyuTest,),      # superclass
                      # and methods.  f=filename is required for proper scoping
                      {'runTest': lambda self, f=filename: self.RunOneTest(f)})
    setattr(module, test_class.__name__, test_class)


if __name__ == '__main__':

  RegisterFilesForTesting()
  unittest.main()