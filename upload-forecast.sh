#!/bin/bash

./wrfparser/wrfparser.py --outdir psathyrella.github.io/wrfparser

./scrape.py --outfname psathyrella.github.io/weatherscraper/weather.html

cd _history
git add --all .
git commit -m "forecast for `date`"
git push origin master
cd ..


cd psathyrella.github.io
git pull origin master
git add --all weatherscraper/
git add --all wrfparser/
git commit -m "forecast for `date`"
git push origin master
cd ..
