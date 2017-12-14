Return the location of buildset artifacts

When a 'buildset' directory exists in job logs, then
use zuul_return to set buildset_artifacts_url for
children jobs.

**Role Variables**

.. zuul:rolevar:: zuul_log_url

   Base URL where logs are to be found.
