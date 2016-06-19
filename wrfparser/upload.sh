#!/bin/bash

wrfdir=$PWD
# ./wrfparser.py
cd ~/psathyrella.github.io
git pull origin master
cp $wrfdir/*.html ~/psathyrella.github.io/wrfparser/
cp -r $wrfdir/images/processed/* ~/psathyrella.github.io/wrfparser/images/processed
git add wrfparser/*
git commit -m"new fcast"
git push origin master
