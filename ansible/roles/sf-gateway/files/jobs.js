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
    $scope.rowClassRuns = function(run) {
        if (run.result == "SUCCESS") {
            return "success";
        } else {
            return "warning";
        }
    };
    $scope.rowClassJobs = function(job) {
//        if (job.status == "SUCCESS") {
            return "success";
/*        } else {
            return "warning";
        }*/
    };

    $scope.ShowJobList = function () {
        $scope.jobInfo = undefined;
        // Fetch job list
        $http.get("/manage/api/v2/jobs/")
            .then(function success(result) {
                $scope.jobsList = result.data.results
            });
    }
    $scope.ShowJob = function (job) {
        $scope.jobsList = undefined;
        $http.get("/manage/api/v2/builds/?job_name=" + job["name"])
            .then(function success(result) {
                for (run_pos = 0; run_pos < result.data.results.length; run_pos += 1) {
                    run = result.data.results[run_pos]
                    if (run.change > 0) {
                        run.change_url = "/r/#/c/" + run.change + "/" + run.patchset;
                    } else {
                        run.change_url = "/r/gitweb?p=" + run.project + ".git;a=commit;h=" + run.ref;
                    }
                    if (run.node_name == null) {
                        run.node_name = 'master'
                    }
                }
                $scope.jobInfo = result.data;
            });
    }
    $scope.ShowJobList();
});
