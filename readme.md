## weather for the mountains

To pull forecasts from NDFD and mountain-forecast.com and synthesize the info into plots:

    ./scrape.py --outfname _html/weather.html

While to pull the gifs from the UW WRF page and chop them up into something a little easier to view:

    ./wrfparser/wrfparser.py --outdir _html/wrfparser

Or, just look at the current forecast [plots](http://psathyrella.github.io/weatherscraper/weather.html) and [maps](http://psathyrella.github.io/wrfparser/4km_3-hour-precip.html).

Weatherscraper is free software under the GPL v3.

## inspiration

Started with the [lost in the mountains](http://lost-in-the-mountains.com/washington_climbing.php) location list.
