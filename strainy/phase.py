import multiprocessing
import pysam
import pickle
import os
import sys
import subprocess
from multiprocessing.managers import BaseManager
import logging
import shutil

from strainy.clustering.cluster import cluster
from strainy.color_bam import color
from strainy.flye_consensus import FlyeConsensus
from strainy.params import *
from strainy.logging import set_thread_logging


logger = logging.getLogger()



def _thread_fun(args):
    set_thread_logging(StRainyArgs.log_phase, "phase", multiprocessing.current_process().pid)
    logger.info("\n\n\t==== Processing uniting " + str(StRainyArgs.edges[args[0]]) + " ====")
    cluster(*args)
    logger.info("Thread finished!")


def _error_callback(pool, e):
    logger.error("Worker thread exception! " + str(e))
    pool.terminate()
    raise e


def phase(edges):
    logger.info("CMD: " + " ".join(sys.argv[1:]))
    if os.path.isdir(StRainyArgs.log_phase):
        shutil.rmtree(StRainyArgs.log_phase)
    os.mkdir(StRainyArgs.log_phase)
    default_manager = multiprocessing.Manager()
    empty_consensus_dict = {}
    shared_flye_consensus = FlyeConsensus(StRainyArgs.bam, StRainyArgs.fa, StRainyArgs.threads, empty_consensus_dict, default_manager)
    pool = multiprocessing.Pool(StRainyArgs.threads)
    init_args = [(i, shared_flye_consensus) for i in range(len(edges))]
    pool.map_async(_thread_fun, init_args, error_callback=lambda e: _error_callback(pool, e))
    pool.close()
    pool.join()
    shared_flye_consensus.print_cache_statistics()
    return shared_flye_consensus.get_consensus_dict()


def color_bam(edges):
    pool = multiprocessing.Pool(StRainyArgs.threads)
    pool.map(color, range(0, len(edges)))
    pool.close()

    out_bam_dir = os.path.join(StRainyArgs.output, 'bam')
    files_to_be_merged = []
    for fname in subprocess.check_output(f'find {out_bam_dir} -name "*unitig*.bam"', shell=True, universal_newlines=True).split('\n'):
        if len(fname):
            files_to_be_merged.append(fname)

    # Number of file to be merged could be > 4092, in which case samtools merge throws too many open files error
    for i, bam_file in enumerate(files_to_be_merged):
        # fetch the header and put it at the top of the file, for the first bam_file only
        if i == 0:
            subprocess.check_output(f"samtools view -H {bam_file} > {StRainyArgs.output}/bam/coloredSAM.sam", shell=True)

        # convert bam to sam, append to the file
        subprocess.check_output(f"samtools view {bam_file} >> {StRainyArgs.output}/bam/coloredSAM.sam", shell=True)

    # convert the file to bam and sort
    subprocess.check_output(f"samtools view -b {StRainyArgs.output}/bam/coloredSAM.sam >> {StRainyArgs.output}/bam/unsortedBAM.bam", shell=True)
    pysam.samtools.sort(f"{StRainyArgs.output}/bam/unsortedBAM.bam", "-o", f"{StRainyArgs.output}/bam/coloredBAM.bam")
    pysam.samtools.index(f"{StRainyArgs.output}/bam/coloredBAM.bam", f"{StRainyArgs.output}/bam/coloredBAM.bai")

    # remove unnecessary files
    os.remove(f"{StRainyArgs.output}/bam/unsortedBAM.bam")
    os.remove(f"{StRainyArgs.output}/bam/coloredSAM.sam")
    for f in files_to_be_merged:
        os.remove(f)


def phase_main():
    #logging.info(StRainyArgs)
    logger.info("Starting phasing")
    dirs = ("%s/vcf/" % StRainyArgs.output,
            "%s/adj_M/" % StRainyArgs.output,
            "%s/clusters/" % StRainyArgs.output,
            "%s/graphs/" % StRainyArgs.output,
            "%s/bam/" % StRainyArgs.output,
            "%s/bam/clusters" % StRainyArgs.output,
            "%s/flye_inputs" % StRainyArgs.output,
            "%s/flye_outputs" % StRainyArgs.output)

    for dir in dirs:
        try:
            os.stat(dir)
        except:
            os.makedirs(dir)

    consensus_dict = phase(StRainyArgs.edges)
    if write_consensus_cache:
        with open(os.path.join(StRainyArgs.output, consensus_cache_path), 'wb') as f:
            pickle.dump(consensus_dict, f)
    color_bam(StRainyArgs.edges)


if __name__ == "__main__":
    phase_main()
