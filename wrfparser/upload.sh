#!/bin/bash

repodir=$1
if [ "$repodir" == "" ] || ! [ -d $repodir ]; then
    echo "bad git repo dir $repodir"
    exit 1
fi

cd $repodir
git pull origin master
git add --all wrfparser/
git commit -m "forecasts pushed on `date`"
git push origin master
