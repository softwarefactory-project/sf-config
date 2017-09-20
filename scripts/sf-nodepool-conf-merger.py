#!/usr/bin/env python

import os
import sys
import yaml


def yaml_merge_load(inp):
    paths = []
    for root, dirs, files in os.walk(inp, topdown=True):
        paths.extend([os.path.join(root, path) for path in files])

    # Keeps only .yaml files
    paths = filter(lambda x: x.endswith('.yaml') or x.endswith('.yml'), paths)

    user = {}
    for path in paths:
        data = yaml.safe_load(open(path))
        if not data:
            continue
        for key, value in data.items():
            user.setdefault(key, []).append(value)
    return user


def merge(inp, _nodepool):
    if os.path.isfile(inp):
        user = yaml.safe_load(open(inp))
    elif os.path.isdir(inp):
        user = yaml_merge_load(inp)
    else:
        raise RuntimeError("%s: unknown source" % inp)
    conf = yaml.safe_load(open(_nodepool))
    user = yaml.safe_load(open(inp))

    if "rh-python35" in _nodepool:
        cache_dir = "/var/opt/rh/rh-python35/cache/nodepool"
    else:
        cache_dir = "/var/cache/nodepool"

    for provider in user['providers']:
        if inp.endswith("nodepool.yaml"):
            # This syntax is nodepool2 only
            for image in provider['images']:
                image['private-key'] = '/var/lib/nodepool/.ssh/id_rsa'
        if not provider.get("image-type"):
            provider["image-type"] = "raw"

    for dib in user['diskimages']:
        envvars = dib.setdefault('env-vars', {})
        envvars['TMPDIR'] = "%s/dib_tmp" % cache_dir
        envvars['DIB_IMAGE_CACHE'] = "%s/dib_cache" % cache_dir
        envvars['DIB_GRUB_TIMEOUT'] = '0'
        envvars['DIB_CHECKSUM'] = '1'
        # Make sure env-vars are str
        for k, v in envvars.items():
            if not isinstance(v, basestring):
                envvars[k] = str(v)

    if 'cron' in user:
        conf['cron'] = user['cron']
    conf['labels'] = user['labels']
    conf['providers'] = user['providers']
    conf['diskimages'] = user['diskimages']
    return yaml.dump(conf, default_flow_style=False)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("usage: %s src dest" % sys.argv[0])
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2]
    _nodepool = "%s/_nodepool.yaml" % os.path.dirname(out)
    for reqfile in (_nodepool, inp):
        if not os.path.isfile(reqfile):
            print("%s: missing file" % reqfile)
            sys.exit(1)
    merged = merge(inp, _nodepool)
    open(out, 'w').write(merged)
