import os
import shutil
import sys
import tempfile
import unittest

from mavis.breakpoint import read_bpp_from_input_file
from mavis.constants import PIPELINE_STEP
from mavis.main import main
from mock import patch


DATA_PREFIX = os.path.join(os.path.dirname(__file__), 'data')
TEMP_OUTPUT = None


def setUpModule():
    global TEMP_OUTPUT
    # create the temp output directory to store file outputs
    TEMP_OUTPUT = tempfile.mkdtemp()


class TestPairing(unittest.TestCase):

    def test_pairing(self):
        args = [
            'mavis', PIPELINE_STEP.PAIR,
            '-n', os.path.join(DATA_PREFIX, 'pairing_annotations.tab'),
            '-f', os.path.join(DATA_PREFIX, 'pairing_sequences.fa'),
            '-o', TEMP_OUTPUT,
            '--annotations', os.path.join(DATA_PREFIX, 'pairing_reference_annotations_file.tab')
        ]
        with patch.object(sys, 'argv', args):
            self.assertEqual(0, main())
        # make sure the output file exists
        output = os.path.join(TEMP_OUTPUT, 'mavis_paired_A36971_A36973.tab')
        self.assertTrue(os.path.exists(output))
        # check that the expected pairings are present
        bpps = read_bpp_from_input_file(output, explicit_strand=False, expand_ns=False)
        self.assertEqual(6, len(bpps))


def tearDownModule():
    # remove the temp directory and outputs
    shutil.rmtree(TEMP_OUTPUT)


if __name__ == '__main__':
    unittest.main()
