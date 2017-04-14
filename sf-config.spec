%global         sum The Software Factory configuration sfconfig

Name:           sf-config
Version:        2.5.0
Release:        1%{?dist}
Summary:        %{sum}

License:        ASL 2.0
URL:            https://softwarefactory-project.io/r/p/%{name}
Source0:        https://github.com/softwarefactory-project/software-factory/archive/%{version}.tar.gz

BuildArch:      noarch

Requires:       ansible
Requires:       python-jinja2

%description
%{sum}

%prep
%autosetup -n %{name}-%{version}

%build

%install
# The sfconfig.py
install -p -D -m 0755 scripts/sfconfig.py %{buildroot}%{_bindir}/sfconfig.py
# retro compat until 2.5.0 is released
install -p -D -m 0755 scripts/yaml-merger.py %{buildroot}/usr/local/bin/yaml-merger.py
# /etc/software-factory
install -p -D -m 0644 defaults/arch.yaml %{buildroot}%{_sysconfdir}/software-factory/arch.yaml
install -p -D -m 0644 defaults/sfconfig.yaml %{buildroot}%{_sysconfdir}/software-factory/sfconfig.yaml
install -p -D -m 0644 defaults/logo-splash.png %{buildroot}%{_sysconfdir}/software-factory/logo-splash.png
install -p -D -m 0644 defaults/logo-topmenu.png %{buildroot}%{_sysconfdir}/software-factory/logo-topmenu.png
# /usr/share/sf-config
install -p -d %{buildroot}%{_datarootdir}/sf-config
mv ansible config-repo defaults refarch scripts templates %{buildroot}%{_datarootdir}/sf-config/

%files
/usr/local/bin/yaml-merger.py
%{_bindir}/sfconfig.py
%dir %attr(0750, root, root) %{_sysconfdir}/software-factory/
%config(noreplace) %{_sysconfdir}/software-factory/*
%{_datarootdir}/sf-config/

%changelog
* Fri Apr 14 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.5.0-1
- Initial packaging
