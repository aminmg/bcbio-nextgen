"""Provide analysis of input files by chromosomal regions.

Handle splitting and analysis of files from chromosomal subsets separated by
no-read regions.
"""
import os

from bcbio.distributed.split import (parallel_split_combine,
                                     grouped_parallel_split_combine, group_combine_parts)
from bcbio import utils
from bcbio.variation import genotype, multi

# ## data preparation

def add_region_info(samples, regions):
    """Add reference to BED file of callable regions to each sample.
    """
    out = []
    for data in samples:
        data["config"]["algorithm"]["callable_regions"] = regions["analysis_bed"]
        out.append(data)
    return out

# ## BAM preparation

def _split_by_regions(regions, dirname, out_ext, in_key):
    """Split a BAM file data analysis into chromosomal regions.
    """
    def _do_work(data):
        bam_file = data[in_key]
        if bam_file is None:
            return None, []
        part_info = []
        base_out = os.path.splitext(os.path.basename(bam_file))[0]
        nowork = [["nochrom"], ["noanalysis", regions["noanalysis"]]]
        for region in regions["analysis"] + nowork:
            out_dir = os.path.join(data["dirs"]["work"], dirname, data["name"][-1], region[0])
            if region[0] in ["nochrom", "noanalysis"]:
                region_str = region[0]
            else:
                region_str = "_".join([str(x) for x in region])
            region_outfile = os.path.join(out_dir, "%s-%s%s" %
                                          (base_out, region_str, out_ext))
            part_info.append((region, region_outfile))
        out_file = os.path.join(data["dirs"]["work"], dirname, data["name"][-1],
                                "%s%s" % (base_out, out_ext))
        return out_file, part_info
    return _do_work

def parallel_prep_region(samples, regions, run_parallel):
    """Perform full pre-variant calling BAM prep work on regions.
    """
    file_key = "work_bam"
    split_fn = _split_by_regions(regions, "bamprep", "-prep.bam", file_key)
    # identify samples that do not need preparation -- no prep or
    # variant calling
    extras = []
    torun = []
    for data in [x[0] for x in samples]:
        a = data["config"]["algorithm"]
        if (not a.get("mark_duplicates") and not a.get("recalibrate") and
              not a.get("realign", "gatk") and not a.get("variantcaller", "gatk")):
            extras.append([data])
        elif not data.get(file_key):
            extras.append([data])
        else:
            torun.append([data])
    return extras + parallel_split_combine(torun, split_fn, run_parallel,
                                           "piped_bamprep", None, file_key, ["config"])

def delayed_bamprep_merge(samples, run_parallel):
    """Perform a delayed merge on regional prepared BAM files.
    """
    needs_merge = False
    for data in samples:
        if (data[0]["config"]["algorithm"].get("merge_bamprep", True) and
              "combine" in data[0]):
            needs_merge = True
            break
    if needs_merge:
        return run_parallel("delayed_bam_merge", samples)
    else:
        return samples

# ## Variant calling

def _split_by_ready_regions(output_ext, file_key, dir_ext_fn):
    """Organize splits into pre-built files generated by parallel_prep_region
    """
    def _do_work(data):
        if "region" in data and not data["region"][0] in ["nochrom", "noanalysis"]:
            bam_file = data[file_key]
            ext = output_ext
            chrom, start, end = data["region"]
            base = os.path.splitext(os.path.basename(bam_file))[0]
            noregion_base = base[:base.index("-%s_%s_%s" % (chrom, start, end))]
            out_dir = os.path.join(data["dirs"]["work"], dir_ext_fn(data))
            out_file = os.path.join(out_dir, "{noregion_base}{ext}".format(**locals()))
            out_parts = []
            if not utils.file_exists(out_file):
                out_region_dir = os.path.join(out_dir, chrom)
                out_region_file = os.path.join(out_region_dir, "{base}{ext}".format(**locals()))
                out_parts = [(data["region"], out_region_file)]
            return out_file, out_parts
        else:
            return None, []
    return _do_work

def parallel_variantcall_region(samples, run_parallel):
    """Perform variant calling and post-analysis on samples by region.
    """
    to_process = []
    extras = []
    to_group = []
    for x in samples:
        added = False
        for add in genotype.handle_multiple_variantcallers(x):
            added = True
            to_process.append(add)
        if not added:
            if "combine" in x[0] and x[0]["combine"].keys()[0] in x[0]:
                assert len(x) == 1
                to_group.append(x[0])
            else:
                extras.append(x)
    split_fn = _split_by_ready_regions("-variants.vcf.gz", "work_bam", genotype.get_variantcaller)
    if len(to_group) > 0:
        extras += group_combine_parts(to_group)
    return extras + grouped_parallel_split_combine(to_process, split_fn,
                                                   multi.group_batches, run_parallel,
                                                   "variantcall_sample", "split_variants_by_sample",
                                                   "concat_variant_files",
                                                   "vrn_file", ["region", "sam_ref", "config"])

def clean_sample_data(samples):
    """Clean unnecessary information from sample data, reducing size for message passing.
    """
    out = []
    for data in samples:
        data["dirs"] = {"work": data["dirs"]["work"], "galaxy": data["dirs"]["galaxy"],
                        "fastq": data["dirs"].get("fastq")}
        data["config"] = {"algorithm": data["config"]["algorithm"],
                          "resources": data["config"]["resources"]}
        for remove_attr in ["config_file", "regions", "algorithm"]:
            data.pop(remove_attr, None)
        out.append([data])
    return out
