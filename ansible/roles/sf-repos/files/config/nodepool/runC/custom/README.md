Place your playbooks for creating custom containers or customizing
existing ones in this directory.

In order to work with Zuul, they must include "_create_zuul_worker_user.yaml" or
at least perform similar tasks:

* create a zuul-worker user with the correct uid
* add Zuul's key to zuul-worker's authorized_keys
* create the "src" directory in zuul-worker's home directory
