import networkx as nx
import itertools
import warnings
from .bam import cigar as cigar_tools
from .bam.read import nsb_align
from .constants import reverse_complement


class Contig:
    """
    """
    def __init__(self, sequence, score):
        self.seq = sequence
        self.remapped_sequences = {}
        self.score = score
        self.alignments = []
        self.input_reads = set()
        self.strand_specific = False

    def __hash__(self):
        return hash(self.seq)

    def add_mapped_sequence(self, read, multimap=1):
        rc = reverse_complement(read)
        if rc in self.remapped_sequences:
            self.remapped_sequences[rc] = min(self.remapped_sequences.get(rc, 1), 1 / multimap)
        else:
            self.remapped_sequences[read] = min(self.remapped_sequences.get(read, 1), 1 / multimap)

    def remap_score(self):
        return sum(self.remapped_sequences.values())


class DeBruijnGraph(nx.DiGraph):
    """
    wrapper for a basic digraph
    enforces edge weights
    """
    def get_edge_freq(self, n1, n2):
        if not self.has_edge(n1, n2):
            raise KeyError('missing edge', n1, n2)
        data = self.get_edge_data(n1, n2)
        return data['freq']

    def add_edge(self, n1, n2, freq=1):
        if self.has_edge(n1, n2):
            data = self.get_edge_data(n1, n2)
            freq += data['freq']
        nx.DiGraph.add_edge(self, n1, n2, freq=freq)

    def trim_tails_by_freq(self, min_weight):
        """
        for any paths where all edges are lower than the minimum weight trim

        Args:
            min_weight (int): the minimum weight for an edge to be retained
        """
        for n in list(self.nodes()):
            if not self.has_node(n):
                continue
            # follow until the path forks or we run out of low weigh edges
            curr = n
            while self.degree(curr) == 1:
                if self.out_degree(curr) == 1:
                    curr, other, data = self.out_edges(curr, data=True)[0]
                    if data['freq'] < min_weight:
                        self.remove_node(curr)
                        curr = other
                    else:
                        break
                elif self.in_degree(curr) == 1:
                    other, curr, data = self.in_edges(curr, data=True)[0]
                    if data['freq'] < min_weight:
                        self.remove_node(curr)
                        curr = other
                    else:
                        break
                else:
                    break
        for n in list(self.nodes()):
            if not self.has_node(n):
                continue
            if self.degree(n) == 0:
                self.remove_node(n)

    def trim_noncutting_edges_by_freq(self, min_weight):
        """
        trim any low weight edges where another path exists between the source and target
        of higher weight
        """
        current_edges = list(self.edges(data=True))
        for src, tgt, data in sorted(current_edges, key=lambda x: (x[2]['freq'], x[0], x[1])):
            try:
                self.remove_edge(src, tgt)
                if not nx.has_path(self, src, tgt):  # guaranteed to be higher or equal weight
                    self.add_edge(src, tgt, **data)
            except KeyError:
                pass


def digraph_connected_components(graph):
    """
    the networkx module does not support deriving connected
    components from digraphs (only simple graphs)
    this function assumes that connection != reachable
    this means there is no difference between connected components
    in a simple graph and a digraph

    Args:
        graph (networkx.DiGraph): the input graph to gather components from

    Returns:
        :class:`list` of :class:`list`: returns a list of compnents which are lists of node names
    """
    g = nx.Graph()
    for src, tgt in graph.edges():
        g.add_edge(src, tgt)
    for n in graph.nodes():
        g.add_node(n)
    return nx.connected_components(g)


def assemble(
    sequences,
    assembly_max_kmer_size=None,
    assembly_min_edge_weight=3,
    assembly_min_match_quality=0.95,
    assembly_min_read_mapping_overlap=None,
    assembly_min_contig_length=None,
    assembly_min_consec_match_remap=3,
    assembly_max_paths=20,
    assembly_max_kmer_strict=False,
    log=lambda *x: None
):
    """
    for a set of sequences creates a DeBruijnGraph
    simplifies trailing and leading paths where edges fall
    below a weight threshold and the return all possible unitigs/contigs

    Args:
        sequences (:class:`list` of :class:`str`): a list of strings/sequences to assemble
        assembly_max_kmer_size (int): the size of the kmer to use
        assembly_min_edge_weight (int): see :term:`assembly_min_edge_weight`
        assembly_min_match_quality (float): percent match for re-aligned reads to contigs
        assembly_min_read_mapping_overlap (int): the minimum amount of overlap required when aligning reads to contigs
        assembly_max_paths (int): see :term:`assembly_max_paths`

    Returns:
        :class:`list` of :class:`Contig`: a list of putative contigs
    """
    if len(sequences) == 0:
        return []
    min_seq = min([len(s) for s in sequences])
    if assembly_max_kmer_size is None:
        temp = int(min_seq * 0.75)
        if temp < 10:
            assembly_max_kmer_size = min(min_seq, 10)
        else:
            assembly_max_kmer_size = temp
    elif assembly_max_kmer_size > min_seq:
        if not assembly_max_kmer_strict:
            assembly_max_kmer_size = min_seq
            warnings.warn(
                'cannot specify a kmer size larger than one of the input sequences. reset to {0}'.format(min_seq))
    assembly_min_read_mapping_overlap = assembly_max_kmer_size if assembly_min_read_mapping_overlap is None else \
        assembly_min_read_mapping_overlap
    assembly_min_contig_length = min_seq + 1 if assembly_min_contig_length is None else assembly_min_contig_length
    assembly = DeBruijnGraph()
    log('hashing kmers')
    for s in sequences:
        if len(s) < assembly_max_kmer_size:
            continue
        for kmer in kmers(s, assembly_max_kmer_size):
            l = kmer[:-1]
            r = kmer[1:]
            assembly.add_edge(l, r)
    if not nx.is_directed_acyclic_graph(assembly):
        NotImplementedError('assembly not supported for cyclic graphs')

    # now just work with connected components
    assembly.trim_noncutting_edges_by_freq(assembly_min_edge_weight)
    # trim all paths from sources or to sinks where the edge weight is low
    assembly.trim_tails_by_freq(assembly_min_edge_weight)
    path_scores = {}  # path_str => score_int

    for component in digraph_connected_components(assembly):
        # since now we know it's a tree, the assemblies will all be ltd to
        # simple paths
        sources = set()
        sinks = set()
        for node in component:
            if assembly.degree(node) == 0:  # ignore singlets
                pass
            elif assembly.in_degree(node) == 0:
                sources.add(node)
            elif assembly.out_degree(node) == 0:
                sinks.add(node)
        if len(sources) * len(sinks) > assembly_max_paths:
            continue

        # if the assembly has too many sinks/sources we'll need to clean it
        # we can do this by removing all current sources/sinks
        while len(sources) * len(sinks) > assembly_max_paths:
            warnings.warn(
                'source/sink combinations: {} from {} nodes'.format(len(sources) * len(sinks), len(component)))
            for s in sources | sinks:
                assembly.remove_node(s)
                component.remove(s)
            sources = set()
            sinks = set()
            for node in component:
                if assembly.degree(node) == 0:  # ignore singlets
                    pass
                elif assembly.in_degree(node) == 0:
                    sources.add(node)
                elif assembly.out_degree(node) == 0:
                    sinks.add(node)
        for source, sink in itertools.product(sources, sinks):
            for path in nx.all_simple_paths(assembly, source, sink):
                s = path[0] + ''.join([p[-1] for p in path[1:]])
                score = 0
                for i in range(0, len(path) - 1):
                    score += assembly.get_edge_freq(path[i], path[i + 1])
                path_scores[s] = max(path_scores.get(s, 0), score)
    # now map the contigs to the possible input sequences
    contigs = {}
    for seq, score in list(path_scores.items()):
        if seq not in sequences and len(seq) >= assembly_min_contig_length:
            contigs[seq] = Contig(seq, score)

    contig_exact = {}
    for contig in contigs:
        contig_exact[contig] = set(kmers(contig, assembly_min_consec_match_remap))
    # remap the input reads
    filtered_contigs = {}
    for seq, contig in sorted(contigs.items()):
        rseq = reverse_complement(seq)
        if seq not in filtered_contigs and rseq not in filtered_contigs:
            filtered_contigs[seq] = contig
    
    contigs = list(filtered_contigs.values())

    log('remapping reads to {} contigs'.format(len(contigs)))

    for input_seq in sequences:
        maps_to = {}  # contig, score
        exact_match_kmers = set(kmers(input_seq, assembly_min_consec_match_remap))
        for contig in contigs:
            if len(exact_match_kmers & contig_exact[contig.seq]) == 0:
                continue
            a = nsb_align(
                contig.seq,
                input_seq,
                min_overlap_percent=assembly_min_read_mapping_overlap / len(contig.seq),
                min_match=assembly_min_match_quality
            )
            if len(a) != 1:
                continue
            if cigar_tools.match_percent(a[0].cigar) < assembly_min_match_quality:
                continue
            maps_to[contig] = a[0]
        for contig, read in maps_to.items():
            contig.add_mapped_sequence(read, len(maps_to.keys()))
    log('assemblies complete')
    return contigs


def kmers(s, size):
    """
    for a sequence, compute and return a list of all kmers of a specified size

    Args:
        s (str): the input sequence
        size (int): the size of the kmers

    Returns:
        :class:`list` of :class:`str`: the list of kmers

    Example:
        >>> kmers('abcdef', 2)
        ['ab', 'bc', 'cd', 'de', 'ef']
    """
    kmers = []
    for i in range(0, len(s)):
        if i + size > len(s):
            break
        kmers.append(s[i:i + size])
    return kmers