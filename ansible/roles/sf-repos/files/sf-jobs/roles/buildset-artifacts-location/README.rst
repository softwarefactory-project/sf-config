Return the location of buildset artifacts

When a 'buildset' directory exists in the job logs, then use
zuul_return to set buildset_artifacts_url for children jobs.

rpm-build job:
* Create a repository
* Fetch the repository to "{{ zuul.executor.log_root }}/buildset"
* Use the buildset-artifacts-location role

rpm-test jobs:
* Install "{{ buildset_artficats_url }}" yum repository
* Run integration tests

.. code-block:: yaml

  layout:
    jobs:
      - rpm-build
      - rpm-test1:
          dependencies:
            - rpm-build
      - rpm-test2:
          dependencies:
            - rpm-build


**Role Variables**

.. zuul:rolevar:: zuul_log_url

   Base URL where logs are to be found.
