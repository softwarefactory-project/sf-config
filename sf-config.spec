%global         sum The Software Factory configuration sfconfig

Name:           sf-config
Version:        3.1.0
Release:        3%{?dist}
Summary:        %{sum}

License:        ASL 2.0
URL:            https://softwarefactory-project.io/r/p/%{name}
Source0:        https://github.com/softwarefactory-project/software-factory/archive/%{version}.tar.gz

# Disable automatic requirement because scl repos is installed by sfconfig/inventory.py
AutoReq: 0

BuildArch:      noarch

Conflicts:      epel-release

Requires:       python3-jinja2
Requires:       python3-requests
Requires:       python3-selinux
Requires:       python3-six
Requires:       python3-pyyaml
Requires:       iproute
Requires:       openssh
Requires:       openssl

Buildrequires:  python3-devel
Buildrequires:  python3-setuptools
Buildrequires:  python3-pbr

%description
%{sum}

%prep
%autosetup -n %{name}-%{version}

%build
export PBR_VERSION=%{version}
%{__python3} setup.py build

%install
# The sfconfig module
export PBR_VERSION=%{version}
%{__python3} setup.py install --skip-build --root %{buildroot}
# /etc/software-factory
install -p -D -m 0644 defaults/arch.yaml %{buildroot}%{_sysconfdir}/software-factory/arch.yaml
install -p -D -m 0644 defaults/sfconfig.yaml %{buildroot}%{_sysconfdir}/software-factory/sfconfig.yaml
install -p -D -m 0644 defaults/logo-favicon.ico %{buildroot}%{_sysconfdir}/software-factory/logo-favicon.ico
install -p -D -m 0644 defaults/logo-splash.png %{buildroot}%{_sysconfdir}/software-factory/logo-splash.png
install -p -D -m 0644 defaults/logo-topmenu.png %{buildroot}%{_sysconfdir}/software-factory/logo-topmenu.png
install -p -d -m 0755 %{buildroot}%{_sysconfdir}/software-factory/certs
# /usr/share/sf-config
install -p -d %{buildroot}%{_datarootdir}/sf-config
mv ansible defaults refarch scripts templates testinfra %{buildroot}%{_datarootdir}/sf-config/
# /var/
install -p -d -m 0700 %{buildroot}/var/log/software-factory
install -p -d -m 0755 %{buildroot}/var/lib/software-factory
install -p -d -m 0700 %{buildroot}/var/lib/software-factory/backup
install -p -d -m 0750 %{buildroot}/var/lib/software-factory/state
install -p -d -m 0750 %{buildroot}/var/lib/software-factory/versions
install -p -d -m 0700 %{buildroot}/var/lib/software-factory/sql
install -p -d -m 0755 %{buildroot}/var/lib/software-factory/git
install -p -d -m 0755 %{buildroot}/var/lib/software-factory/conf
# /usr/
install -p -d -m 0755 %{buildroot}/usr/libexec/software-factory
install -p -d -m 0750 %{buildroot}/usr/share/software-factory

%files
%license LICENSE
%{_bindir}/sf*
%{python3_sitelib}/sfconfig-%{version}-py*.egg-info
%{python3_sitelib}/sfconfig
%dir %attr(0750, root, root) %{_sysconfdir}/software-factory/
%dir %attr(0755, root, root) /var/lib/software-factory/
%dir %attr(0700, root, root) /var/lib/software-factory/backup
%dir %attr(0750, root, root) /var/lib/software-factory/state
%dir %attr(0750, root, root) /var/lib/software-factory/versions
%dir %attr(0700, root, root) /var/lib/software-factory/sql
%dir %attr(0755, root, root) /var/lib/software-factory/git
%dir %attr(0755, root, root) /var/lib/software-factory/conf
%dir %attr(0700, root, root) /var/log/software-factory
%dir %attr(0755, root, root) /usr/libexec/software-factory
%dir %attr(0750, root, root) /usr/share/software-factory
%config(noreplace) %{_sysconfdir}/software-factory/*
%{_datarootdir}/sf-config/

%pre
# Upgrade context
if [ $1 -gt 1 ]; then
  # Save the arch file in the rpm-state directory
  mkdir -p %{_localstatedir}/lib/rpm-state/%{name}/
  cp /etc/software-factory/arch.yaml %{_localstatedir}/lib/rpm-state/%{name}/arch.yaml
fi

%post
# Upgrade context
if [ $1 -gt 1 ]; then
  # Restore the arch file from the rpm-state directory
  cp %{_localstatedir}/lib/rpm-state/%{name}/arch.yaml /etc/software-factory/arch.yaml
fi

%changelog
* Tue Nov  5 2019  <user@tmacs> - 3.1.0-3
- Switch to python3

* Fri Dec 14 2018 Javier Peña <jpena@redhat.com> - 3.1.0-2
- Add missing dependencies on iproute, openssl and openssh

* Thu Oct  4 2018 Tristan Cacqueray <tdecacqu@redhat.com> - 3.1.0-1
- Add versions directory

* Tue Jul 10 2018 Fabien Boucher <fboucher@redhat.com> - 3.0.0-4
- Add dependency to PyYAML

* Fri Jun  1 2018 Fabien Boucher <fboucher@redhat.com> - 3.0.0-3
- Move sfconfig directories creation in packaging

* Fri Apr 27 2018 Nicolas Hicher <nhicher@redhat.com> - 3.0.0-2
- Add /var/log/software-factory directory creation

* Wed Feb  7 2018 Tristan Cacqueray <tdecacqu@redhat.com> - 3.0.0-1
- Bump version
- Add sf-graph-render command

* Tue Nov 21 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.7.0-3
- Require ansible >= 2.4.1

* Thu Oct 05 2017 Fabien Boucher <tdecacqu@redhat.com> - 2.7.0-2
- Make sure previous version of the arch.yaml is kept bypassing the
  rpm config style behavior.

* Tue Jul 18 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.7.0-1
- Refactor sfconfig into a python module

* Tue Jul 18 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.6.0-2
- Add /var/lib/software-factory/backup directory creation

* Mon Jul 03 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.6.0-1
- Symlink sfconfig.py and sfconfig to support smooth transition

* Fri Apr 14 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.5.0-1
- Initial packaging
