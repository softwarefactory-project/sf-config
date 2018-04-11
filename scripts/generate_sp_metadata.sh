#!/bin/sh

# Adapted from https://github.com/UNINETT/mod_auth_mellon/blob/master/mellon_create_metadata.sh

set -e

ENTITYID="$1"
BASEURL="$2"
CERT_FILE="$3"

CERT="$(grep -v '^-----' "$CERT_FILE")"

cat >/etc/httpd/saml2/mellon_metadata.xml <<EOF
<EntityDescriptor entityID="$ENTITYID" xmlns="urn:oasis:names:tc:SAML:2.0:metadata" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
  <SPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <KeyDescriptor use="signing">
      <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ds:X509Data>
          <ds:X509Certificate>$CERT</ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </KeyDescriptor>
    <SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect" Location="$BASEURL/logout"/>
    <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="$BASEURL/postResponse" index="0"/>
  </SPSSODescriptor>
</EntityDescriptor>
EOF

umask 0777
chmod go+r /etc/httpd/saml2/mellon_metadata.xml
