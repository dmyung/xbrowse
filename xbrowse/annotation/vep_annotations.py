import platform
import os
import re
import tempfile

import sh

from xbrowse import vcf_stuff
from xbrowse.annotation import utils as annotation_utils


# VEP adds a bunch of annotations; we ignore everything besides the ones on this white list
SAVED_VEP_FIELDS = {
    'allele',
    'amino_acids',
    'codons',
    'consequence',
    'domains',
    'ensp',
    'hgvsp'
    'existing_variation',
    'feature',
    'gene',
    'motif_name',
    'motif_pos',
    'polyphen',
    'protein_position',
    'pubmed',
    'sift'
}


class HackedVEPAnnotator():
    """
    xBrowse depends on VEP annotations -
    This class is a wrapper around VEP that provides a pythonic interface to VEP annotations
    It should just call the REST API, but that is slow, so it spins out subprocesses :(
    """
    def __init__(self, vep_perl_path, vep_fasta_path, vep_cache_dir, vep_batch_size=20000, human_ancestor_fa=None):
        self._vep_perl_path = vep_perl_path
        self._vep_fasta_path = vep_fasta_path
        self._vep_cache_dir = vep_cache_dir
        self._vep_batch_size = vep_batch_size
        self._human_ancestor_fa = human_ancestor_fa

    def _run_vep(self, input_vcf, output_vcf):
        """
        Just run VEP to the xbrowse configurations
        """
        vep_command = [
            self._vep_perl_path,
            "--offline",
            "--protein",
            "--vcf",
            "--force_overwrite",
            "--hgvs",
            "--fasta", self._vep_fasta_path,
            #"--everything",
            "--dir", self._vep_cache_dir,
            "-i", input_vcf,
            "-o", output_vcf,
        ]
        # if self._human_ancestor_fa is not None:
        #     vep_command += [
        #         "--plugin",
        #         "LoF,human_ancestor_fa:{}".format(self._human_ancestor_fa),
        #     ]

        if platform.system() == 'Darwin':
            vep_command.append("--compress")
            vep_command.append("gunzip -c")

        sh.perl(vep_command)

    def get_vep_annotations_for_variants(self, variant_t_list):
        """
        Load annotations for a set of variants
        - write these annotations to a temporary vcf file
        - runs VEP on the temp VCF file
        - loads newly annotated VCF to annotator
        Obviously there should be a better way to do this, but this is what we have for now
        """

        def process_batch(variant_t_batch):

            vep_input_file_path = tempfile.mkstemp()[1]
            vep_output_file_path = tempfile.mkstemp()[1]

            vep_input_file = open(vep_input_file_path, 'w')
            vcf_stuff.write_sites_vcf(vep_input_file, variant_t_batch)
            vep_input_file.close()

            self._run_vep(vep_input_file_path, vep_output_file_path)

            ret = list(get_vep_annotations_from_vcf(open(vep_output_file_path)))
            os.remove(vep_input_file_path)
            os.remove(vep_output_file_path)
            return ret

        batch = []
        for variant_t in variant_t_list:
            batch.append(variant_t)
            if len(batch) == self._vep_batch_size:
                print "Running VEP on next {} variants, through {}".format(self._vep_batch_size, variant_t[0])
                annotations = process_batch(batch)
                for variant, annotation in annotations:
                    yield variant.unique_tuple(), annotation
                batch = []
        if len(batch) > 0:
            annotations = process_batch(batch)
            for variant, annotation in annotations:
                yield variant.unique_tuple(), annotation


def get_csq_fields_from_line(csq_line):
    """
    Runs a regex on meta line and gives back list of CSQ fields
    """
    search = re.search('Format: ([\w|\|]+)', csq_line)
    fields = search.group(1).split('|') if search.group(1) else []
    return [f.lower() for f in fields]


def get_vep_annotation_from_csq_info(csq_info_string, csq_field_names):
    """

    """
    csq_strings = csq_info_string.split(',')
    vals = []
    for s in csq_strings:
        d = {}
        csq_values = s.split('|')
        for i in range(len(csq_values)):

            csq_field = csq_field_names[i].lower()
            # ignore fields not in our whitelist
            if csq_field not in SAVED_VEP_FIELDS:
                continue

            # if a variant contains multiple consequence annotations, use the worst one
            if csq_field == 'consequence':
                annots = csq_values[i].split('&')
                val = annotation_utils.get_worst_vep_annotation(annots)

            # otherwise if it contains multiple annotations for a different field, just make the value a list
            # obvisouly this is suboptimal and we should not need to do this :/
            elif '&' in csq_values[i]:
                val = csq_values[i].split('&')
            else:
                val = csq_values[i]

            d[csq_field] = val

        d['is_nmd'] = "NMD_transcript_variant" in s
        d['is_nc'] = "nc_transcript_variant" in s

        vals.append(d)
    return vals


def get_csq_fields_from_vcf_desc(csq_desc):
    """
    Runs a regex on meta line and gives back list of CSQ fields
    """
    search = re.search('Format: ([\w|\|]+)', csq_desc)
    fields = search.group(1).split('|') if search.group(1) else []
    return [f.lower() for f in fields]


def get_vep_annotations_from_vcf(vcf_file_obj):
    """
    Iterate through the variants in a VEP annotated VCF, pull out annotation from CSQ field
    """
    vep_meta_fields = ['CSQ']
    header_info = {}
    csq_field_names = None
    for variant in vcf_stuff.iterate_vcf(vcf_file_obj, meta_fields=vep_meta_fields, header_info=header_info):
        if csq_field_names is None:
            csq_field_names = get_csq_fields_from_vcf_desc(header_info['CSQ'].desc)
        vep_annotation = get_vep_annotation_from_csq_info(variant.extras['CSQ'], csq_field_names)
        yield variant, vep_annotation