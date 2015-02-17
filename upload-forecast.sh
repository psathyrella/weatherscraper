#!/bin/bash

git pull origin master
./scrape.py --outfname psathyrella.github.io/weatherscraper/weather.html
cd psathyrella.github.io
git add weatherscraper/
git commit -m "forecast for `date`"
git push origin master
