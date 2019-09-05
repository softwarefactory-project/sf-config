Prepare remote openshift workspaces

This role is intended to run once before any other role in a Zuul job.
This role requires the origin-clients to be installed.

It copies the prepared source repos to the pods' cwd.

**Role Variables**

.. zuul:rolevar:: openshift_pods
   :default: {{ zuul.resources }}

   The list of openshift pods to copy the source to.
