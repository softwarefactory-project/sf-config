#!/bin/env python
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
import requests
import subprocess
import sys
import time

import smtplib
from email.mime.text import MIMEText


def log(msg):
    print(msg)
    subprocess.Popen(["logger", "smart-restart: %s" % msg]).wait()


def sendmail(args, subject, message):
    msg = MIMEText(message)

    msg['Subject'] = subject
    msg['From'] = args.sender
    msg['To'] = args.mail

    s = smtplib.SMTP('localhost')
    s.sendmail(args.sender, [args.mail], msg.as_string())
    s.quit()


def usage():
    p = argparse.ArgumentParser()

    p.add_argument("role", choices=("zuul", "zuul3"))
    p.add_argument("services", nargs="+", help='The services\' name')
    p.add_argument("--url", help='The services status url')
    p.add_argument("--mail", help='The admin mail to contact')
    p.add_argument("--sender", help='The mail sender')
    p.add_argument("--retries", type=int, default=60)
    p.add_argument("--delay", type=int, default=10)
    p.add_argument("--action", choices=("restart", "stop"), default='restart')
    return p.parse_args()


def daemonize():
    # A really basic daemonize method that should work well enough for
    # now in this circumstance. Based on the public domain code at:
    # http://web.archive.org/web/20131017130434/http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

    pid = os.fork()
    if pid > 0:
        return True

    os.chdir('/')
    os.setsid()
    os.umask(0)

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    sys.stdout.flush()
    sys.stderr.flush()
    i = open('/dev/null', 'r')
    o = open('/dev/null', 'a+')
    e = open('/dev/null', 'a+', 0)
    os.dup2(i.fileno(), sys.stdin.fileno())
    os.dup2(o.fileno(), sys.stdout.fileno())
    os.dup2(e.fileno(), sys.stderr.fileno())
    return False


def smart_restart_zuul(args):
    # Check if services are actually running
    services = []
    if args.action == "restart":
        for service in args.services:
            if not subprocess.Popen(
                    ["systemctl", "is-active", "-q", service]).wait():
                services.append(service)
    else:
        services = args.services
    if not services:
        return True

    # Check if jobs are running
    jobs = {}
    try:
        req = requests.get("%s/status.json" % args.url)
        status = req.json()
    except:
        status = {}
    for pipeline in status.get("pipelines", []):
        for change_queue in pipeline.get("change_queues", []):
            if change_queue.get("heads"):
                jobs.setdefault(pipeline["name"], 0)
                jobs[pipeline["name"]] += len(change_queue["heads"])
    if jobs:
        log("Can't restart zuul because jobs are running: %s" % jobs)
        return False
    for service in ("zuul-server", "zuul-launcher", "zuul-merger"):
        if service in args.services:
            subprocess.Popen(["systemctl", args.action, service]).wait()
    return True


def smart_restart_zuul3(args):
    # Check if services are actually running
    services = []
    if args.action == "restart":
        for service in args.services:
            if not subprocess.Popen(
                    ["systemctl", "is-active", "-q", service]).wait():
                services.append(service)
    else:
        services = args.services
    if not services:
        return True

    # Check if jobs are running
    jobs = {}
    try:
        req = requests.get("%s/status.json" % args.url)
        status = req.json()
    except:
        status = {}
    for pipeline in status.get("pipelines", []):
        for change_queue in pipeline.get("change_queues", []):
            if change_queue.get("heads"):
                jobs.setdefault(pipeline["name"], 0)
                jobs[pipeline["name"]] += len(change_queue["heads"])
    if jobs:
        log("Can't restart zuul3 because jobs are running: %s" % jobs)
        return False
    for service in ("scheduler", "executor", "merger", "web"):
        service = "rh-python35-zuul-%s" % service
        if service in args.services:
            subprocess.Popen(["systemctl", args.action, service]).wait()
    return True


def smart_restart(args):
    if args.role == "zuul":
        return smart_restart_zuul(args)
    elif args.role == "zuul3":
        return smart_restart_zuul3(args)


def restart(args, daemon):
    if daemon:
        if daemonize():
            exit(0)
        retries = args.retries
    else:
        # Only retries 7 times in foreground
        retries = 3
    for retry in range(retries):
        if smart_restart(args):
            return True
        time.sleep(args.delay)
    if daemon:
        # Alert the admin restart couldn't be performed
        log("Couldn't restart %s, sending a mail now" % args)
        if args.mail:
            sendmail(args, "Action required about %s" % args.role,
                     "sfconfig couldn't perform smart-restart %s.\n" % args +
                     "Please manually connect to the instance and restart the "
                     "services to apply configuration change.")
    return False


def main():
    args = usage()

    if args.role == "zuul3":
        args.services = list(map(lambda x: "rh-python35-%s" % x,
                                 args.services))

    if restart(args, daemon=False):
        # If restart succeeded, notify ansible task
        return 3
    log("Couldn't restart %s in time, continuing as a daemon now" % args.role)

    # Restart is not possible right now, let's keep trying in background
    restart(args, daemon=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log("Unexpected error running %s" % " ".join(sys.argv))
        raise
