Upload ansible content to galaxy

**Role Variables**

.. zuul:rolevar:: galaxy_info

   Complex argument which contains the information about the Galaxy
   server as well as the authentication information needed. It is
   expected that this argument comes from a `Secret`.

  .. zuul:rolevar:: github_token

     GitHub Token to log in to Galaxy.

  .. zuul:rolevar:: github_username
     :default: First component of the project name

     GitHub Username.

  .. zuul:rolevar:: api_server
     :default: The built-in ansible-galaxy default for the production api server.

     The API server destination.

.. zuul:rolevar:: galaxy_project_name
   :default: Second component of the project name

   The GitHub project name.
