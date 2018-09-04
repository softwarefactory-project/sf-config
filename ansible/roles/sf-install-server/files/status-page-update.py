# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Load history data using:
# for i in $(seq 14 -1 0); do
#  python status-page-update.py --output /var/www/status/index.html \
#    --lib /var/lib/software-factory/backup/status_history.yaml \
#    --now $(python -c "import datetime; print((datetime.datetime.utcnow() -
#            datetime.timedelta(days=$i)).strftime('%Y-%m-%d'))");
# done

import argparse
import datetime
import yaml

import pymysql


HTML_DOM = """<!DOCTYPE html>
<html>
  <head>
    <title>Status page</title>
    <meta charset='UTF-8'>
    <link rel='stylesheet' type='text/css'
          href='/static/patternfly/css/patternfly.min.css' />
    <link rel='stylesheet' type='text/css'
          href='/static/patternfly/css/patternfly-additions.min.css' />
    <style>
    .body {top: 52px;}
    </style>
  </head>
  <body>
    <nav class="navbar navbar-default navbar-pf" role="navigation">
      <ul class="nav navbar-nav navbar-primary">
        <li class="active"><a href="./">Status</a></li>
        <li><a href="/grafana">Grafana</a></li>
        <li><a href="/prometheus">Prometheus</a></li>
      </ul>
    </nav>
    <div class="container" style='width: 100%'>
      <div class="list-group list-view-pf list-view-pf-view">
        BODY
      </div>
    </div>
    <script src='/static/js/jquery.min.js'></script>
    <script src='/static/bootstrap/js/bootstrap.min.js'></script>
    <script src='/static/patternfly/js/patternfly.min.js'></script>
    <script>
      $(".list-group-item-header").click(function(event){
        if(!$(event.target).is("button, a, input, .fa-ellipsis-v")){
          $(this).find(".fa-angle-right").toggleClass("fa-angle-down")
            .end().parent().toggleClass("list-view-pf-expand-active")
            .find(".list-group-item-container").toggleClass("hidden");
          }
      })
      $(".list-group-item-container .close").on("click", function (){
        $(this).parent().addClass("hidden")
               .parent().removeClass("list-view-pf-expand-active")
               .find(".fa-angle-right").removeClass("fa-angle-down");
      })
    </script>
  </body>
</html>
"""


def table(dom, columns, rows):
    dom.append(
        "<table style='white-space: nowrap; margin: 0px' "
        "class='table table-condensed table-responsive table-bordered'>"
    )
    if columns:
        dom.append("<thead><tr>")
        for col in columns:
            dom.append("<th>%s</th>" % col)
        dom.append("</tr></thead>")
    dom.append("<tbody>")
    for row in rows:
        if columns and len(row) > len(columns):
            dom.append("<tr id='%s'>" % row.pop())
        else:
            dom.append("<tr>")
        for col in row:
            dom.append("<td>%s</td>" % col)
        dom.append("</tr>")
    dom.append("</tbody></table><br />")


class StatusPage:
    columns = [
        "zuul_build.uuid",
        "zuul_buildset.pipeline",
        "zuul_build.job_name",
        "zuul_buildset.project",
        "zuul_build.result",
        "zuul_build.log_url",
        "zuul_build.end_time",
        "zuul_buildset.tenant",
    ]

    def connect(self):
        secrets = yaml.safe_load(open(
            "/var/lib/software-factory/ansible/group_vars/all.yaml"))
        return pymysql.connect(
            host=secrets["zuul_mysql_host"],
            user=secrets["zuul_mysql_user"],
            password=secrets["zuul_mysql_password"],
            db='zuul',
            cursorclass=pymysql.cursors.DictCursor)

    def update(self, now):
        status = {
            'date': now,
            'jobs': {}
        }
        yesterday = now - datetime.timedelta(days=1)
        with self.connect().cursor() as cursor:
            cursor.execute(
                "SELECT %s FROM zuul_build "
                "INNER JOIN zuul_buildset "
                "ON zuul_build.buildset_id=zuul_buildset.id "
                "WHERE zuul_build.start_time > %s "
                "AND zuul_build.start_time <= %s" %
                (",".join(self.columns), "%s", "%s"), (yesterday, now))
            status["jobs"]["count"] = cursor.rowcount
            for build in cursor.fetchall():
                status["jobs"].setdefault(build["tenant"], 0)
                status["jobs"][build["tenant"]] += 1
                if build["result"] == "SUCCESS":
                    continue
                if build["result"] == "NODE_FAILURE" or \
                   (build["pipeline"] != "check" and
                   "openstack" not in build["pipeline"]):
                    status.setdefault("tenants", {}).setdefault(
                        build["tenant"], []).append(build)
        return status

    def renderStatus(self, status, expanded):
        expand = " hidden"
        list_expand = ""
        angle = ""
        if expanded:
            expand = ""
            angle = " fa-angle-down"
            list_expand = " list-view-pf-expand-active"

        statusInfo = []

        # jobs has global count and tenant's counts,
        # remove 1 to get tenant number
        active_tenant = len(status["jobs"]) - 1

        # Global summary
        columns = ["tenant", "job executed", "job anomaly"]
        active_tenant = 0
        rows = []
        for tenant, jobs in sorted(status["jobs"].items()):
            if tenant == "count":
                continue
            active_tenant += 1
            failures = 0
            if tenant in status.get("tenants", {}):
                failures = len(status["tenants"][tenant])
            rows.append((tenant, jobs, failures))
        if rows:
            table(statusInfo, columns, rows)

        bugs = 0
        for tenant, failures in sorted(status.get("tenants", {}).items()):
            bugs += len(failures)
            statusInfo.append("<h3>%s anomalous jobs</h3>" % tenant)
            columns = list(filter(
                lambda x: x != "tenant",
                map(lambda x: x.split('.')[-1], self.columns)))
            rows = []
            for failure in failures:
                row = []
                for column in columns:
                    value = failure[column]
                    if column == "log_url":
                        value = "<a href='%s'>logs</a>" % (value)
                    elif column == "uuid":
                        value = "<a href='/zuul/t/%s/build/%s'>%s</a>" % (
                            tenant, value, value[:7])
                    row.append(value)
                rows.append(row)
            table(statusInfo, columns, rows)

        return ("""
        <div class="list-group-item{list_expand}">
          <div class="list-group-item-header">
            <div class="list-view-pf-expand">
              <span class="fa fa-angle-right{angle}"></span>
            </div>
            <div class="list-view-pf-main-info">
              <div class="list-view-pf-body">
                <span class="pficon pficon-info list-view-pf-icon-sm"></span>
                <div class="list-view-pf-description">
                  <div class="list-group-item-heading">
                    &nbsp;&nbsp;{date}
                  </div>
                </div>
                <div class="list-view-pf-additional-info">
                  <div class="list-view-pf-additional-info-item">
                    <span class="fa fa-bug"></span>
                    <strong>{bugs}</strong> bugs
                  </div>
                  <div class="list-view-pf-additional-info-item">
                    <span class="pficon pficon-registry"></span>
                    <strong>{jobs}</strong> jobs
                  </div>
                  <div class="list-view-pf-additional-info-item">
                    <span class="pficon pficon-users"></span>
                    <strong>{tenant}</strong> tenants
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="list-group-item-container container-fluid{expand}">
            <div class="close"><span class="pficon pficon-close"></span></div>
            <div>
                  {status}
            </div>
          </div>
        </div>""".format(
          expand=expand,
          angle=angle,
          list_expand=list_expand,
          date=status["date"].strftime("%Y-%m-%d (%a)"),
          jobs=status["jobs"].get("count", 0),
          tenant=active_tenant,
          bugs=bugs,
          status="\n".join(statusInfo)))

    def render(self, history):
        expanded = True
        first = True
        body = []
        for status in history:
            jobs = status["jobs"].get("count", 0)
            if first or jobs:
                body.append(self.renderStatus(status, expanded and jobs))
                if jobs:
                    expanded = False
            first = False
        return HTML_DOM.replace('BODY', "\n".join(body))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", default=datetime.datetime.utcnow())
    parser.add_argument("--dry", action="store_true",
                        help="Do not update history")
    parser.add_argument("--lib", help="a yaml file to store history")
    parser.add_argument("--output", help="a html file to write status page")
    args = parser.parse_args()
    history = []
    if args.lib:
        try:
            with open(args.lib) as fileobj:
                history = yaml.safe_load(fileobj)
        except IOError:
            pass

    if not isinstance(args.now, datetime.datetime):
        args.now = datetime.datetime.strptime(args.now, "%Y-%m-%d")
    status = StatusPage()
    if not args.dry:
        history = [status.update(args.now)] + history
    if args.output:
        open(args.output, "w").write(status.render(history))
    else:
        print(history[0])

    if args.lib:
        with open(args.lib, "w") as fileobj:
            yaml.safe_dump(
                history[:60], fileobj, default_flow_style=False)


if __name__ == "__main__":
    main()
