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
import base64
import os
import time
import xml.dom.minidom

from hashlib import sha256
from Crypto.Cipher import AES


def usage():
    p = argparse.ArgumentParser()

    p.add_argument("--secrets-dir",
                   default="/var/lib/software-factory/jenkins")
    p.add_argument("action", choices=('create', 'read', 'update', 'delete'))
    p.add_argument("uid", help='The secret id')
    p.add_argument("content", nargs="?", help='The secret value/file')
    p.add_argument("--description", help='Optional secret description')
    return p.parse_args()


class JenkinsSecretEditor:
    def __init__(self, secrets_dir):
        self.secrets_dir = secrets_dir

        def read(path):
            try:
                return open(os.path.join(secrets_dir, path), "rb").read()
            except OSError:
                raise RuntimeError("Couldn't read jenkins files")
        master_key = read("secrets/master.key")
        hudson_file = read("secrets/hudson.util.Secret")
        file_file = read("secrets/org.jenkinsci.plugins.plaincredentials."
                         "impl.FileCredentialsImpl")
        credencial = read("credentials.xml")

        self.text_key = AES.new(sha256(master_key).digest()[:16],
                                AES.MODE_ECB).decrypt(hudson_file)[:16]
        self.file_key = AES.new(sha256(master_key).digest()[:16],
                                AES.MODE_ECB).decrypt(file_file)[:16]
        self.creds = xml.dom.minidom.parseString(credencial)

    def save(self):
        fpath = os.path.join(self.secrets_dir, "credentials.xml")
        # Backup old file
        os.rename(fpath, "%s-%s" % (fpath, time.strftime("%Y-%m-%d-%s")))
        with open(fpath, "w") as of:
            of.write(self.creds.toprettyxml())
            print("%s: updated" % fpath)

    def decrypt(self, node, tag, key):
        data = AES.new(key, AES.MODE_ECB).decrypt(base64.b64decode(
            self.get_node_data(node, tag)))
        if b"::::MAGIC::::" in data:
            data = data[:data.index(b"::::MAGIC::::")]
        # Jenkins uses a weird padding for file, remove it from known type
        elif b"\x00\x00" in data[-32:]:
            # Tarball padding
            data = data[:data.rindex(b"\x00\x00") + 2]
        elif b"\x0a" in data[-32:]:
            # Textfile padding
            data = data[:data.rindex(b"\x0a") + 1]
        return data

    def encrypt(self, content, key):
        content += b"::::MAGIC::::"
        pad = 16 - (len(content) % 16)
        content += b"\x00" * pad
        return base64.b64encode(AES.new(key, AES.MODE_ECB).encrypt(content))

    def get_nodes(self):
        return self.creds.getElementsByTagName(
            "java.util.concurrent.CopyOnWriteArrayList")[0]

    def iter_node(self):
        for node in self.get_nodes().childNodes:
            if node.nodeType == node.TEXT_NODE:
                continue
            yield node

    def get_node_data(self, node, tag):
        child = node.getElementsByTagName(tag)
        if len(child) == 0 or child[0] is None or child[0].firstChild is None:
            return ""
        return child[0].firstChild.data

    def get_node_type(self, node):
        return node.tagName.split(".")[-1]

    def get_node(self, uid):
        for node in self.iter_node():
            if self.get_node_data(node, "id") == uid:
                return node

    def read(self, uid):
        for node in self.iter_node():
            if uid == "all" or uid == self.get_node_data(node, "id"):
                node_type = self.get_node_type(node)
                print("%s: %s | %s" % (
                    self.get_node_data(node, "id"),
                    node_type,
                    self.get_node_data(node, "description")
                ))
                if node_type == "StringCredentialsImpl":
                    secret = self.decrypt(node, "secret", self.text_key)
                elif node_type == "FileCredentialsImpl":
                    secret = self.get_node_data(node, "fileName")
                    if os.path.isfile(secret):
                        print("=> Skipping because %s already exists" % secret)
                        continue
                    with open(secret, "wb") as of:
                        of.write(self.decrypt(node, "data", self.file_key))
                else:
                    print("=> Skipping unknown type")
                    continue
                print(" => [%s]" % secret)

    def create_node(self, uid, content, description):
        if os.path.isfile(content):
            node_type = "zuul_secret.FileCredentialsImpl"
        else:
            node_type = "zuul_secrets.StringCredentialsImpl"
        node = self.creds.createElement(node_type)

        def createNode(tag, content):
            new_node = self.creds.createElement(tag)
            new_node.appendChild(self.creds.createTextNode(content))
            node.appendChild(new_node)
        createNode("id", uid)
        createNode("description", description if description else "")

        if os.path.isfile(content):
            createNode("fileName", os.path.basename(content))
            createNode("data", self.encrypt(open(content, "rb").read(),
                                            self.file_key))
        else:
            createNode("secret", self.encrypt(content, self.text_key))
        return node

    def create(self, uid, content, description):
        # check node doesn't already exists
        if self.get_node(uid):
            print("%s: already exists" % uid)
            return
        node = self.create_node(uid, content, description)
        self.get_nodes().appendChild(node)
        self.save()

    def update(self, uid, content, description):
        node = self.get_node(uid)
        if not node:
            print("%s: doesn't exist" % uid)
            return
        new_node = self.create_node(uid, content, description)
        self.get_nodes().removeChild(node)
        self.get_nodes().appendChild(new_node)
        self.save()

    def delete(self, uid):
        node = self.get_node(uid)
        if not node:
            print("%s: doesn't exist" % uid)
            return
        self.get_nodes().removeChild(node)
        self.save()


def main():
    args = usage()

    editor = JenkinsSecretEditor(args.secrets_dir)

    if args.action == 'create':
        editor.create(args.uid, args.content, args.description)
    elif args.action == 'read':
        editor.read(args.uid)
    elif args.action == 'update':
        editor.update(args.uid, args.content, args.description)
    elif args.action == 'delete':
        editor.delete(args.uid)


if __name__ == "__main__":
    main()
