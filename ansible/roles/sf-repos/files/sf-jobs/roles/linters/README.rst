Runs linters for a project

**Role Variables**

.. zuul:rolevar:: linters
   :default: [flake8,doc8,bashate,yamllint,ansible-lint,golint]

   List of linters to execute.

.. zuul:rolevar:: ansible_lint_roles_dir

   Set this variable to the Ansible roles directory.
