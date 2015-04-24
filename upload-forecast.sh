#!/bin/bash

git pull origin master
./scrape.py --no-history --outfname psathyrella.github.io/weatherscraper/weather.html
cd psathyrella.github.io
git add --all weatherscraper/
git commit -m "forecast for `date`"
git push origin master
