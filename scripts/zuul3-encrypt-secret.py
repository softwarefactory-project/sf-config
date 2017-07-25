#!/usr/bin/env python
# Modified from openstack-infra/zuul/tools/encrypt_secret.py

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
import base64
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap

DESCRIPTION = """Encrypt a secret for Zuul.

This program fetches a project-specific public key from a Zuul server and
uses that to encrypt a secret.  The only pre-requisite is an installed
OpenSSL binary.
"""


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('key', help="The path of the key.")
    parser.add_argument('name', help="The name of the secret.")
    parser.add_argument('--infile',
                        default=None,
                        help="A filename whose contents will be encrypted.  "
                        "If not supplied, the value will be read from "
                        "standard input.")
    parser.add_argument('--outfile',
                        default=None,
                        help="A filename to which the encrypted value will be "
                        "written.  If not supplied, the value will be written "
                        "to standard output.")
    args = parser.parse_args()

    pubkey = open(args.key)

    if args.infile:
        with open(args.infile) as f:
            plaintext = f.read()
    else:
        plaintext = sys.stdin.read()

    plaintext = plaintext.encode("utf-8")

    pubkey_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        pubkey_file.write(pubkey.read())
        pubkey_file.close()

        p = subprocess.Popen(['openssl', 'rsa', '-text',
                              '-pubin', '-in',
                              pubkey_file.name],
                             stdout=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            raise Exception("Return code %s from openssl" % p.returncode)
        output = stdout.decode('utf-8')
        m = re.match(r'^Public-Key: \((\d+) bit\)$', output, re.MULTILINE)
        nbits = int(m.group(1))
        nbytes = int(nbits / 8)
        max_bytes = nbytes - 42  # PKCS1-OAEP overhead
        chunks = int(math.ceil(float(len(plaintext)) / max_bytes))

        ciphertext_chunks = []

        for count in range(chunks):
            chunk = plaintext[int(count * max_bytes):
                              int((count + 1) * max_bytes)]
            p = subprocess.Popen(['openssl', 'rsautl', '-encrypt',
                                  '-oaep', '-pubin', '-inkey',
                                  pubkey_file.name],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            (stdout, stderr) = p.communicate(chunk)
            if p.returncode != 0:
                raise Exception("Return code %s from openssl" % p.returncode)
            ciphertext_chunks.append(base64.b64encode(stdout).decode('utf-8'))

    finally:
        os.unlink(pubkey_file.name)

    output = textwrap.dedent('%s: !encrypted/pkcs1-oaep\n' % args.name)

    twrap = textwrap.TextWrapper(width=79,
                                 initial_indent=' ' * 8,
                                 subsequent_indent=' ' * 10)
    for chunk in ciphertext_chunks:
        chunk = twrap.fill('- ' + chunk)
        output += chunk + '\n'

    if args.outfile:
        with open(args.outfile, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == '__main__':
    main()
