// @licstart  The following is the entire license notice for the
// JavaScript code in this page.
//
// Copyright 2017 Red Hat
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.
//
// @licend  The above is the entire license notice
// for the JavaScript code in this page.

angular.module('zuulDashboard', []).controller('mainController', function($scope, $http, $location, $window) {
    $scope.formdata = {'limit': 50};

    $scope.rowClassRuns = function(run) {
        if (run.result == "SUCCESS") {
            return "success";
        } else {
            return "warning";
        }
    };
    $scope.rowClassJobs = function(job) {
        if (job.last_success_time > job.last_failure_time) {
            return "success";
        } else {
            return "warning";
        }
    };

    $scope.ShowJobList = function () {
        $scope.jobInfo = undefined;
        // Fetch job list
        $http.get("/manage/v2/jobs/?order_by=last_run&desc=true&limit=" + $scope.formdata.limit)
            .then(function success(result) {
                for (job_pos = 0; job_pos < result.data.results.length; job_pos += 1) {
                    job = result.data.results[job_pos];
                    job.last_success_start = Date.parse(job.last_success.start_time);
                    job.last_success_id = job.last_success.id;
                    job.last_failure_start = Date.parse(job.last_failure.start_time);
                    job.last_failure_id = job.last_failure.id;
                    job.last_run_start = Date.parse(job.last_run.start_time);
                    job.last_run_id = job.last_run.id;
                }
                $scope.jobsList = result.data.results
            });
    }
    $scope.ShowJobBuilds = function (job) {
        $scope.jobsList = undefined;
        $http.get("/manage/v2/builds/?desc=true&limit=" + $scope.formdata.limit + "&job_name=" + job["name"])
            .then(function success(result) {
                for (run_pos = 0; run_pos < result.data.results.length; run_pos += 1) {
                    run = result.data.results[run_pos]
                    if (run.change > 0) {
                        run.change_url = "/r/#/c/" + run.change + "/" + run.patchset;
			run.change_id = run.change + "," + run.patchset;
                    } else {
                        run.change_url = "/r/gitweb?p=" + run.repository + ".git;a=commit;h=" + run.ref;
			run.change_id = run.ref.substr(0, 7);
                    }
                    run.duration = (Date.parse(run.end_time) / 1000) - (Date.parse(run.start_time) / 1000);
                    if (run.node_name == null) {
                        run.node_name = 'master'
                    }
                }
                $scope.jobInfo = result.data;
                $scope.jobInfo.name = job["name"]
            });
    }
    $scope.ShowJobList();
});
