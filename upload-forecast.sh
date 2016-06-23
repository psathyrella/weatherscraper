#!/bin/bash

# git pull origin master
./scrape.py --outfname psathyrella.github.io/weatherscraper/weather.html

cd _history
git add --all .
git commit -m "forecast for `date`"
git push origin master
cd ..

./wrfparser/wrfparser.py --outdir psathyrella.github.io/wrfparser

cd psathyrella.github.io
git pull origin master
git add --all weatherscraper/
git commit -m "forecast for `date`"
git push origin master
cd ..
