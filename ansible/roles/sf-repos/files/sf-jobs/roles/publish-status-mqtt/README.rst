Publish build status to a MQTT message queue

This role publishes basic information about a build to a MQTT message queue. It
is intended to be used at the beginning of *pre* and *post* playbooks.

The information is formatted in JSON, and has the following keys:

* branch
* build
* buildset
* change
* change_url
* executor_hostname
* job
* jobtags
* newrev
* oldrev
* patchset
* pipeline
* project
* projects
* ref
* status
* tag
* tenant
* timeout
* voting

More details on these specific fields can be found in Zuul's documentation:
https://docs.openstack.org/infra/zuul/user/jobs.html#var-zuul

The *status* field can have the following values depending on when the role is
executed:

* START if run in a *pre* playbook
* SUCCESS or FAILURE if run in a *post* playbook, depending on the value of
  *zuul_success*

**Role Variables**

.. zuul:rolevar:: mqtt_server
   :default: None

   The MQTT server to which data will be published.

.. zuul:rolevar:: mqtt_username
   :default: None

   The username to use to authenticate on the MQTT service.

.. zuul:rolevar:: mqtt_password
   :default: None

   The password to use for authentication.

.. zuul:rolevar:: mqtt_topic
   :default: zuul/{{ zuul.tenant }}/{{ zuul.project.name }}/{{ zuul.pipeline }}/{{ zuul.job }}

   The topic under which data will be published.
