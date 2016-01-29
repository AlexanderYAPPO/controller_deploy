import subprocess
import time
import re
import jinja2
import os
from subprocess import check_output
import argparse

DISKS = ["fast"]


def log(msg):
    print time.strftime("%d.%m.%Y %H:%M ") + msg


def log_info(msg):
    msg = "INFO:   " + msg
    log(msg)


def log_error(msg):
    msg = "Error:   " + msg
    log(msg)


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


class TestRunner(object):
    # bs in K, size in G (2^30B); disk name should be like "md3820i_raid_10_disks_5"
    def __init__(self, disk_name, bs, size):
        self.res_string = ""

        self.__start_tm__ = ""
        self.__disk_name__ = disk_name
        self.__bs__ = bs
        self.__size__ = size
        self.__storage_name__ = ""
        self.__raid__ = ""
        self.__disks_number__ = ""
        self.__parse_disk_name__()
        self.__ttype__ = ""

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
        dest = "/dev/disk/by-id/scsi-%s" % self.__disk_name__
        # dest = "/dev/null"
        bs = "%sKB" % self.__bs__
        run_arr = ["sudo", "dd", "if=%s" % source, "of=%s" % dest, "bs=%s" % bs, "count=%s" % self.__count__]
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
    def __init__(self, disk_name, bs, size, template_name):
        TestRunner.__init__(self, disk_name, bs, size)
        self.read_throughput = ""
        self.write_throughput = ""
        # self.read_iops = ""
        # self.write_iops = ""

        self.__template_name__ = template_name
        self.__fio_conf_name__ = "fio_%s_%sK_%sG" % (self.__disk_name__, self.__bs__, self.__size__)
        self.__ttype__ = "fio"
        self.__run__()

    def __run__(self):
        variables = {
            'disk_name': self.__disk_name__,
            'bs': "%sK" % self.__bs__,
            'size': "%sG" % self.__size__
        }
        with Jinja2Renderer(self.__template_name__, self.__fio_conf_name__, variables):
            run_arr = ["sudo", "fio", self.__fio_conf_name__]
            log_info("Running fio with args: %s" % ' '.join(run_arr))
            self.__start_tm__ = time.strftime("%d.%m.%Y %H:%M")
            self.res_string = check_output(run_arr, stderr=subprocess.STDOUT)
        self.__parse_output__()

    def __parse_output__(self):
        splitted_output = str.splitlines(self.res_string)
        write_stats = splitted_output[-1]
        read_stats = splitted_output[-2]
        read_throughput_match = re.search(r'aggrb=(.*?), ', read_stats)
        write_throughput_match = re.search(r'aggrb=(.*?), ', write_stats)
        try:
            self.read_throughput = read_throughput_match.group(1)
            self.write_throughput = write_throughput_match.group(1)
        except (IndexError, AttributeError):
            log_error("fio broken output (or broken regex matching), exiting")
            log_error(self.res_string)
            exit(1)

    def get_csv_vars_dict(self):
        res = super(FioRunner, self).get_csv_vars_dict()
        res.update({'fio_write': self.write_throughput,
                    'fio_read': self.read_throughput})
        return res


class IdDict:
    def __init__(self): pass
    def __getitem__(self, k): return k


class CSVWriter(object):
    def __init__(self, filename, open_csvf_flag):
        self.filename = filename
        self.__open_csvf_flag__ = open_csvf_flag
        self.__f__ = None
        self.__columns__ = ["start_tm", "disk_name", "storage", "raid", "disks", "bs", "size", "ttype", "dd_speed",
                            "fio_write", "fio_read"]
        self.__csv_empty_dict = dict((c, "") for c in self.__columns__)
        self.__csv_fmt__ =  ""
        for c in self.__columns__[:-1]:
            self.__csv_fmt__ += "%(" + c + ")s,"
        self.__csv_fmt__ += "%(" + self.__columns__[-1] + ")s\n"

    def __enter__(self):
        self.__f__ = open(self.filename, self.__open_csvf_flag__)
        self.__f__.write(self.__csv_fmt__ % IdDict())
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__f__.close()

    # accepts dict with column values
    def add_line(self, values):
        full_values = self.__csv_empty_dict.copy()
        full_values.update(values)
        self.__f__.write(self.__csv_fmt__ % full_values)


def run_tests(disks, dd_bss, fio_bss, sizes, csv_filename, open_csvf_flag, fio_template_name):
    with CSVWriter(csv_filename, open_csvf_flag) as cvw:
        for disk in disks:
            for size in sizes:
                for dd_bs in dd_bss:
                    dr = DDRunner(disk, dd_bs, size)
                    cvw.add_line(dr.get_csv_vars_dict())
                for fio_bs in fio_bss:
                    fr = FioRunner(disk, fio_bs, size, fio_template_name)
                    cvw.add_line(fr.get_csv_vars_dict())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Measure scsi disks perfomance with dd and fio. Usage example:\n'
                                                 'python storage_test.py --disks md3820i_raid_1_disks_2'
                                                 ' md3860i_raid_0_disks10 --dd_bss 4 4096 16384'
                                                 ' --fio_bss 1 4 128 1024 4096 --sizes 1 20 40 \n'
                                                 'Note that dd will not warn you if the disk doesn\'t exists!\n'
                                                 'Another important moment is that bss are passed in Kibibytes and'
                                                 ' sizes are passed in Gibibytes (i.e base 2).',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-d', '--disks', nargs='+',
                        help='<Required> disks to test. Disk names should be like md3820i_raid_10_disks_5 -- this way'
                             ' they will be correctly parsed.',
                        required=True)
    parser.add_argument('-ss', '--sizes', nargs='+',
                        help='<Required> int, amount of data to pass in G (GIBIBYTES!) (base 2)',
                        required=True, type=int)
    parser.add_argument('-dbs', '--dd_bss', nargs='*',
                        help='<Optional> int, dd block sizes in K (KIBIBYTES!) (base 2)',
                        default=[], type=int)
    parser.add_argument('-fbs', '--fio_bss', nargs='*',
                        help='<Optional> int, fio block sizes in K (KIBIBYTES!)(base 2)',
                        default=[], type=int)
    parser.add_argument('-csvf', '--csv_filename',
                        help='<Optional> csv with results filename, default storage_tests_res.csv',
                        default="storage_tests_res.csv")
    parser.add_argument('-ocsvf', '--open_csvf_flag',
                        help='<Optional> csv with results open flag, default is "w"', default="w")
    parser.add_argument('-fio_templ', '--fio_template_name',
                        help='<Optional> fio jinja2 template name, default is "danger-jinja2-template.j2". Must be'
                             ' located in the folder with the script. Passed args to it are bss, size and scsi'
                             ' device name',
                        default="danger-jinja2-template.j2")
    args = parser.parse_args()
    run_tests(args.disks, args.dd_bss, args.fio_bss, args.sizes, args.csv_filename, args.open_csvf_flag,
              args.fio_template_name)
