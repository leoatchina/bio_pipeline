# coding:utf8
'''Author leoatchina'''
import os
import traceback
import collections
import signal
import csv
import re
import datetime
import subprocess
import hashlib

from collections import deque
from multiprocessing import cpu_count
from multiprocessing import Pool

from collections import OrderedDict 

meminfo  = open('/proc/meminfo').read()
matched  = re.search(r'^MemTotal:\s+(\d+)', meminfo)
sys_mem  = int(int(matched.groups()[0])/1024/1024)
sys_core = cpu_count()


# 时间函数
def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def caluate_md5(file_path):
    try:
        myhash = hashlib.md5()
        with open(file_path, 'rb') as f:
            while True:
                b = f.read(8096)
                if not b:
                    break
                myhash.update(b)
        return myhash.hexdigest()
    except Exception as e:
        raise e


def compare_md5(file_path, md5):
    try:
        if not os.path.isfile(file_path):
            raise Exception("%s is not a file" % file_path)
        if md5:
            return (True if md5 == caluate_md5(file_path) else False)
        else:
            raise Exception("file or md5 absent")
    except Exception as e:
        print(file_path, e)
        return False


def check_md5(file_path, md5_file_path):
    try:
        md5 = os.popen('cat ' + md5_file_path).readlines()[0].strip()
        return compare_md5(file_path, md5)
    except Exception as e:
        raise e


def check_md5infile(file_path, md5_file_path):
    try:
        fl = file_path.split("/")[-1]
        md5 = ""
        for line in os.popen("cat %s" % md5_file_path).readlines():
            ln = line.strip("\n")
            if fl == ln.split("  ")[1]:
                md5 = ln.split("  ")[0]
                break
        if md5:
            return compare_md5(file_path, md5)
        else:
            return False
    except Exception as e:
        print(e)
        return False


def return_cmd(cmd):
    try:
        if cmd:
            tmp = os.popen(cmd).readlines()
            return [line.strip() for line in tmp]
        else:
            raise Exception("cmd is None")
    except Exception as e:
        print(e)
        return None


def mkdirs(*paths):
    for path in paths:
        os.system("mkdir -p %s" % path)


def write_to_csv(csv, *lst):
    if lst:
        lst = [i if len(i) > 0 else "" for i in lst]
        line = ",".join(lst)
        os.system("echo %s >> %s" % (line, csv))


def read_csv(csv_file, delimiter=","):
    with open(csv_file) as csv_handle:
        csv_reader = csv.reader(csv_handle, delimiter = delimiter)
        return [i for i in csv_reader]


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class Pipeline(object):
    ''' pipelines to run '''
    def __del__(self):
        self.pool.terminate()

    def terminate(self):
        self.pool.terminate()

    def __init__(self, run_csv = None, sync_cnt = 2, test = 1):
        # run_array to record run status
        # for a run_csv, the first column records diffrerent ids for samples
        self.run_csv   = run_csv
        self.run_array = OrderedDict()
        self.test      = test
        self.sync_cnt  = sync_cnt
        # One ID has its pipeline : pipelines[ID]
        self.pipelines = collections.OrderedDict()
        self.pool      = Pool(sync_cnt, init_worker, maxtasksperchild = sync_cnt)
        self.pool.terminate()
        if self.run_csv:
            if os.path.isfile(self.run_csv):
                lines = read_csv(self.run_csv)
                # skip header
                lines = lines[1:]
                # sometimes recorded time cover more than 1 cells, so combine them
                for line in lines:
                    if len(line) > 6:
                        line[5] = ",".join(line[5:])
                    line = [each.strip() for each in line[:6]] 
                    ID, procedure, target, start_time, end_time, cost_time = line
                    if target is None or len(target.strip()) == 0:
                        target = ""
                    runned = "%s:%s:%s" % (ID, procedure, target)
                    self.run_array[runned] = "%s %s %s" % (start_time, end_time, cost_time)
            else:
                # create record csv if not exists
                os.system("echo 'ID,procedure,target,start_time,end_time,cost_time' > %s" % self.run_csv)

    def append(self, ID, procedure, cmd, target = None, log = None, run_sync = False, record_on_error = False):
        if target is None or len(target.strip()) == 0:
            target = ""
        runned = "%s:%s:%s" % (ID, procedure, target)
        if runned in self.run_array:
            pass
        else:
            """ TODO
            run_sync参数, async run the procedure, cmd of differrnet target, default is False
            """
            if self.pipelines.get(ID, None):
                self.pipelines[ID].append((procedure, cmd, target, log, run_sync, record_on_error))
            else:
                self.pipelines[ID] = deque([(procedure, cmd, target, log, run_sync, record_on_error)])

    def run_pipeline(self):
        self.pool = Pool(self.sync_cnt, init_worker, maxtasksperchild = self.sync_cnt)
        for ID, pipeline in self.pipelines.items():
            for step in pipeline: 
                procedure, cmd, target, log, run_sync, record_on_error = step 
                self.pool.apply_async(Pipeline.run, args = (ID, pipeline, self.test, self.run_csv))
        self.pool.close()
        self.pool.join()
        self.pool.terminate()

    def print(self):
        for ID in self.pipelines:
            print("===== %s ======" % ID)
            pipeline = self.pipelines[ID]
            for cmd in pipeline:
                print(cmd)

    def print_runned(self):
        for runned in self.run_array:
            print(runned)

    # run is staticmethod, it could not be contained in class Pipeline
    @staticmethod
    def run(ID, procedure, cmd, target, log, run_sync, record_on_error, test, run_csv):
        try:
            start_time = datetime.datetime.now()
            now        = start_time.strftime("%Y-%m-%d %H:%M:%S")
            print("================ %s ===============\n%s\n" % (now, cmd))
            if not test:
                if log:
                    with open(log, 'wb') as file_out:
                        p = subprocess.Popen(cmd, stdout = file_out, stderr = file_out, shell = True)
                        p.wait()
                else:
                    subprocess.check_output(cmd, shell = True)
                end_time          = datetime.datetime.now()
                cost_time_reform  = str(end_time - start_time)
                start_time_reform = start_time.strftime("%Y-%m-%d %H:%M:%S")
                end_time_reform   = end_time.strftime("%Y-%m-%d %H:%M:%S")
                if run_csv:
                    write_to_csv(run_csv, ID, procedure, target, start_time_reform, end_time_reform, cost_time_reform)
                print("{}:{}, start at {}, fininshed at {}, cost {}".format(ID, procedure, start_time_reform, end_time_reform, cost_time_reform))
        except subprocess.CalledProcessError:
            end_time          = datetime.datetime.now()
            cost_time_reform  = str(end_time - start_time)
            start_time_reform = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_time_reform   = end_time.strftime("%Y-%m-%d %H:%M:%S")
            if record_on_error and run_csv:
                write_to_csv(run_csv, ID, procedure, target, start_time_reform, end_time_reform, cost_time_reform)
                print("{}:{}, started at {}, errored at {}, but still record".format(ID, procedure, start_time_reform, end_time_reform))
            else:
                print("{}:{}, started at {}, errored at {}, and not record".format(ID, procedure, start_time_reform, end_time_reform))
        except Exception as ex:
            traceback.print_exc()
            raise ex
