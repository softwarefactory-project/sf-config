%global         sum The Software Factory configuration sfconfig

Name:           sf-config
Version:        3.0.0
Release:        1%{?dist}
Summary:        %{sum}

License:        ASL 2.0
URL:            https://softwarefactory-project.io/r/p/%{name}
Source0:        https://github.com/softwarefactory-project/software-factory/archive/%{version}.tar.gz

BuildArch:      noarch

Requires:       ansible >= 2.4.1
Requires:       python-jinja2

Buildrequires:  python2-devel
Buildrequires:  python-setuptools
Buildrequires:  python2-pbr

%description
%{sum}

%prep
%autosetup -n %{name}-%{version}

%build
export PBR_VERSION=%{version}
%{__python2} setup.py build

%install
# The sfconfig module
export PBR_VERSION=%{version}
%{__python2} setup.py install --skip-build --root %{buildroot}
# /etc/software-factory
install -p -D -m 0644 defaults/arch.yaml %{buildroot}%{_sysconfdir}/software-factory/arch.yaml
install -p -D -m 0644 defaults/sfconfig.yaml %{buildroot}%{_sysconfdir}/software-factory/sfconfig.yaml
install -p -D -m 0644 defaults/logo-favicon.ico %{buildroot}%{_sysconfdir}/software-factory/logo-favicon.ico
install -p -D -m 0644 defaults/logo-splash.png %{buildroot}%{_sysconfdir}/software-factory/logo-splash.png
install -p -D -m 0644 defaults/logo-topmenu.png %{buildroot}%{_sysconfdir}/software-factory/logo-topmenu.png
# /usr/share/sf-config
install -p -d %{buildroot}%{_datarootdir}/sf-config
mv ansible defaults refarch scripts templates testinfra %{buildroot}%{_datarootdir}/sf-config/
# /var/lib/software-factory/backup
install -p -d -m 0700 %{buildroot}/var/lib/software-factory/backup

%files
%{_bindir}/sf*
%{python2_sitelib}/sfconfig-%{version}-py*.egg-info
%{python2_sitelib}/sfconfig
%dir %attr(0750, root, root) %{_sysconfdir}/software-factory/
%dir %attr(0700, root, root) /var/lib/software-factory/backup
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
