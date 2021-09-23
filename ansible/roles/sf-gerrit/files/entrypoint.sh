#!/bin/bash -e

if [ ! -d /var/gerrit/git/All-Projects.git ] || [ "$1" == "init" ]; then
    echo "Initializing Gerrit site ..."
    java $JAVA_OPTS -jar /var/gerrit/bin/gerrit.war init \
         -d /var/gerrit --batch --no-auto-start --skip-plugins
    java $JAVA_OPTS -jar /var/gerrit/bin/gerrit.war reindex -d /var/gerrit
fi

if [ ! -f /var/gerrit/plugins/download-commands.jar ]; then
    echo "Extract plugins for gerrit.war for they were present in pkg"
    mkdir /tmp/gerrit
    cd /tmp/gerrit
    unzip /var/gerrit/bin/gerrit.war
    mv WEB-INF/plugins/*jar /var/gerrit/plugins/
    cd && rm -rf /tmp/gerrit
fi

if [ "$1" != "init" ]; then
    echo "Reindex Gerrit ..."
    java $JAVA_OPTS -jar /var/gerrit/bin/gerrit.war reindex -d /var/gerrit
    echo "Running Gerrit ..."
    exec /var/gerrit/bin/gerrit.sh run
fi
