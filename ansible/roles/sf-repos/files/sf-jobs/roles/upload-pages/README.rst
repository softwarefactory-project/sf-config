Publish contents of ``{{ zuul.executor.work_root }}/pages/`` dir using
rsync over ssh to a remote fileserver that has previously been added to
the inventory by :zuul:role:`add-fileserver`.

The contents is published on the static webserver using a
Apache virtual host definition.

This uploads pages to a static webserver using SSH.

**Role Variables**

.. zuul:rolevar:: zuul_pagesserver_root
   :default: /var/www/pages/

   The root path to the pages on the static webserver.

.. zuul:rolevar:: zuul_pagesvhosts_root
   :default: /etc/httpd/pages.d/

   The root path where apache's vhost files are stored on the static webserver.

.. zuul:rolevar:: vhost_name

   The vhost name to use to fill the vhost template.

.. zuul:rolevar:: fqdn

   The fqdn to use to fill the vhost template.
