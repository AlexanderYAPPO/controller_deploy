import subprocess
import time
import re
import jinja2
import os
from subprocess import check_output
import argparse
import time
import json

def log(msg):
    print time.strftime("%d.%m.%Y %H:%M ") + msg


def log_info(msg):
    msg = "INFO:   " + msg
    log(msg)


def log_error(msg):
    msg = "Error:   " + msg
    log(msg)


def sleep(sec):
    log_info("Sleeping for %s sec" % sec)
    time.sleep(sec)

# Render source file to destination file with variables substitution. The template must be in the folder with script.
class Jinja2Renderer:
    __template_loader__ = jinja2.FileSystemLoader(searchpath=os.path.dirname(os.path.realpath(__file__)))
    __template_env__ = jinja2.Environment(loader=__template_loader__)

    def __init__(self, source, destination, variables):
        self.__destination__ = destination
        self.__variables__ = variables
        self.__template__ = self.__template_env__.get_template(source)

    def __enter__(self):
        output_text = self.__template__.render(self.__variables__)
        with open(self.__destination__, 'w') as f:
            f.write(output_text)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value:
            raise exc_value
        subprocess.check_call(["rm", self.__destination__])

class DestinationDisk:
    # mock enables writing to tmp file for local testing
    def __init__(self, disk_name, mock=False):
        self.disk_name = disk_name
        self.mock = mock
        # self.mock = True

    def get_full_disk_path(self):
        if self.mock:
            return "/tmp/test"
        else:
            return "/dev/disk/by-id/scsi-%s" % self.disk_name


class TestRunner(object):
    # bs in K, size in G (2^30B); disk name should be like "md3820i_raid_10_disks_5"
    def __init__(self, disk_name, bs, size):
        self.res_string = ""

        self.__start_tm__ = ""
        self.__disk_name__ = disk_name
        self.__disk_path__ = DestinationDisk(self.__disk_name__).get_full_disk_path()
        self.__bs__ = bs
        self.__size__ = size
        self.__storage_name__ = ""
        self.__raid__ = ""
        self.__disks_number__ = ""
        self.__parse_disk_name__()
        self.__ttype__ = ""
        self.__logfile__ = ""
        self.__duration__ = 0

    def __parse_disk_name__(self):
        parsed_disk_name_match = re.match(r'(.*?)_raid_([\d]+)_disks_([\d]+)', self.__disk_name__)
        if parsed_disk_name_match:
            self.__storage_name__ = parsed_disk_name_match.group(1)
            self.__raid__ = parsed_disk_name_match.group(2)
            self.__disks_number__ = parsed_disk_name_match.group(3)

    def get_csv_vars_dict(self):
        return {'start_tm': self.__start_tm__,
                'disk_name': self.__disk_name__,
                'storage': self.__storage_name__,
                'raid': self.__raid__,
                'disks': self.__disks_number__,
                'bs': "%sK" % self.__bs__,
                'size': "%sG" % self.__size__,
                'duration(sec)' : self.__duration__,
                'logfile' : self.__logfile__,
                'ttype': self.__ttype__}


# Run dd test from /dev/zero to scsi disk_name, bs and size.
class DDRunner(TestRunner):
    def __init__(self, disk_name, bs, size):
        TestRunner.__init__(self, disk_name, bs, size)
        self.speed = ""

        self.__count__ = size * 1024 * 1024 / bs
        self.__ttype__ = "dd"
        self.__run__()

    def __run__(self):
        source = "/dev/zero"
        bs = "%sKB" % self.__bs__
        run_arr = ["sudo", "dd", "if=%s" % source, "of=%s" % self.__disk_path__, "bs=%s" % bs, "count=%s" % self.__count__]
        log_info("Running dd with args: %s" % ' '.join(run_arr))
        self.__start_tm__ = time.strftime("%d.%m.%Y %H:%M")
        self.res_string = check_output(run_arr, stderr=subprocess.STDOUT)
        self.__parse_speed__()

    def __parse_speed__(self):
        line_with_speed = str.splitlines(self.res_string)[-1]
        speed_match = re.search(r', ([\d,.]+ .?.?/s)$', line_with_speed)
        try:
            self.speed = speed_match.group(1)
        except (IndexError, AttributeError):
            log_error("dd broken output (or broken regex matching), exiting")
            log_error(line_with_speed)
            exit(1)

    def get_csv_vars_dict(self):
        res = super(DDRunner, self).get_csv_vars_dict()
        res.update({'dd_speed': self.speed})
        return res


# Run fio test.
class FioRunner(TestRunner):
    def __init__(self, disk_name, bs, size, iodepth, read_percent, access, template_name, res_dir):
        TestRunner.__init__(self, disk_name, bs, size)
        self.read_bw = 0
        self.read_iops = 0
        self.read_clat_min = 0
        self.read_clat_max = 0
        self.read_clat_avg = 0
        self.write_bw = 0
        self.write_iops = 0
        self.write_clat_min = 0
        self.write_clat_max = 0
        self.write_clat_avg = 0


        self.__iodepth__ = iodepth
        self.__read_percent__ = read_percent
        self.__read_percent_j2__ = ""
        self.__access__ = access
        self.__access_j2__ = ""
        self.__rw_j2__ = ""
        self.__j2_dict__ = {}
        self.__start_tm__ = time.strftime("%d.%m.%Y_%H_%M")

        self.__template_name__ = template_name
        self.__test_id_string__ = "%s_%s_%sK_%sG_%siod_%sread_%s" % (self.__start_tm__, self.__disk_name__, self.__bs__,
                                                                     self.__size__, self.__iodepth__,
                                                                     self.__read_percent__, self.__access__)
        self.__fio_conf_name__ = "fio_%s" % self.__test_id_string__
        if not os.path.exists(res_dir):
            os.makedirs(res_dir)
        self.__logfile__ = os.path.join(res_dir, "%s.json" % self.__test_id_string__)

        self.__run__()

    def prepare_jinja2_vars(self):
        if self.__access__ == "seq":
            self.__access_j2__ = ""
        elif self.__access__ == "rand":
            self.__access_j2__ = "rand"
        else:
            log_error("Wrong access type: %s" % self.__access__)
            exit(1)

        if self.__read_percent__ == 0:
            self.__rw_j2__ = "write"
        elif self.__read_percent__ == 100:
            self.__rw_j2__ = "read"
        elif (self.__read_percent__ > 0) and (self.__read_percent__ < 100):
            self.__rw_j2__ = "rw"
            self.__read_percent_j2__ = "rwmixread=%s" % self.__read_percent__
        else:
            log_error("Wrong read_percent: %s" % self.__read_percent__)
            exit(1)

        self.__j2_dict__ = {
            'test_name' : "%s_%s" % (self.__rw_j2__, self.__access__),
            'disk_path': self.__disk_path__,
            'bs': "%sK" % self.__bs__,
            'size': "%sG" % self.__size__,
            'rw' : self.__rw_j2__,
            'rwmixread' : self.__read_percent_j2__,
            'iodepth' : self.__iodepth__
        }

    def __run__(self):
        self.prepare_jinja2_vars()
        with Jinja2Renderer(self.__template_name__, self.__fio_conf_name__, self.__j2_dict__):
            run_arr = ["sudo", "fio", self.__fio_conf_name__, "--output-format=json",
                       "--output=%s" % self.__logfile__]
            log_info("Running fio with args: %s" % ' '.join(run_arr))
            now = time.time()
            self.res_string = check_output(run_arr, stderr=subprocess.STDOUT)
            self.__duration__ = int(time.time() - now)
            subprocess.check_call(["sudo", "chmod", "6", self.__logfile__])
        self.__parse_output__()

    def __parse_output__(self):
        with open(self.__logfile__, 'r') as jf:
            json_data = json.load(jf)["jobs"][0]
            self.read_bw = json_data["read"]["bw"]
            self.read_iops = json_data["read"]["iops"]
            self.read_clat_min = json_data["read"]["clat"]["min"]
            self.read_clat_max = json_data["read"]["clat"]["max"]
            self.read_clat_avg = json_data["read"]["clat"]["percentile"]["50.000000"]
            self.write_bw = json_data["write"]["bw"]
            self.write_iops = json_data["write"]["iops"]
            self.write_clat_min = json_data["write"]["clat"]["min"]
            self.write_clat_max = json_data["write"]["clat"]["max"]
            self.write_clat_avg = json_data["write"]["clat"]["percentile"]["50.000000"]


    def get_csv_vars_dict(self):
        res = super(FioRunner, self).get_csv_vars_dict()
        res.update({'iodepth': self.__iodepth__,
                    'rw': self.__rw_j2__,
                    'access': self.__access__,
                    'read_bw' : self.read_bw,
                    'read_iops' : self.read_iops,
                    'read_clat_min' : self.read_clat_min,
                    'read_clat_max' : self.read_clat_max,
                    'read_clat_avg' : self.read_clat_avg,
                    'write_bw' : self.write_bw,
                    'write_iops' : self.write_iops,
                    'write_clat_min' : self.write_clat_min,
                    'write_clat_max' : self.write_clat_max,
                    'write_clat_avg' : self.write_clat_avg,
                     })
        return res


class IdDict:
    def __init__(self): pass
    def __getitem__(self, k): return k


class CSVWriter(object):
    def __init__(self, filename, open_csvf_flag):
        self.filename = filename
        self.__open_csvf_flag__ = open_csvf_flag
        self.__f__ = None
        self.__columns__ = ["start_tm", "duration(sec)", "disk_name", "storage", "raid", "disks", "bs", "size",
                            "iodepth", "rw", "access", "read_bw", "read_iops", "read_clat_min", "read_clat_max",
                            "read_clat_avg", "write_bw", "write_iops", "write_clat_min", "write_clat_max",
                            "write_clat_avg", "logfile"]

        self.__csv_empty_dict = dict((c, "") for c in self.__columns__)
        self.__csv_fmt__ =  ""
        for c in self.__columns__[:-1]:
            self.__csv_fmt__ += "%(" + c + ")s\t"
        self.__csv_fmt__ += "%(" + self.__columns__[-1] + ")s\n"

    def __enter__(self):
        self.__f__ = open(self.filename, self.__open_csvf_flag__, 0)
        self.__f__.write(self.__csv_fmt__ % IdDict())
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__f__.close()

    # accepts dict with column values
    def add_line(self, values):
        full_values = self.__csv_empty_dict.copy()
        full_values.update(values)
        self.__f__.write(self.__csv_fmt__ % full_values)
        self.__f__.flush() # we hardly need it since bufsize=0

# called between tests
def clean_cache():
    sleep(1)


def run_tests(disks, bss, sizes, iodepths, read_percents, accesses, csv_filename, open_csvf_flag, fio_template_name):
    with CSVWriter(csv_filename, open_csvf_flag) as cvw:
        for disk in disks:
            for size in sizes:
                for iodepth in iodepths:
                    for bs in bss:
                        for read_percent in read_percents:
                            for access in accesses:
                                fr = FioRunner(disk, bs, size, iodepth, read_percent, access, fio_template_name,
                                               "storage_tests_logs")
                                cvw.add_line(fr.get_csv_vars_dict())
                                clean_cache()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Measure scsi disks performance with fio. Usage example:\n'
                                                 'python storage_test.py --disks md3820i_raid_1_disks_2'
                                                 ' md3860i_raid_0_disks_10 --bss 1 4 128 1024 4096 --sizes 1 20 40'
                                                 ' --read_percents 0 25 50 75 100 --access rand seq \n'
                                                 'Note that that bss are passed in Kibibytes and'
                                                 ' sizes are passed in Gibibytes (i.e base 2).',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-d', '--disks', nargs='+',
                        help='<Required> disks to test. Disk names should be like md3820i_raid_10_disks_5 -- this way'
                             ' they will be correctly parsed.',
                        required=True)
    parser.add_argument('-fbs', '--bss', nargs='+',
                        help='<Required> int, fio block sizes in K (KIBIBYTES!)(base 2)',
                        type=int, required=True)
    parser.add_argument('-ss', '--sizes', nargs='+',
                        help='<Required> int, amount of data to pass in G (GIBIBYTES!) (base 2)',
                        required=True, type=int)
    parser.add_argument('-iod', '--iodepths', nargs='+',
                    help='<Required> int, fio iodepth',
                    required=True, type=int)
    parser.add_argument('-rp', '--read_percents', nargs='+',
                    help='<Required> int, read_percentage of test. 0 means write only test, 100 read only',
                    type=int, required=True)
    parser.add_argument('-acc', '--access', nargs='+',
                        help='<Required> Sequential, random or both. Accepted values: [seq], [rand], [seq rand]',
                        required=True)
    parser.add_argument('-csvf', '--csv_filename',
                        help='<Optional> csv with results filename, default storage_tests_res.csv',
                        default="storage_tests_res.csv")
    parser.add_argument('-ocsvf', '--open_csvf_flag',
                        help='<Optional> csv with results open flag, default is "w"', default="w")
    parser.add_argument('-fio_templ', '--fio_template_name',
                        help='<Optional> fio jinja2 template name, default is "fio.j2". Must be'
                             ' located in the folder with the script. Passed args to it are bss, size,'
                             ' scsi device name, rw type and optionally rwmixread',
                        default="fio.j2")
    # parser.add_argument('-dbs', '--dd_bss', nargs='*',
    #                     help='<Optional> int, dd block sizes in K (KIBIBYTES!) (base 2)',
    #                     default=[], type=int)
    args = parser.parse_args()
    run_tests(args.disks, args.bss, args.sizes, args.iodepths, args.read_percents, args.access, args.csv_filename,
              args.open_csvf_flag, args.fio_template_name)
