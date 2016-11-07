#!/bin/bash

repodir=$1
if [ "$repodir" == "" ] || ! [ -d $repodir ]; then
    echo "bad git repo dir $repodir"
    exit 1
fi

echo "  pull/add/commit/push in $repodir"
cd $repodir
git pull --quiet origin master
git add --all wrfparser/
git commit --quiet -m "forecasts pushed on `date`"
git push --quiet origin master
