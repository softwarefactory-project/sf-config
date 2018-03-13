This roles build static web content to ``{{ pages_build_dir }}``.
It supports Sphinx and Pelican content and default to a bare
copy of the source to the build directory if specific content
type has not been detected.

**Role Variables**

.. zuul:rolevar:: pages_build_dir
   :default: "pages-artifacts/"

   Directory where pages artifacts will be build.
