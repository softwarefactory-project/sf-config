%global  sum A demo-project

Name:    demo-project
Version: 0.0.1
Release: 1%{?dist}
Summary: %{sum}

License: ASL 2.0
URL:     https://demo-project.softwarefactory-project.io/
Source0: https://tarball.softwarefactory-project.io/demo-project-%{version}.tar.gz

BuildArch: noarch

BuildRequires: python-setuptools

%description
%{sum}

%prep
%autosetup -n demo-project-%{version}

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install --skip-build --root %{buildroot}

%files
%{python2_sitelib}/*

%changelog
* Tue Nov 14 2017 Demo User <demo@softwarefactory-project.io> - 0.0.1-1
- Initial packaging
