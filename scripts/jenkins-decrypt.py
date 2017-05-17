#!/bin/env python
# Decrypt jenkins secrets to a yaml file
# Inspired from http://thiébaud.fr/jenkins_credentials.html

from xml.dom.minidom import parse
import argparse
import os
import base64
import yaml

from hashlib import sha256
from Crypto.Cipher import AES


def main():
    p = argparse.ArgumentParser()
    p.add_argument("jenkins_dir")
    p.add_argument("--output")
    args = p.parse_args()

    def read(path):
        return open(os.path.join(args.jenkins_dir, path), "rb").read()
    try:
        master_key = read("secrets/master.key")
        hudson_file = read("secrets/hudson.util.Secret")
        file_file = read("secrets/org.jenkinsci.plugins.plaincredentials."
                         "impl.FileCredentialsImpl")
    except OSError:
        print("Couldn't read jenkins files")
        exit(2)

    credencial = os.path.join(args.jenkins_dir, "credentials.xml")

    hudson_key = AES.new(sha256(master_key).digest()[:16], AES.MODE_ECB).decrypt(
        hudson_file)[:16]
    file_key = AES.new(sha256(master_key).digest()[:16], AES.MODE_ECB).decrypt(
        file_file)[:16]

    creds = parse(credencial).getElementsByTagName(
        "java.util.concurrent.CopyOnWriteArrayList")[0]
    secrets = {}

    for node in creds.childNodes:
        if node.nodeType == node.TEXT_NODE:
            continue

        def get(tag):
            try:
                child = node.getElementsByTagName(tag)[0].firstChild
                if child is None:
                    return ""
                return child.data
            except:
                print("Couldn't decode %s" % node.toxml())
                raise

        def decrypt(tag, key=hudson_key):
            data = AES.new(key, AES.MODE_ECB).decrypt(
                base64.b64decode(get(tag)))
            if b"::::MAGIC::::" in data:
                data = data[:data.index(b"::::MAGIC::::")]
            elif data.endswith(b"\x08\x08\x08\x08\x08\x08\x08\x08"):
                data = data[:-8]
            return data

        secret_id = get("id")
        secret = {
            "description": get("description"),
            "type": node.tagName.split(".")[-1],
        }
        if secret_id in secrets:
            print("Secret id %s already defined", secret_id)
            exit(1)
        if secret["type"] == "StringCredentialsImpl":
            secret["secret"] = decrypt("secret").decode('utf-8')
        elif secret["type"] == "BasicSSHUserPrivateKey":
            print("Skipping ssh private key %s" % secret_id)
        elif secret["type"] == "FileCredentialsImpl":
            secret["fileName"] = get("fileName")
            secret["content"] = decrypt("data", key=file_key)
        elif secret["type"] == "UsernamePasswordCredentialsImpl":
            secret["username"] = get("username")
            secret["password"] = decrypt("password").decode('utf-8')
        else:
            print("Unknown type %s" % node.toxml())
            exit(1)
        secrets[secret_id] = secret

    yaml_str = yaml.dump(secrets, default_flow_style=False)
    if not args.output:
        print(yaml_str)
    else:
        open(args.output, "w").write(yaml_str)


if __name__ == "__main__":
    main()
