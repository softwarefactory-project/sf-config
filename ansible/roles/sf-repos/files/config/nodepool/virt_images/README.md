# Virt-customize based nodepool image

This directory contains nodepool image built using virt-customize-dib elements.

To use a playbook, add this to a nodepool yaml file:

```yaml
diskimages:
  - name: cloud-fedora-rawhide
    python-path: /usr/bin/python3
    dib-cmd: /usr/bin/dib-virt-customize /etc/nodepool/virt_images/cloud-fedora-rawhide.yaml
```
