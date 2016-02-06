import subprocess
import time
import re
import jinja2
import os
from subprocess import check_output
import argparse
import time
import json
from storage_test import *


class WrongJsonFilename(Exception):
    pass


def parse_json_filename(j, jdir):
    j_match = re.match(r'(\d+\.\d+\.\d+_\d+_\d+)_(.*_raid_\d+_disks_\d+)_(\d+)K_(\d+)G_(\d+)iod_(\d+)read_(seq|rand).json$', j)
    if not j_match:
        raise WrongJsonFilename
    else:
        start_tm = j_match.group(1)
        disk_name = j_match.group(2)
        bs = int(j_match.group(3))
        size = int(j_match.group(4))
        iodepth = int(j_match.group(5))
        read_percent = int(j_match.group(6))
        access = j_match.group(7)
        fr = FioRunner(disk_name, bs, size, iodepth, read_percent, access, jdir, start_tm)
        fr.parse_output()
        return fr.get_csv_vars_dict()


def csv_from_jsons(dir_with_jsons, outfile, outfile_flag):
    if not os.path.isdir(dir_with_jsons):
        log_error("Directory with jsons not found: %s" % dir_with_jsons)
    else:
        with CSVWriter(outfile, outfile_flag) as cvw:
            jsons = [f for f in os.listdir(dir_with_jsons) if os.path.isfile(os.path.join(dir_with_jsons, f))]
            for j in jsons:
                try:
                    cvw.add_line(parse_json_filename(j, dir_with_jsons))
                    # log_info("File %s parsed" % j)
                except WrongJsonFilename:
                    log_warn("Error while parsing filename %s; skipping it " % j)
                    continue

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parses json files in passed dir, forming main csv file. If '
                                                 'json filename or content is broken, the file will be skipped with '
                                                 'the warning. '
                                                 'Usage example: python json_to_res.py storage_tests_logs')
    parser.add_argument("dir_with_jsons", help="dir with jsons to parse")
    parser.add_argument('-o', '--outfile', nargs='?', default='storage_tests_res.csv',
                        help='result csv file, default storage_tests_res.csv')
    parser.add_argument('-oflag', '--outfile_flag', nargs='?', default='w',
                        help='result csv file opening flag, default "w"')
    args = parser.parse_args()
    csv_from_jsons(args.dir_with_jsons, args.outfile, args.outfile_flag)