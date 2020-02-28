#!/bin/bash

repodir=$1
if [ "$repodir" == "" ] || ! [ -d $repodir ]; then
    echo "bad git repo dir $repodir"
    exit 1
fi

echo "  pull/add/commit/push in $repodir"
# TODO need to add the branch orphaning or whatever to this so it happens automatically every 100 commits or whatever (currently the .git dir just gets bigger and bigger, and is like 70GB after a year)
cd $repodir
git pull --quiet origin master
git add --all wrfparser/
git commit --quiet -m "forecasts pushed on `date`"
git push --quiet origin master
