#!/bin/bash

git pull origin master
./scrape.py --outfname psathyrella.github.io/weatherscraper/weather.html

cd _history
git add --all .
git commit -m "forecast for `date`"
git push origin master
cd ..

cd psathyrella.github.io
git add --all weatherscraper/
git commit -m "forecast for `date`"
git push origin master
cd ..
