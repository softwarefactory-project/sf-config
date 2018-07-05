// @licstart  The following is the entire license notice for the
// JavaScript code in this page.
//
// Copyright 2016 Red Hat
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

// Fancy tooltips
$(document).ready(function(){
    $('[data-toggle="tooltip"]').tooltip();
});

angular.module('sfWelcome', []).controller('mainController', function($scope, $http, $location) {
    $scope.host = $location.protocol() + "://" + $location.host();
    $scope.hide = true;
    $scope.dlimit = 5;
    $http.get('/manage/v2/resources').
        success(function(data) {
            $scope.Projects = data['resources']['projects'];
            angular.forEach($scope.Projects, function(project, key) {
                new_sr = [];
                angular.forEach(project['source-repositories'], function(sr, key) {
                    if (!('private' in sr[Object.keys(sr)[0]] && sr[Object.keys(sr)[0]]['private'])) {
                        new_sr.push(Object.keys(sr)[0]);
                    }
                })
                project['source-repositories'] = new_sr;
            })
            $scope.Repos = data['resources']['repos'];
        })
});
