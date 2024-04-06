#!/bin/bash

repodir=$1
if [ "$repodir" == "" ] || ! [ -d $repodir ]; then
    echo "bad git repo dir $repodir"
    exit 1
fi
reponame=`basename $repodir`  # psathyrella.github.io
if [ "$reponame" != "psathyrella.github.io" ]; then
    echo "error: wrong repo name $reponame (should be psathyrella.github.io)"
    exit 1
fi

echo "    pull/add/commit/push in $repodir"

echo "    cd $repodir"
cd $repodir

echo "    pulling (log in pull.log)"
git pull --quiet origin master >pull.log
git checkout --orphan tmp-branch
git add --all wrfparser/  # Add all files and commit them
git commit --quiet -m "forecasts pushed on `date`"
git branch -D master  # Deletes the master branch
git branch -m master  # Rename the current branch to master
git push --quiet -f origin master  # Force push master branch to github
# git gc --aggressive --prune=all     # remove the old files

cd .. #$OLDPWD
if [ -d repo.bak/$reponame ]; then
    rm -rf repo.bak/$reponame
fi
mv $reponame repo.bak/
git clone --quiet git@github.com:psathyrella/$reponame
