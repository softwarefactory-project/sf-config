#!/usr/bin/env python
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
import hashlib
import select
import smtplib
import socket
import time

from email.mime.text import MIMEText

try:
    from systemd import journal as systemd_journal
except ImportError:
    import subprocess
    subprocess.Popen(["sudo", "yum", "install", "-y", "systemd-python"]).wait()
    from systemd import journal as systemd_journal


def usage():
    p = argparse.ArgumentParser()
    p.add_argument("--mail", help="Alert by mail", nargs="+")
    p.add_argument("--sender", help="Mail from",
                   default="root@%s" % socket.gethostname())
    p.add_argument("--cache", help="Time in days to skip known traceback",
                   type=int, default=7)
    return p.parse_args()

# Store incomplete traceback per pid
backlog = {}
TRACE_COOKIE = 'Traceback (most recent call last):'


def process_event(pid, comm, message):
    if TRACE_COOKIE in message:
        if pid in backlog:
            print("%s is raising interlaced traceback..." % pid)
            return None
        else:
            # Store traceback column position
            backlog[pid] = [message.index(TRACE_COOKIE)]
    elif pid in backlog:
        # Traceback already in progress
        if len(backlog[pid]) > 512:
            print("%s is raising super long traceback..." % pid)
            return backlog[pid][1:]
        tb_column = backlog[pid][0]
        if len(message) <= tb_column:
            # Traceback seems to be over
            return backlog[pid][1:]
        line = message[tb_column:]
        backlog[pid].append(line)
        t = line.split()
        if not t:
            # Traceback seems to be over
            return backlog[pid][1:]
        # Even line, it should start with 'File'
        if len(backlog[pid][1:]) & 1 == 1:
            if t[0] != 'File':
                # Traceback seems to be over
                return backlog[pid][1:]


def sendmail(args, subject, message):
    for mail in args.mail:
        msg = MIMEText(message)

        msg['Subject'] = subject
        msg['From'] = args.sender
        msg['To'] = mail

        s = smtplib.SMTP('localhost')
        s.sendmail(args.sender, [mail], msg.as_string())
        s.quit()


def main():
    args = usage()
    journal = systemd_journal.Reader()
    journal.log_level(systemd_journal.LOG_INFO)
    journal.this_boot()
    journal.seek_tail()
    journal.get_previous()
    fd = journal.fileno()
    p = select.poll()
    poll_event_mask = journal.get_events()
    p.register(fd, poll_event_mask)

    known_tb = {}

    time_limit = 3600 * 24 * args.cache

    while p.poll():
        try:
            if journal.process() != systemd_journal.APPEND:
                continue
            for event in journal:
                unit = event.get('_SYSTEMD_UNIT')
                pid = event.get('_PID')
                comm = event.get('_COMM')
                if comm and "segfault" in comm:
                    event_title = "%s: %s" % (socket.gethostname(), comm)
                    print(event_title)
                    if args.mail:
                        sendmail(args, event_title, "")
                traceback = process_event(pid, comm, event.get("MESSAGE"))
                if not traceback:
                    continue
                del backlog[pid]
                traceback_hash = hashlib.md5(
                    "".join(traceback[1:-1])).hexdigest()
                if traceback_hash in known_tb:
                    if time.time() - known_tb[traceback_hash] < time_limit:
                        # Already saw this week
                        continue
                event_title = "=== New traceback from %s %s %s[%s]" % (
                    socket.gethostname(), unit, comm, pid)
                event_body = "\n".join(traceback)
                print(event_title)
                print(event_body)
                if args.mail:
                    sendmail(args, event_title, event_body)
                known_tb[traceback_hash] = time.time()

        except KeyboardInterrupt:
            exit(0)

if __name__ == "__main__":
    main()
