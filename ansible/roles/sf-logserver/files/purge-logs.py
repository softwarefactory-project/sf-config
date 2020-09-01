#!/usr/bin/env python3
#
# Copyright 2020 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import argparse
import os
from pathlib import Path
import shutil
import sys
import logging
from datetime import datetime, timedelta


parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('--retention-days', type=int, default=31)
parser.add_argument('--log-path-dir', default='/var/www/logs')
parser.add_argument('--debug', action='store_true')
args = parser.parse_args()
logging.basicConfig(
    format='%(asctime)s %(levelname)-5.5s %(message)s',
    level=logging.DEBUG if args.debug else logging.INFO)
log = logging.getLogger()


def check_dir_path(log_path):
    p = Path(log_path)
    if not p.exists():
        print("Can not find provided dir path %s" % log_path)
        sys.exit(1)
    return p.resolve()


def delete_dir(dir_path):
    shutil.rmtree(dir_path)


def get_jobdir(dirs, files):
    dirs_name = set(map(lambda s: s.name, dirs))

    def is_zuul():
        return 'zuul-info' in dirs_name

    def is_jenkins():
        return 'ara-database' in dirs_name

    def is_jenkins_console():
        return 'consoleText.txt' in files

    def is_empty_dir():
        return not files and not dirs

    return is_zuul() or is_jenkins() or is_jenkins_console() or is_empty_dir()


# (dirs, files)
# DirContent = typing.Tuple[typing.Set[Path], typing.Set[str]]


def ls(dir_path):
    dirs = set()
    files = set()
    for entry in os.listdir(dir_path):
        entry_path = dir_path / entry
        if entry_path.is_dir():
            dirs.add(entry_path)
        elif entry_path.exists():
            files.add(entry)
    return (dirs, files)


def find_old_files(calculated_time, log_path):
    queue = set((log_path, ))
    while queue:
        root = queue.pop()
        try:
            current_dirs, current_files = ls(root)
        except FileNotFoundError:
            log.exception("Directory not found")
            continue
        if get_jobdir(current_dirs, current_files):
            log.debug("%s : is a job dir", root)
            dir_date = datetime.fromtimestamp(os.path.getctime(root))
            if dir_date < calculated_time:
                yield root
        else:
            log.debug("%s : walking", root)
            queue = queue.union(current_dirs)


def search_and_destroy(calculated_time, dry_run, log_path):
    for job_dir in find_old_files(calculated_time, log_path):
        log.debug("%s : removing old logs", job_dir)
        if not dry_run and log_path != job_dir:
            delete_dir(job_dir)


if __name__ == "__main__":
    root = check_dir_path(args.log_path_dir)
    calculated_time = datetime.now() - timedelta(days=args.retention_days)
    search_and_destroy(calculated_time, args.dry_run, root)
