#!/bin/bash

reponame=psathyrella.github.io
defbranch=display

repodir=`realpath $1`
if [ "$repodir" == "" ] || ! [ -d $repodir ]; then
    echo "bad git repo dir $repodir"
    exit 1
fi
if ! [ -d $repodir/.git ]; then
    echo "no .git in repo dir $repodir (probably should clone by hand using command below)"
    exit 1
fi

if [ "`basename $repodir`" != $reponame ]; then
    echo "error: wrong repo name `basename $repodir` (should be $reponame)"
    exit 1
fi

echo "    pull/add/commit/push in $repodir"
cd $repodir

git pull --quiet origin $defbranch
git checkout --orphan tmp-branch
git add --all wrfparser/  # Add all files and commit them
git commit --quiet -m "forecasts pushed on `date`"
git branch -D $defbranch  # Deletes the $defbranch branch
git branch -m $defbranch  # Rename the current branch to $defbranch
git push --quiet -f origin $defbranch  # Force push $defbranch branch to github
# git gc --aggressive --prune=all     # remove the old files

cd .. #$OLDPWD
if [ -d repo.bak/$reponame ]; then
    rm -rf repo.bak/$reponame
fi
mv $reponame repo.bak/
git clone --quiet git@github.com:psathyrella/$reponame
