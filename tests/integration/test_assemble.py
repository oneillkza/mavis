import os
import time
import unittest

import timeout_decorator

from mavis.assemble import Contig, assemble, filter_contigs
from mavis.interval import Interval
from mavis.constants import reverse_complement

from . import MockObject, DATA_DIR


class TestFilterContigs(unittest.TestCase):
    @timeout_decorator.timeout(30)
    def test_large_set(self):
        contigs = []
        with open(os.path.join(DATA_DIR, 'similar_contigs.txt'), 'r') as fh:
            for line in fh.readlines():
                contigs.append(Contig(line.strip(), 1))  # give a dummy score of 1
        start_time = int(time.time())
        filtered = filter_contigs(contigs, 0.10)
        end_time = int(time.time())
        print('duration:', end_time - start_time)
        print()
        for c in filtered:
            print(c.seq)
        self.assertEqual(3, len(filtered))  # figure out amount later. need to optimize timing


class TestContigRemap(unittest.TestCase):
    def setUp(self):
        self.contig = Contig(' ' * 60, None)
        self.contig.add_mapped_sequence(MockObject(reference_start=0, reference_end=10))
        self.contig.add_mapped_sequence(MockObject(reference_start=0, reference_end=20))
        self.contig.add_mapped_sequence(MockObject(reference_start=50, reference_end=60))

    def test_depth_even_coverage(self):
        covg = self.contig.remap_depth(Interval(1, 10))
        self.assertEqual(2, covg)

    def test_depth_mixed_coverage(self):
        covg = self.contig.remap_depth(Interval(1, 20))
        self.assertEqual(1.5, covg)

    def test_depth_no_coverage(self):
        covg = self.contig.remap_depth(Interval(21, 49))
        self.assertEqual(0, covg)

    def test_depth_whole_contig_coverage(self):
        self.assertAlmostEqual(40 / 60, self.contig.remap_depth())

    def test_depth_weighted_read(self):
        self.contig.add_mapped_sequence(MockObject(reference_start=0, reference_end=10), 5)
        self.assertAlmostEqual(42 / 60, self.contig.remap_depth())

    def test_depth_bad_query_range(self):
        with self.assertRaises(ValueError):
            self.contig.remap_depth(Interval(0, 10))
        with self.assertRaises(ValueError):
            self.contig.remap_depth(Interval(1, len(self.contig.seq) + 1))

    def test_coverage(self):
        self.assertEqual(0.5, self.contig.remap_coverage())


class TestAssemble(unittest.TestCase):
    def setUp(self):
        self.log = lambda *x, **k: print(x, k)

    def test1(self):
        sequences = [
            'TCTTTTTCTTTCTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAGTCTTACTGACAAGCATGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCGTAAATCGCCGTGCTTGGTGCTTAATGTACTT',
            'AAGTACATTAAGCACCAAGCACGGCGATTTACGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACATGCTTGTCAGTAAGACTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAGAAAGAAAAAGA',
            'CCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACT',
            'AGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGG',
            'TTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGAAATCTCCATGCTTGGTTGTTAAACTACTAATGCCTCACACGGGTCATCAG',
            'CTGATGACCCGTGTGAGGCATTAGTAGTTTAACAACCAAGCATGGAGATTTCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAA',
            'GGGGGAGGGGAGATTAGCACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGAC',
            'GTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTGCTAATCTCCCCTCCCCC',
            'GAGACTCCATCTCTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTTTTTCTTTCTTTCTTTCTTTCTTTCTATCTATCTATCTTGCATATTTTTACTTATTAAATTAGTTCTGTCCATCCAAT',
            'ATTGGATGGACAGAACTAATTTAATAAGTAAAAATATGCAAGATAGATAGATAGAAAGAAAGAAAGAAAGAAAGAAAAAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAGAGATGGAGTCTC',
            'CATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTCTTTCTTTTCTTTTTTCTTCCTG',
            'CAGGAAGAAAAAAGAAAAGAAAGAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATG',
            'CTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTG',
            'CAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAG',
            'ACTTTGCTTCCCTTGTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTC',
            'GAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCACAAGGGAAGCAAAGT',
            'TACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGA',
            'TCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTA',
            'TCCACAGTTCTCCACACTAACACAGGGCTAGTCTGTCTGTCCTCCTGTCTGGATTTGTTTCTTGCTTCCTCGCTGTCGTCCTGACTCTGTGCATCTATCGTGCCTTCCGTCTGTCTTACTTGGTTCCTTTGTGTTGGTATGTGAGGCTTT',
            'AAAGCCTCACATACCAACACAAAGGAACCAAGTAAGACAGACGGAAGGCACGATAGATGCACAGAGTCAGGACGACAGCGAGGAAGCAAGAAACAAATCCAGACAGGAGGACAGACAGACTAGCCCTGTGTTAGTGTGGAGAACTGTGGA',
            'AACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTTCTAGC',
            'GCTAGAAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTT',
            'CCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTTTTTCTATTTTTTCTTCTTCCTTTCTCT',
            'AGAGAAAGGAAGAAGAAAAAATAGAAAAAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGG',
            'TCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATC',
            'GATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGA',
            'CATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTTTTTTTGTTTTTTA',
            'TAAAAAACAAAAAAAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATG',
            'CCGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGCCTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGTCTCGTCCCAGCTTAATCTTATTGACCAGCAGGTTACCTTCTTTTTATTTTTGTT',
            'AACAAAAATAAAAAGAAGGTAACCTGCTGGTCAATAAGATTAAGCTGGGACGAGACAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGGCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACGG',
            'CTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCT',
            'AGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAG',
            'CATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAA',
            'TTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATG',
            'GCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGAAA',
            'TTTCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGC',
            'AACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGAAATCTCCATGCTTGGTTGTTAAAA',
            'TTTTAACAACCAAGCATGGAGATTTCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTT',
            'TCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGAAATCTCCATGCTTG',
            'CAAGCATGGAGATTTCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGA',
            'CCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGAAATCTCC',
            'GGAGATTTCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGG',
            'ACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGAAATCTCCAT',
            'ATGGAGATTTCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGT',
            'CTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACCTTCTTTTTATTTTTGTTTTTAAACCACATTGATCTGA',
            'TCAGATCAATGTGGTTTAAAAACAAAAATAAAAAGAAGGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAG',
            'TTCCCTTGTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTN',
            'NAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCACAAGGGAA',
            'TTCCCTTGTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTT',
            'AAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCACAAGGGAA',
            'GCTTCCCTTGTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCT',
            'AGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCACAAGGGAAGC',
            'TCCCTCTCTCGCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTC',
            'GAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGCGAGAGAGGGA',
            'TCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTCATTTCTTTCTTTCTTTTTCTTCCTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTC',
            'GAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAGGAAGAAAAAGAAAGAAAGAAATGAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGA',
            'TAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGACAAGCAGGTTACC',
            'GGTAACCTGCTTGTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTA',
            'GGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTC',
            'GAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCC',
            'TGGGGCAGGGGAGATTAGGACAACCTTCACCAGTTCGTTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTT',
            'AAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAACGAACTGGTGAAGGTTGTCCTAATCTCCCCTGCCCCA',
            'AGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTCTTTCTATTCTATCTTCTTCCTGACTCTTCCTAGCTTAATCTTAATGAC',
            'GTCATTAAGATTAAGCTAGGAAGAGTCAGGAAGAAGATAGAATAGAAAGAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACT',
            'CTTCCCTTGTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTT',
            'AAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCACAAGGGAAG',
            'TTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTCTTTCTATTCTAT',
            'ATAGAATAGAAAGAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAA',
            'CATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGGCTAGTCTGTCTGTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTCTTTTTCTTTCTTTCTTTCTTTCTTTCTTTTCTATCTTCTTCCTT',
            'AAGGAAGAAGATAGAAAAGAAAGAAAGAAAGAAAGAAAGAAAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGAAAGACAGACAGACTAGCCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATG',
            'GTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTCTTTCTATTCT',
            'AGAATAGAAAGAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCAC',
            'TGCTTCCCTTGTGCCCCTTTCCCTACCTGGGCCAAACTCAGAAGAGCTGGGGGAGGGGAGATTAGGACAACCTTCACCAGTTCATTTCCCTCTCTCTCTGCTTTCCACAGTTCTCCACACTAACAAAGGACTAGTCTTTTTCTTTCTTTC',
            'GAAAGAAAGAAAAAGACTAGTCCTTTGTTAGTGTGGAGAACTGTGGAAAGCAGAGAGAGAGGGAAATGAACTGGTGAAGGTTGTCCTAATCTCCCCTCCCCCAGCTCTTCTGAGTTTGGCCCAGGTAGGGAAAGGGGCACAAGGGAAGCA',
            'AGTAGCGTAATGAACTAAGTGAAGATGTGAAACAGAATTTTAACTTAATAACTTCAATCAGCAACACCCATCGACTCTTCCTAAACTCAAATCCCATGCCCTGCTAAATTATGGGACAAATCACTATACTCTGGATCTAACCAGTCAAGA',
            'TCTTGACTGGTTAGATCCAGAGTATAGTGATTTGTCCCATAATTTAGCAGGGCATGGGATTTGAGTTTAGGAAGAGTCGATGGGTGTTGCTGATTGAAGTTATTAAGTTAAAATTCTGTTTCACATCTTCACTTAGTTCATTACGCTACT',
            'CATGAAGGAAGAAATTCATCTTCTGTCGAAAAGACAGTAGGAGTATCCAAGAAAGTTCAATGAGGTTTAGATGAAAGCCCAAGTGTGACACTAGTACTCTAACAAGTATGCATGGAGAGTTCATATCAACGTGATGTAAAAACAAATATA',
            'TATATTTGTTTTTACATCACGTTGATATGAACTCTCCATGCATACTTGTTAGAGTACTAGTGTCACACTTGGGCTTTCATCTAAACCTCATTGAACTTTCTTGGATACTCCTACTGTCTTTTCGACAGAAGATGAATTTCTTCCTTCATG',
            'GTCCTCAGCCACAGTTCCCTGCTTGCCTTGGCTCTCCTCCAGCCAATTATCTCCTTCTCATTTGGTACTGCTTGCCCTGGGGTGATTGCTTGAGTGGGTGTGACCTGTGGTTGGTCTCACTGGGTCTGGTTAAAGTCCTGTTGTGTGCTC',
            'GAGCACACAACAGGACTTTAACCAGACCCAGTGAGACCAACCACAGGTCACACCCACTCAAGCAATCACCCCAGGGCAAGCAGTACCAAATGAGAAGGAGATAATTGGCTGGAGGAGAGCCAAGGCAAGCAGGGAACTGTGGCTGAGGAC',
            'GGCCCTGGAACTTGTCTGTCTGTCTGTTGATTTGGAATTGACAGTGGTTGCAGACCTTTAAGTCAAACCTTTCCTCTTGATCCCAATGTGCCCTTCGCTTTCTCTAAAAGGTTCTCCCTTCCTCTTATTTTTCCTTATCCTCTTCTCCAT',
            'ATGGAGAAGAGGATAAGGAAAAATAAGAGGAAGGGAGAACCTTTTAGAGAAAGCGAAGGGCACATTGGGATCAAGAGGAAAGGTTTGACTTAAAGGTCTGCAACCACTGTCAATTCCAAATCAACAGACAGACAGACAAGTTCCAGGGCC'
        ]

        assembly = assemble(
            sequences,
            assembly_max_kmer_size=-1,
            assembly_min_nc_edge_weight=3,
            assembly_min_edge_weight=2,
            assembly_min_match_quality=0.95,
            assembly_min_read_mapping_overlap=None,
            assembly_min_contig_length=150,
            assembly_min_exact_match_to_remap=6,
            assembly_max_paths=20,
            assembly_min_uniq=0.01,
            assembly_max_kmer_strict=False,
            log=self.log)
        self.assertEqual(3, len(assembly))

    def test_assembly_low_center(self):
        sequences = {
            'AGTTGGAGCATCTAAGCATGATTTCTTGGGAGATACGGCCATTGGTGTTTTTTCTCAACCTGTCACTAGAGAGAGATACAGTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTG',
            'CAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGACTGTATCTCTCTCTAGTGACAGGTTGAGAAAAAACACCAATGGCCGTATCTCCCAAGAAATCATGCTTAGATGCTCCAACT',
            'AAGCATGATTTCTTGGGAGATACGGCCATTGGTGTTTTTTCTCAACCTGTCACTAGAGAGAGATACAGTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGG',
            'CCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGACTGTATCTCTCTCTAGTGACAGGTTGAGAAAAAACACCAATGGCCGTATCTCCCAAGAAATCATGCTT',
            'TTGGAGCATCTAAGCATGATTTCTTGGGAGATACGGCCATTGGTGTTTTTTCTCAACCTGTCACTAGAGAGAGATACAGTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAA',
            'TTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGACTGTATCTCTCTCTAGTGACAGGTTGAGAAAAAACACCAATGGCCGTATCTCCCAAGAAATCATGCTTAGATGCTCCAA',
            'CATGATTTCTTGGGAGATACGGCCATTGGTGTTTTTTCTCAACCTGTCACTAGAGAGAGATACAGTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCC',
            'GGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGACTGTATCTCTCTCTAGTGACAGGTTGAGAAAAAACACCAATGGCCGTATCTCCCAAGAAATCATG',
            'CCCTACTACTGAGCCCTTGTCCCAGGGACAAGAAGGAACATGCTGTGTTGCTTGACAGTGAAGTGAACCACCAAGAAATACAAAGAATGTGTGATGAAGAGCCCAGAGGTAAGGCGGAATAGGTAAGGGGATGCCATCTCAGTCTGGCAG',
            'CTGCCAGACTGAGATGGCATCCCCTTACCTATTCCGCCTTACCTCTGGGCTCTTCATCACACATTCTTTGTATTTCTTGGTGGTTCACTTCACTGTCAAGCAACACAGCATGTTCCTTCTTGTCCCTGGGACAAGGGCTCAGTAGTAGGG',
            'CTAAGGCTCATGTTCTTCTTACTGAGCCCTACTACTGAGCCCTTGTCCCAGGGACAAGAAGGAACATGCTGTGTTGCTTGACAGTGAAGTGAACCACCAAGAAATACAAAGAATGTGTGTTGAAGAGCCCAGAGGTAATGCGGCATGGGG',
            'CCCCATGCCGCATTACCTCTGGGCTCTTCAACACACATTCTTTGTATTTCTTGGTGGTTCACTTCACTGTCAAGCAACACAGCATGTTCCTTCTTGTCCCTGGGACAAGGGCTCAGTAGTAGGGCTCAGTAAGAAGAACATGAGCCTTAG',
            'GGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGTCCCGCCTTTGACTGATTCAGACACAGTGAGGATCTTATGGATGAGACAGAGATGACTGGAAGAGGTTGAGTAGGGAACATGTCTTGTCC',
            'GGACAAGACATGTTCCCTACTCAACCTCTTCCAGTCATCTCTGTCTCATCCATAAGATCCTCACTGTGTCTGAATCAGTCAAAGGCGGGACCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCC',
            'GGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTAGGTAACATGTCTTTTCC',
            'GGAAAAGACATGTTACCTACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCC',
            'AGTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGT',
            'ACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGACT',
            'CTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTAGG',
            'CCTACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAG',
            'GCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTA',
            'TACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGC',
            'GGCCCGTCTGTGTAGGATGCAGACACAGTGAGGATCATATGGAGGAGACAGAGATGACTGGAAGAGGTTGAGGAGGGGACATGTCTGTGCCAGCTTTCCTAATGCTTCATCATCGGAAGAGCCAGGGGTATAGAAAATGGAATTAAAAGC',
            'GCTTTTAATTCCATTTTCTATACCCCTGGCTCTTCCGATGATGAAGCATTAGGAAAGCTGGCACAGACATGTCCCCTCCTCAACCTCTTCCAGTCATCTCTGTCTCCTCCATATGATCCTCACTGTGTCTGCATCCTACACAGACGGGCC',
            'CTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTAGGGAACATGTCT',
            'AGACATGTTCCCTACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAG',
            'GTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTT',
            'AACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGAC',
            'AAGACTTGTTTTTCTCATCATAACACAGTCCAGTATTTATGTTCTGAAATATCCATGTGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGGTGACTGGAAGAGGTTGAGTAGGGAACATGTCTGTTCCAG',
            'CTGGAACAGACATGTTCCCTACTCAACCTCTTCCAGTCACCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCACATGGATATTTCAGAACATAAATACTGGACTGTGTTATGATGAGAAAAACAAGTCTT',
            'TTTCCTAGGGGAAGACTTGTTTGTCCCAGCATAACACAGTCCAGTTTGTATGGTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTAGGGACCAT',
            'ATGGTCCCTACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGACCATACAAACTGGACTGTGTTATGCTGGGACAAACAAGTCTTCCCCTAGGAAA',
            'GTTTTCCTAGGGGAAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTAGGGAAC',
            'GTTCCCTACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTTCCCCTAGGAAAAC',
            'AAGACTTGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCGTTGACTGATGCAGACACAGTGAGGATCTTATGGAAGAGACAGAGATGACTGGAAGAGGTTGAGTAGGGAACATGTCTGTTCCAG',
            'CTGGAACAGACATGTTCCCTACTCAACCTCTTCCAGTCATCTCTGTCTCTTCCATAAGATCCTCACTGTGTCTGCATCAGTCAACGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACAAGTCTT',
            'CTGGACTGTGTTATGATCGGAAAAACAGGTCAACCCCTAGGAAAGCGGTGGCTTGCCGGTACCGCCCTCTACTGACATGCTGAGCAGAAACACCAATGCCCCTACCCCCCACGCAGTCATGCTTAGCTGCTCCCACTCCTTTCCGCCCTT',
            'AAGGGCGGAAAGGAGTGGGAGCAGCTAAGCATGACTGCGTGGGGGGTAGGGGCATTGGTGTTTCTGCTCAGCATGTCAGTAGAGGGCGGTACCGGCAAGCCACCGCTTTCCTAGGGGTTGACCTGTTTTTCCGATCATAACACAGTCCAG',
            'TAGGTTTCATCATGCTTAGAATTTGATTATCTAGCACCCTGTCATTCTCAATCCATTATCCTGATTTCTTCTCTATAGCACTTATCACTTCACAACATTTTATTTTATATGAATTTGTTTATCTGTTATATAGATGCCCCACTGAAATAT',
            'ATATTTCAGTGGGGCATCTATATAACAGATAAACAAATTCATATAAAATAAAATGTTGTGAAGTGATAAGTGCTATAGAGAAGAAATCAGGATAATGGATTGAGAATGACAGGGTGCTAGATAATCAAATTCTAAGCATGATGAAACCTA',
            'CGGCCATTGGTGTTTTTTCTCAACCTGTCACTAGAGAGAGATACAGTCAAGCCTCCGTTTTCCTAGGGGAAGACTTGTTTTTCTACTCTGGGTGGAGAAAAATTATTAAAAAGTCTTGATTATCAGAATTTGGCCCCTAGTTTTTCTCAT',
            'ATGAGAAAAACTAGGGGCCAAATTCTGATAATCAAGACTTTTTAATAATTTTTCTCCACCCAGAGTAGAAAAACAAGTCTTCCCCTAGGAAAACGGAGGCTTGACTGTATCTCTCTCTAGTGACAGGTTGAGAAAAAACACCAATGGCCG',
            'CAGAACCTCAAAATACTGCCTGGTACCAATAAATATTTGTTAGGTAAGTAAAGCTGATCATTGTATTAATCATTTCACTTATATTTATGGACTGATCATGGTAGTCAGGCCCTGAGAAATAAAACAGAGCTCATAACCTGGCGGTTCGAA',
            'TTCGAACCGCCAGGTTATGAGCTCTGTTTTATTTCTCAGGGCCTGACTACCATGATCAGTCCATAAATATAAGTGAAATGATTAATACAATGATCAGCTTTACTTACCTAACAAATATTTATTGGTACCAGGCAGTATTTTGAGGTTCTG',
            'TAGAGTTGGGTCTTAAAAGATGAAGGAAGGGGGCACACTGGGTCCCAGTAAGACAAGAAGAGACTATGTGCTGGACATGGCGCTCAGTGATTTACATGTATACAATGCCTCATTTAGTACTCAGAAGAACTGGAAGAAGATGTATTATTA',
            'TAATAATACATCTTCTTCCAGTTCTTCTGAGTACTAAATGAGGCATTGTATACATGTAAATCACTGAGCGCCATGTCCAGCACATAGTCTCTTCTTGTCTTACTGGGACCCAGTGTGCCCCCTTCCTTCATCTTTTAAGACCCAACTCTA',
            'TTTTCTACTCTGGGTGGAGAAAAATTATTAAAAAGTCTTGATTATCAGAATTTGGCCCCTAGTTTTTCTCATCATAACACAGTCCAGTATGTATGTTCTGAAATATCCATGGGCCCGCCTTTGACTGATGCAGACACAGTGAGGATCTTA',
            'TAAGATCCTCACTGTGTCTGCATCAGTCAAAGGCGGGCCCATGGATATTTCAGAACATACATACTGGACTGTGTTATGATGAGAAAAACTAGGGGCCAAATTCTGATAATCAAGACTTTTTAATAATTTTTCTCCACCCAGAGTAGAAAA'
        }
        for seq in sequences:
            assert reverse_complement(seq) in sequences
        assemblies = assemble(
            sequences,
            assembly_max_kmer_size=-1,
            assembly_min_nc_edge_weight=2,
            assembly_min_edge_weight=1,
            assembly_min_match_quality=0.95,
            assembly_min_read_mapping_overlap=None,
            assembly_min_contig_length=None,
            assembly_min_exact_match_to_remap=6,
            assembly_max_paths=20,
            assembly_min_uniq=0.01,
            assembly_max_kmer_strict=True,
            log=self.log)
        for assembly in assemblies:
            print(assembly.seq)
        self.assertEqual(2, len(assemblies))

    def test_low_evidence(self):
        seqs = [
            'AGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAAGCCATTCATTCTGTGTTTTTTTATATAGCAGTTATTATTTTAAAG',
            'TCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAAGCCATTCATTCTGTGTTTTTTTATATAGCAGTTATTATTTTAAAGCAGTTATTATTCTTATATT',
            'GAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAAGCCATTCATTCTGTGTCTTTTTATATAGCAGTTATTATTTTAAAGCAGTTATTATTCTTATATTTCTTATTTTT',
            'GCCTTCATGAGTAGGATTATTGCCCATTTTAAAAAAAGGTCCATGAGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAA',
            'CTTCATGAGTAGGATTATTGCCCATTTTAAAAAAAGGTCCATGAGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAAGC',
            'AGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAAGCCATTCATTCTGTGTTTTTTTATAGAGCAGTTATTATTTTAAAG',
            'GCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACTGTGAGAAATACATTTCTGTTCACATAAGCCATTCATTCTGTGTTTTTTTATATAGCAGTTATTATTTTAAAGC',
            'GGTATTAGGAAGTGAGACAATTAGGAGGTAATTAGGTCATGAGAGTGGAGCCTTCATGAGTAGGATTATTGCCCATTTTAAAAAAAGGTCCATGAGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTT',
            'TAGGAAGTGAGACAATTAGGAGGTAATTAGGTCATGAGAGTGGAGCCTTCATGAGTAGGATTATTGCCCATTTTAAAAAAAGGTCCATGAGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGAT',
            'AGGAGGTAATTAGGTCATGAGAGTGGAGCCTTCATGAGTAGGATTATTGCCCATTTTAAAAAAAGGTCCATGAGCACTTTCTTGCCTTTTATCTATCATCTGAGGACACATGCTGGGCACTCTGATTTCAGATTTCCATCCTCCAGAACT',
            'AAAGTTGGTTTTTCACAAAATTGGGATTGAAATTACAGCCACCATTCGATGGTATTAGGAAGGGAGGCAATTAGGAGGTACTTGGGTCAGGAGAGGGGAGCCTGCATGAGTAGGATTAATGGCCATTTTAAAAAACGATCAATGTGCACG'
        ]
        sequences = set(seqs)
        for seq in seqs:
            sequences.add(reverse_complement(seq))
        print('assembly size', len(sequences))
        assemblies = assemble(
            sequences,
            assembly_max_kmer_size=-1,
            assembly_min_nc_edge_weight=2,
            assembly_min_edge_weight=1,
            assembly_min_match_quality=0.95,
            assembly_min_read_mapping_overlap=150 * 0.9,
            assembly_min_contig_length=150,
            assembly_min_exact_match_to_remap=6,
            assembly_max_paths=20,
            assembly_min_uniq=0.01,
            assembly_max_kmer_strict=True,
            log=self.log)
        for assembly in assemblies:
            print(assembly.seq, assembly.remap_score())
        self.assertEqual(2, len(assemblies))
