%global         sum The Software Factory configuration sfconfig

Name:           sf-config
Version:        2.6.0
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
export PBR_VERSION=%{version}
%{__python2} setup.py build

%install
export PBR_VERSION=%{version}
%{__python2} setup.py install --skip-build --root %{buildroot}
# Backward compatible sfconfig.py
ln -s %{_bindir}/sfconfig %{buildroot}%{_bindir}/sfconfig.py
sed -i 's#^import sys$#import sys; sys.path.insert(0, "/usr/lib/python2.7/site-packages/")#'  %{buildroot}%{_bindir}/sfconfig
# /etc/software-factory
install -p -D -m 0644 defaults/arch.yaml %{buildroot}%{_sysconfdir}/software-factory/arch.yaml
install -p -D -m 0644 defaults/sfconfig.yaml %{buildroot}%{_sysconfdir}/software-factory/sfconfig.yaml
install -p -D -m 0644 defaults/logo-favicon.ico %{buildroot}%{_sysconfdir}/software-factory/logo-favicon.ico
install -p -D -m 0644 defaults/logo-splash.png %{buildroot}%{_sysconfdir}/software-factory/logo-splash.png
install -p -D -m 0644 defaults/logo-topmenu.png %{buildroot}%{_sysconfdir}/software-factory/logo-topmenu.png
# /usr/share/sf-config
install -p -d %{buildroot}%{_datarootdir}/sf-config
mv ansible config-repo defaults refarch scripts templates %{buildroot}%{_datarootdir}/sf-config/

%files
%{python2_sitelib}/*
%{_bindir}/sfconfig*
%dir %attr(0750, root, root) %{_sysconfdir}/software-factory/
%config(noreplace) %{_sysconfdir}/software-factory/*
%{_datarootdir}/sf-config/

%changelog
* Mon Jul 03 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.6.0-1
- Switch to real python module
- Add sfconfig command

* Fri Apr 14 2017 Tristan Cacqueray <tdecacqu@redhat.com> - 2.5.0-1
- Initial packaging
