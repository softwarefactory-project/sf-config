#!/bin/bash -e

# The /dev/./urandom is not a typo. https://stackoverflow.com/questions/58991966/what-java-security-egd-option-is-for
JAVA_OPTIONS="-Djava.security.egd=file:/dev/./urandom"

if [ -f /var/gerrit/logs/.run_init ]; then
    echo "Initializing Gerrit site ..."
    java ${JAVA_OPTIONS} -jar /var/gerrit/bin/gerrit.war init -d /var/gerrit --batch --no-auto-start --skip-plugins
    java ${JAVA_OPTIONS} -jar /var/gerrit/bin/gerrit.war reindex -d /var/gerrit
    echo "Installing the plugins ..."
    unzip -jo /var/gerrit/bin/gerrit.war WEB-INF/plugins/* -d /var/gerrit/plugins
    for plugin in /var/gerrit-plugins/*; do
        cp -uv $plugin /var/gerrit/plugins/
    done
    rm -f /var/gerrit/logs/.run_init
fi

echo "Running Gerrit ..."
exec java ${JAVA_OPTIONS} -jar /var/gerrit/bin/gerrit.war daemon -d /var/gerrit
