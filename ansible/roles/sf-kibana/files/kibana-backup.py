#!/usr/bin/env python3

# Original source: https://github.com/selivan/kibana-backup-simple
# Small improvements are done in fork:
# https://github.com/danpawlik/kibana-backup-simple

# Kibana documentation:
# https://www.elastic.co/guide/en/kibana/current/saved-objects-api-export.html
# https://www.elastic.co/guide/en/kibana/current/saved-objects-api-import.html

import datetime
import json
import sys
import time
import argparse
import requests
import os

# Error message from Kibana listing all possible saved objects types:
# \"type\" must be one of:
# [config, map, canvas-workpad, canvas-element, index-pattern,
#  visualization, search, dashboard, url]
saved_objects_types = (
    'config', 'map', 'canvas-workpad', 'canvas-element', 'index-pattern',
    'visualization', 'search', 'dashboard', 'url')


def backup(kibana_url, space_id, user, password, backup_dir, insecure):
    """Return string with newline-delimitered json containing
    Kibana saved objects"""
    saved_objects = {}
    if not backup_dir:
        backup_dir = os.path.dirname(os.path.realpath(__file__))

    # Set the same time for all backups if previous exists
    b_time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")

    if len(space_id):
        url = kibana_url + '/s/' + space_id + '/api/saved_objects/_export'
    else:
        url = kibana_url + '/api/saved_objects/_export'
    for obj_type in saved_objects_types:
        r = requests.post(
            url,
            auth=(user, password),
            headers={'Content-Type': 'application/json',
                     'kbn-xsrf': 'reporting'},
            data='{ "type": "' + obj_type + '" }',
            verify=insecure
        )

        if r.status_code == 400:
            # Print warning on missing object, but continue
            print("Can not backup object %s" % obj_type)
            continue
        else:
            r.raise_for_status()  # Raises stored HTTPError

        saved_objects[obj_type] = r.text

        backup_file = "%s/%s.ndjson" % (backup_dir, obj_type)
        if os.path.exists(backup_file):
            backup_file = "%s-%s" % (backup_file, b_time)
        with open(backup_file, 'a') as f:
            f.write(r.text)

    backup_file = "%s/backup.ndjson" % backup_dir
    if os.path.exists(backup_file):
        backup_file = "%s-%s" % (backup_file, b_time)
    with open(backup_file, 'a') as f:
        f.write('\n'.join(saved_objects.values()))

    return '\n'.join(saved_objects.values())


def restore(kibana_url, space_id, user, password, text, resolve_conflicts,
            insecure):
    """Restore given newline-delimitered json containing
    saved objects to Kibana"""

    if len(space_id):
        url = (kibana_url + '/s/' + space_id +
               '/api/saved_objects/_import?overwrite=true')
    else:
        url = kibana_url + '/api/saved_objects/_import?overwrite=true'
    print('POST ' + url)
    for kib_obj in text:
        print("Working on %s" % kib_obj)

        if check_if_empty(kib_obj):
            print("Spotted empty object. Continue...")
            continue

        r = make_request(url, user, password, kib_obj, insecure)

        if not r:
            print("Can not import %s into Kibana" % kib_obj)
            continue

        response_text = json.loads(r.text)
        if not response_text['success'] and resolve_conflicts:
            text = remove_reference(kib_obj)
            r = make_request(url, user, password, text, insecure)

        print(r.status_code, r.reason, '\n', r.text)
        r.raise_for_status()  # Raises stored HTTPError, if one occurred.


def remove_reference(text):
    text = json.loads(text)
    new_references = []
    for ref in text['references']:
        if not ref['id'].startswith('AX') and len(ref['id']) != 20:
            new_references.append(ref)
    text['references'] = new_references
    return json.dumps(text)


def make_request(url, user, password, text, insecure=False, retry=True):
    r = None
    try:
        r = requests.post(
            url,
            auth=(user, password),
            headers={'kbn-xsrf': 'reporting'},
            files={'file': ('backup.ndjson', text)},
            timeout=10,
            verify=insecure
        )
    except requests.exceptions.ReadTimeout:
        if not retry:
            print("Importing failed. Retrying...")
            time.sleep(10)
            make_request(url, user, password, text, insecure)

    if "Please enter your credentials" in r.text:
        print("Please provide correct username and password")
        sys.exit(1)

    return r


def check_if_empty(text):
    text = json.loads(text)
    if 'exportedCount' in text and text['exportedCount'] == 0:
        return True


if __name__ == '__main__':
    args_parser = argparse.ArgumentParser(
        description='Backup and restore Kibana saved objects. '
                    'Writes backup to stdout and reads from stdin.')
    args_parser.add_argument('action', choices=['backup', 'restore'])
    args_parser.add_argument('--kibana-url', default='http://127.0.0.1:5601',
                             help='URL to access Kibana API')
    args_parser.add_argument('--space-id', default='',
                             help='Kibana space id. If not set then the '
                                  'default space is used.')
    args_parser.add_argument('--user', default='', help='Kibana user')
    args_parser.add_argument('--password', default='', help='Kibana password')
    args_parser.add_argument('--backup-dir',
                             help='Dir where backups will be stored')
    args_parser.add_argument('--restore-file', help='ndjson file to restore')
    args_parser.add_argument('--resolve-conflicts', default=True,
                             help='Resolve conflicts by removing index '
                                  'id reference in backup file')
    args_parser.add_argument('--insecure', action='store_true',
                             help='Use that option to ignore if SSL cert '
                                  'has been verified by root CA')
    args = args_parser.parse_args()

    kibana_url = args.kibana_url
    if (not args.kibana_url.startswith('http') and
            not args.kibana_url.startswith('https')):
        kibana_url = "http://%s" % args.kibana_url

    if args.action == 'backup':
        print(backup(kibana_url, args.space_id, args.user, args.password,
                     args.backup_dir, args.insecure)
              )
    elif args.action == 'restore':
        if args.restore_file:
            with open(args.restore_file) as f:
                text = f.readlines()
        else:
            text = ''.join(sys.stdin.readlines())

        restore(kibana_url, args.space_id, args.user, args.password,
                text, args.resolve_conflicts, args.insecure)
