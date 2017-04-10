from argparse import Namespace, ArgumentError
from configparser import ConfigParser, ExtendedInterpolation
import os
import TSV
import re
import pysam
from . import __version__
from .constants import PROTOCOL
from .util import devnull
from .validate.constants import DEFAULTS as VALIDATION_DEFAULTS
from .pairing.constants import DEFAULTS as PAIRING_DEFAULTS
from .cluster.constants import DEFAULTS as CLUSTER_DEFAULTS
from .annotate.constants import DEFAULTS as ANNOTATION_DEFAULTS
from .illustrate.constants import DEFAULTS as ILLUSTRATION_DEFAULTS
from .bam.stats import compute_genome_bam_stats, compute_transcriptome_bam_stats

ENV_VAR_PREFIX = 'MAVIS_'


def cast(value, cast_func):
    if cast_func == bool:
        value = TSV.tsv_boolean(value)
    else:
        value = cast_func(value)
    return value


class LibraryConfig:
    def __init__(
        self, library, protocol, bam_file, inputs, read_length, median_fragment_size, stdev_fragment_size, stranded_bam, 
        **kwargs
    ):
        self.library = library
        self.protocol = PROTOCOL.enforce(protocol)
        self.bam_file = bam_file
        self.read_length = int(read_length)
        self.median_fragment_size = int(median_fragment_size)
        self.stdev_fragment_size = int(stdev_fragment_size)
        self.stranded_bam = cast(stranded_bam, bool)
        try:
            self.inputs = [f for f in re.split('[;\s]+', inputs) if f]
        except TypeError:
            self.inputs = inputs

        acceptable = {}
        acceptable.update(VALIDATION_DEFAULTS.__dict__)

        for attr, value in kwargs.items():
            if attr == 'assembly_max_kmer_size' and value in [None, 'None', '']:  # special case
                setattr(self, attr, None)
            else:
                setattr(self, attr, cast(value, type(acceptable[attr])))

    def flatten(self):
        result = {}
        result.update(self.__dict__)
        result['inputs'] = '\n'.join(result['inputs'])
        return result
    
    @classmethod
    def build(
        self, library, protocol, bam_file, inputs, 
        annotations=None, 
        log=devnull, 
        distribution_fraction=0.98, 
        sample_cap=3000,
        sample_bin_size=1000,
        sample_size=500,
        best_transcripts_only=True,
        **kwargs
    ):
        PROTOCOL.enforce(protocol)
        
        if protocol == PROTOCOL.TRANS and annotations is None:
            raise AttributeError(
                'missing required attribute: annotations. Annotations must be given for transcriptomes')
        try:
            bam = pysam.AlignmentFile(bam_file, 'rb')
            bamstats = None
            if protocol == PROTOCOL.TRANS:
                bamstats = compute_transcriptome_bam_stats(
                    bam, 
                    annotations=annotations, 
                    sample_size=sample_size,
                    sample_cap=sample_cap, 
                    distribution_fraction=distribution_fraction,
                    log=log
                )
            elif protocol == PROTOCOL.GENOME:
                bamstats = compute_genome_bam_stats(
                    bam, 
                    sample_size=sample_size,
                    sample_bin_size=sample_bin_size, 
                    sample_cap=sample_cap, 
                    distribution_fraction=distribution_fraction,
                    log=log
                )
            else:
                raise ValueError('unrecognized value for protocol', protocol)
            log(
                'library:', library, protocol,
                'median', bamstats.median_fragment_size, 
                'stdev', bamstats.stdev_fragment_size, 
                'read length', bamstats.read_length)

            return LibraryConfig(
                library=library, protocol=protocol, bam_file=bam_file, inputs=inputs, 
                median_fragment_size=bamstats.median_fragment_size,
                stdev_fragment_size=bamstats.stdev_fragment_size,
                read_length=bamstats.read_length,
                **kwargs
            )
        finally:
            try:
                bam.close()
            except AttributeError:
                pass


class JobSchedulingConfig:
    def __init__(self, validate_memory_gb=12, default_memory_gb=6, queue='transabyss.q'):
        self.validate_memory_gb = validate_memory_gb
        self.default_memory_gb = default_memory_gb
        self.queue = queue
    
    def flatten(self):
        result = {}
        result.update(self.__dict__)
        return result


class ReferenceFilesConfig:

    def __init__(
        self, 
        annotations=None, 
        reference_genome=None, 
        template_metadata=None, 
        masking=None, 
        blat_2bit_reference=None, 
        low_memory=False
    ):
        self.annotations = annotations or os.environ.get(ENV_VAR_PREFIX + 'ANNOTATIONS', None)
        self.reference_genome = reference_genome or os.environ.get(ENV_VAR_PREFIX + 'REFERENCE_GENOME', None)
        self.template_metadata = template_metadata or os.environ.get(ENV_VAR_PREFIX + 'TEMPLATE_METADATA', None)
        self.masking = masking or os.environ.get(ENV_VAR_PREFIX + 'MASKING', None)
        self.low_memory = low_memory or os.environ.get(ENV_VAR_PREFIX + 'LOW_MEMORY', None)
        self.blat_2bit_reference = blat_2bit_reference or os.environ.get(ENV_VAR_PREFIX + 'BLAT_2BIT_REFERENCE', None)

    def flatten(self):
        result = {}
        result.update(self.__dict__)
        return result


class PairingConfig:

    def __init__(
        self, 
        split_call_distance=PAIRING_DEFAULTS.split_call_distance, 
        contig_call_distance=PAIRING_DEFAULTS.contig_call_distance,
        flanking_call_distance=PAIRING_DEFAULTS.flanking_call_distance,
        max_proximity=CLUSTER_DEFAULTS.max_proximity,
        low_memory=False
    ):
        self.split_call_distance = int(split_call_distance)
        self.contig_call_distance = int(contig_call_distance)
        self.flanking_call_distance = int(flanking_call_distance)

    def flatten(self):
        result = {}
        result.update(self.__dict__)
        return result


def write_config(filename, include_defaults=False, libraries=[], log=devnull):
    config = {}
 
    config['reference'] = ReferenceFilesConfig().flatten()
    
    if libraries:
        for lib in libraries:
            config[lib.library] = lib.flatten()

    if include_defaults:
        config['qsub'] = JobSchedulingConfig().flatten()
        config['illustrate'] = {}
        config['illustrate'].update(ILLUSTRATION_DEFAULTS.__dict__)
        config['validation'] = {}
        config['validation'].update(VALIDATION_DEFAULTS.__dict__)
        config['cluster'] = {}
        config['cluster'].update(CLUSTER_DEFAULTS.__dict__)
        
        for sec in ['qsub', 'illustrate', 'validation', 'cluster']:
            for tag, val in config[sec].items():
                env = ENV_VAR_PREFIX + tag.upper()
                config[sec][tag] = os.environ.get(env, None) or val

    for sec in config:
        for tag, value in config[sec].items():
            if '_regex_' in tag:
                config[sec][tag] = re.sub('\$', '$$', config[sec][tag])
            else:
                config[sec][tag] = str(value)

    conf = ConfigParser()
    for sec in config:
        conf[sec] = {}
        for tag, val in config[sec].items():
            conf[sec][tag] = val

    with open(filename, 'w') as configfile:
        log('writing:', filename)
        conf.write(configfile)


def validate_and_cast_section(section, defaults):
    d = {}
    for attr, value in section.items():
        if attr not in defaults:
            raise KeyError('tag not recognized', attr)
        else:
            d[attr] = cast(value, type(defaults[attr]))
    return d


def read_config(filepath):
    """
    reads the configuration settings from the configuration file

    Args:
        filepath (str): path to the input configuration file

    Returns:
        class:`list` of :class:`Namespace`: namespace arguments for each library
    """
    parser = ConfigParser(interpolation=ExtendedInterpolation())
    parser.read(filepath)

    # get the library sections and add the default settings
    library_sections = []
    for sec in parser.sections():
        if sec not in ['validation', 'reference', 'qsub', 'illustrate', 'annotation', 'cluster']:
            library_sections.append(sec)

    job_sched = JobSchedulingConfig(**(parser['qsub'] if 'qsub' in parser else {}))
    ref = ReferenceFilesConfig(**(parser['reference'] if 'reference' in parser else {}))
    pairing = PairingConfig(**(parser['pairing'] if 'pairing' in parser else {}))
    
    global_args = {}
    global_args.update(job_sched.flatten())
    global_args.update(ref.flatten())
    global_args.update(ILLUSTRATION_DEFAULTS.__dict__)
    global_args.update(pairing.flatten())
    global_args.update(ANNOTATION_DEFAULTS.__dict__)
    global_args.update(CLUSTER_DEFAULTS.__dict__)
    try:
        global_args.update(validate_and_cast_section(parser['illustrate'], ILLUSTRATION_DEFAULTS))
    except KeyError:
        pass

    try:
        global_args.update(validate_and_cast_section(parser['annotation'], ANNOTATION_DEFAULTS))
    except KeyError:
        pass
    
    try:
        global_args.update(validate_and_cast_section(parser['cluster'], CLUSTER_DEFAULTS))
    except KeyError:
        pass



    args = {}
    args.update(VALIDATION_DEFAULTS.__dict__)
    try:
        args.update(parser['validation'] if 'validation' in parser else {})
    except KeyError:
        pass
    
    # check that the reference files all exist
    for attr, fname in parser['reference'].items():
        if not os.path.exists(fname) and attr != 'low_memory':
            raise KeyError(attr, 'file at', fname, 'does not exist')
        global_args[attr] = fname
    
    sections = []
    for sec in library_sections:
        d = {}
        d.update(parser[sec])
        d.update(args)

        # now try building the LibraryConfig object
        try:
            lc = LibraryConfig(**d)
            sections.append(lc)
            continue
        except TypeError as terr:  # missing required argument
            try:
                lc = LibraryConfig.build(**d)
                sections.append(lc)
            except Exception as err:
                raise UserWarning('could not build configuration file', terr, err)
    if len(library_sections) < 1:
        raise UserWarning('configuration file must have 1 or more library sections')

    return Namespace(**global_args), sections


def add_semi_optional_argument(argname, success_parser, failure_parser, help_msg=''):
    """
    for an argument tries to get the argument default from the environment variable
    """
    env_name = ENV_VAR_PREFIX + argname.upper()
    help_msg += ' The default for this argument is configured by setting the environment variable {}'.format(env_name)
    if os.environ.get(env_name, None):
        success_parser.add_argument('--{}'.format(argname), required=False, default=os.environ[env_name], help=help_msg)
    else:
        failure_parser.add_argument('--{}'.format(argname), required=True, help=help_msg)


def get_env_variable(arg, default, cast_type=None):
    """
    Args:
        arg (str): the argument/variable name
    Returns:
        the setting from the environment variable if given, otherwise the default value
    """
    if cast_type is None:
        cast_type = type(default)
    name = ENV_VAR_PREFIX + arg.upper()
    result = os.environ.get(name, None)
    if result is not None:
        return cast(result, cast_type)
    else:
        return default


def augment_parser(parser, optparser, arguments):
    try:
        optparser.add_argument('-h', '--help', action='help', help='show this help message and exit')
        optparser.add_argument(
            '-v', '--version', action='version', version='%(prog)s version ' + __version__,
            help='Outputs the version number')
    except ArgumentError:
        pass
    
    for arg in arguments:
        if arg == 'annotations':
            add_semi_optional_argument(
                arg, optparser, parser, 'Path to the reference annotations of genes, transcript, exons, domains, etc.')
        elif arg == 'reference_genome':
            add_semi_optional_argument(arg, optparser, parser, 'Path to the human reference genome fasta file.')
            optparser.add_argument(
                '--low_memory', default=get_env_variable('low_memory', False), type=TSV.tsv_boolean,
                help='if true defaults to indexing vs loading the reference genome')
        elif arg == 'template_metadata':
            add_semi_optional_argument(arg, optparser, parser, 'File containing the cytoband template information.')
        elif arg == 'masking':
            add_semi_optional_argument(arg, optparser, parser)
        elif arg == 'blat_2bit_reference':
            add_semi_optional_argument(
                arg, optparser, parser, 'path to the 2bit reference file used for blatting contig sequences.')
        elif arg == 'config':
            parser.add_argument('config', 'path to the config file')
        elif arg == 'stranded_bam':
            optparser.add_argument(
                '--stranded_bam', required=True, type=TSV.tsv_boolean, 
                help='indicates that the input bam file is strand specific')
        elif arg == 'force_overwrite':
            optparser.add_argument(
                '-f', '--force_overwrite', default=get_env_variable(arg, False), type=TSV.tsv_boolean,
                help='set flag to overwrite existing reviewed files')
        elif arg == 'output_svgs':
            optparser.add_argument(
                '--output_svgs', default=get_env_variable(arg, True), type=TSV.tsv_boolean,
                help='set flag to suppress svg drawings of putative annotations')
        elif arg == 'min_orf_size':
            optparser.add_argument(
                '--min_orf_size', default=get_env_variable(arg, ANNOTATION_DEFAULTS.min_orf_size), type=int,
                help='minimum sfize for putative ORFs')
        elif arg == 'max_orf_cap':
            optparser.add_argument(
                '--max_orf_cap', default=get_env_variable(arg, ANNOTATION_DEFAULTS.max_orf_cap), type=int,
                help='keep the n longest orfs')
        elif arg == 'min_domain_mapping_match':
            optparser.add_argument(
                '--min_domain_mapping_match',
                default=get_env_variable(arg, ANNOTATION_DEFAULTS.min_domain_mapping_match), type=float,
                help='minimum percent match for the domain to be considered aligned')
        elif arg == 'max_files':
            optparser.add_argument(
                '--max_files', default=get_env_variable(arg, CLUSTER_DEFAULTS.max_files), type=int, dest='max_files',
                help='defines the maximum number of files that can be created')
        elif arg == 'min_clusters_per_file':
            optparser.add_argument(
                '--min_clusters_per_file', default=get_env_variable(arg, CLUSTER_DEFAULTS.min_clusters_per_file),
                type=int, help='defines the minimum number of clusters per file')
        elif arg == 'cluster_radius':
            optparser.add_argument(
                '-r', '--cluster_radius', help='radius to use in clustering',
                default=get_env_variable(arg, CLUSTER_DEFAULTS.cluster_radius), type=int)
        elif arg == 'cluster_clique_size':
            optparser.add_argument(
                '-k', '--cluster_clique_size', default=get_env_variable(arg, CLUSTER_DEFAULTS.cluster_clique_size),
                type=int, help='parameter used for computing cliques, smaller is faster, above 20 will be slow')
        elif arg == 'uninformative_filter':
            optparser.add_argument(
                '--uninformative_filter', default=get_env_variable(arg, CLUSTER_DEFAULTS.uninformative_filter),
                type=TSV.tsv_boolean,
                help='If flag is False then the clusters will not be filtered based on lack of annotation'
            )
        elif arg == 'split_call_distance':
            optparser.add_argument(
                '--split_call_distance', default=get_env_variable(arg, PAIRING_DEFAULTS.split_call_distance), type=int,
                help='distance allowed between breakpoint calls when pairing from split read (and higher) resolution calls')
        elif arg == 'contig_call_distance':
            optparser.add_argument(
                '--contig_call_distance', default=get_env_variable(arg, PAIRING_DEFAULTS.contig_call_distance), type=int,
                help='distance allowed between breakpoint calls when pairing from contig (and higher) resolution calls')
        elif arg == 'flanking_call_distance':
            optparser.add_argument(
            '--flanking_call_distance',
            default=get_env_variable(arg, PAIRING_DEFAULTS.flanking_call_distance), type=int,
            help='distance allowed between breakpoint calls when pairing from contig (and higher) resolution calls')
        elif arg in VALIDATION_DEFAULTS:
            value = VALIDATION_DEFAULTS[arg]
            vtype = type(value) if type(value) != bool else TSV.tsv_boolean
            optparser.add_argument(
                '--{}'.format(arg), default=get_env_variable(arg, value), type=vtype, help='see user manual for desc')
        elif arg in ILLUSTRATION_DEFAULTS:
            value = ILLUSTRATION_DEFAULTS[arg]
            vtype = type(value) if type(value) != bool else TSV.tsv_boolean
            optparser.add_argument(
                '--{}'.format(arg), default=get_env_variable(arg, value), type=vtype, help='see user manual for desc')
        elif arg == 'max_proximity':
            optparser.add_argument(
                '--{}'.format(arg), default=get_env_variable(arg, CLUSTER_DEFAULTS[arg]), type=int, 
                help='maximum distance away from an annotation before the uninformative filter is applied or the'
                'annotation is not considered for a given event')
        elif arg == 'bam_file':
            parser.add_argument('--bam_file', help='path to the input bam file', required=True)
        elif arg == 'read_length':
            parser.add_argument(
                '--read_length', type=int, help='the length of the reads in the bam file', required=True)
        elif arg == 'stdev_fragment_size':
            parser.add_argument(
                '--stdev_fragment_size', type=int, help='expected standard deviation in insert sizes', required=True)
        elif arg == 'median_fragment_size':
            parser.add_argument(
                '--median_fragment_size', type=int, help='median inset size for pairs in the bam file', required=True)
        elif arg == 'library':
            parser.add_argument('--library', help='library name', required=True)
        elif arg == 'protocol':
            parser.add_argument('--protocol', choices=PROTOCOL.values(), help='library protocol', required=True)
        else:
            raise KeyError('invalid argument', arg)
