%global         sum The Software Factory configuration sfconfig

Name:           sf-config
Version:        2.7.0
Release:        1%{?dist}
Summary:        %{sum}

License:        ASL 2.0
URL:            https://softwarefactory-project.io/r/p/%{name}
Source0:        https://github.com/softwarefactory-project/software-factory/archive/%{version}.tar.gz

BuildArch:      noarch

Requires:       ansible
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
%{_bindir}/sfconfig
%{python2_sitelib}/sfconfig-%{version}-py*.egg-info
%{python2_sitelib}/sfconfig
%dir %attr(0750, root, root) %{_sysconfdir}/software-factory/
%dir %attr(0700, root, root) /var/lib/software-factory/backup
%config(noreplace) %{_sysconfdir}/software-factory/*
%{_datarootdir}/sf-config/

%changelog
* Tue Jul 18 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.7.0-1
- Refactor sfconfig into a python module

* Tue Jul 18 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.6.0-2
- Add /var/lib/software-factory/backup directory creation

* Mon Jul 03 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.6.0-1
- Symlink sfconfig.py and sfconfig to support smooth transition

* Fri Apr 14 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.5.0-1
- Initial packaging
