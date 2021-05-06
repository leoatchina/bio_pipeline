#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File              : pipeline.py
# Author            : taotao <taotao@myhexin.com>
# Date              : 2021.04.13
# Last Modified Date: 2021.04.13
# Last Modified By  : taotao <taotao@myhexin.com>
# coding:utf8
# type: ignore

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

    def __init__(self, run_csv=None, sync_cnt=2):
        # run_array to record run status
        # for a run_csv, the first column records diffrerent ids for samples
        self.run_csv   = run_csv
        self.run_array = OrderedDict()
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
                    # 因为会有某些程序要运行超过1天的情况, 会出现预期之外的“， ”
                    # 这个时候，最后一个数字是以秒为单位， 而他前面几个
                    cost_time = line[-1].strip()
                    line = [each.strip() for each in line[:5]]
                    ID, mark, target, start_time, end_time = line
                    if target is None or len(target.strip()) == 0:
                        target = ""
                    runned = "%s:%s:%s" % (ID, mark, target)
                    self.run_array[runned] = "%s %s %s" % (start_time, end_time, cost_time)
            else:
                # create record csv if not exists
                os.system("echo 'ID,mark,target,start_time,end_time,cost_time_reform,cost_time' > %s" % self.run_csv)

    def append(self, ID, mark, cmd, log = None, target = None, system_cmd = True, record_on_error = False):
        """
        TODO, system_cmd mean use os.popopen(cmd), otherwise python command
        """
        if target is None or len(target.strip()) == 0:
            target = ""
        runned = "%s:%s:%s" % (ID, mark, target)
        if runned in self.run_array:
            if self.pipelines.get(ID, None):
                self.pipelines[ID].append((mark, cmd, target, log, record_on_error, True))
            else:
                self.pipelines[ID] = deque([(mark, cmd, target, log, record_on_error, True)])
        else:
            if self.pipelines.get(ID, None):
                self.pipelines[ID].append((mark, cmd, target, log, record_on_error, False))
            else:
                self.pipelines[ID] = deque([(mark, cmd, target, log, record_on_error, False)])

    def print_pipeline(self, print_type = "torun", ID = None):
        """
        print command
        """
        for id in self.pipelines:
            # 只打印指定的id
            if ID is not None:
                if isinstance(ID, list) or isinstance(ID, tuple):
                    if id not in ID:
                        continue
                elif id != ID:
                    continue
            print("===== %s ======" % id)
            pipeline = self.pipelines[id]
            for procedure in pipeline:
                mark, cmd, target, log, record_on_error, runned = procedure
                # 打全部
                if print_type == "all":
                    print("========================= %s =============================" % mark)
                    print(cmd)
                elif print_type == "runned" and runned:
                    print("========================= %s =============================" % mark)
                    print(cmd)
                elif print_type == "torun" and not runned:
                    print("========================= %s =============================" % mark)
                    print(cmd)
            print()

    def print_all(self, ID = None):
        """print_pipelineprint alll commands"""
        self.print_pipeline('all', ID)

    def print_runned(self, ID = None):
        """print runned commands"""
        self.print_pipeline('runned', ID)

    def print_torun(self, ID = None):
        """print to run commands"""
        self.print_pipeline("torun", ID)

    def run_pipeline(self, run = 1):
        if run == 0:
            self.print_torun()
        elif run == 1:
            if self.run_csv:
                bak_csv = re.sub(".csv$", ".%s.csv" % datetime.datetime.now().strftime("%Y%m%d%H%M"), self.run_csv)
                os.system("cp %s %s" % (self.run_csv, bak_csv))
            # TODO add ctrl-c exception
            # for example bqsr and apply_bqsr
            self.pool = Pool(self.sync_cnt, init_worker, maxtasksperchild = self.sync_cnt)
            try:
                for ID, pipeline in self.pipelines.items():
                    self.pool.apply_async(Pipeline.run, args = (ID, pipeline, self.run_csv,))
            except KeyboardInterrupt:
                print('==================== catch keyboardinterupterror =========================')
                self.pool.terminate()
            except Exception:
                traceback.print_exc()
                self.pool.terminate()
            else:
                self.pool.close()
            self.pool.join()
            # TODO, add callculate to total cost_time of a ID
        elif run == 2:
            self.print_runned()
        elif run == 3:
            self.print_all()
        else:
            print("run parameter wrong")

    # run is staticmethod, it could not be contained in class Pipeline
    @staticmethod
    def run(ID, pipeline, run_csv):
        processes = []
        for procedure in pipeline:
            try:
                mark, cmd, target, log, record_on_error, runned = procedure
                if runned:
                    continue
                start_time = datetime.datetime.now()
                start_time_reform = start_time.strftime("%Y-%m-%d %H:%M:%S")
                print("================ %s %s %s %s ===============\n%s\n" % (start_time_reform, ID, mark, target, cmd))
                # 输出到log文件
                if log:
                    with open(log, 'wb') as file_out:
                        p = subprocess.Popen(cmd, stdout = file_out, stderr = file_out, shell = True)
                        processes.append(p)
                        p.wait()
                else:
                    p = subprocess.check_output(cmd, shell = True)
                    processes.append(p)
            # FIXME:
            except subprocess.CalledProcessError:
                end_time          = datetime.datetime.now()
                cost_time         = end_time - start_time
                cost_time_reform  = str(cost_time)
                cost_time         = str(cost_time.total_seconds())
                end_time_reform   = end_time.strftime("%Y-%m-%d %H:%M:%S")
                if record_on_error and run_csv:
                    write_to_csv(run_csv, ID, mark, target, start_time_reform, end_time_reform, cost_time_reform, cost_time)
                    print("{}:{}:{}, started at {}, errored at {}, but still record".format(ID, mark, target, start_time_reform, end_time_reform))
                else:
                    print("{}:{}:{}, started at {}, errored at {}, and not record".format(ID, mark, target, start_time_reform, end_time_reform))
            except Exception as ex:
                raise ex
            else:
                end_time          = datetime.datetime.now()
                cost_time         = end_time - start_time
                cost_time_reform  = str(cost_time)
                cost_time         = str(cost_time.total_seconds())
                end_time_reform   = end_time.strftime("%Y-%m-%d %H:%M:%S")
                if run_csv:
                    write_to_csv(run_csv, ID, mark, target, start_time_reform, end_time_reform, cost_time_reform, cost_time)
                print("{}:{}:{}, start at {}, fininshed at {}, cost {}".format(ID, mark, target, start_time_reform, end_time_reform, cost_time))
