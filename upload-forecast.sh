#!/bin/bash

git checkout current-forecast
./scrape.py --outfname _html/weather.html
git add _html/
git commit -m "forecast for `date`"
git push origin current-forecast
git checkout master
