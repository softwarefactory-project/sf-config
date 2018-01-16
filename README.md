# DO NOT MERGE

# SFCONFIG - Software Factory configuration management

## Ansible roles components

Each roles can define a meta/sfconfig.py file to create a Component class:

* argparse() method can expose command line argument,
  example: see the --zuul-merger parameter

* prepare() method can validate role requirements and define global vars,
  example: see the zuul-launcher prepare that automatically adds the logserver
           role when needed

* configure() method can be used to generate complex role parameters:
** Call add_mysql_database() to set mysql role vars to create a database
** Call generate_ssh_keys() to create ssh keys
** Convert sfconfig.yaml settings into role variables
** Render convenient variable such as internal_url
