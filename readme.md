## weather for the mountains

Pull the forecasts from NDFD and write an html summary file:

  `./scrape.py --outfname _html/weather.html`

To add a location, edit `all-locations.csv`.

The current forecast should be displayed [here](http://htmlpreview.github.io/?https://github.com/psathyrella/weatherscraper/blob/current-forecast/_html/weather.html).

## credit

This is pretty much just [lost in the mountains](http://lost-in-the-mountains.com/washington_climbing.php), but with temperature, wind, and precipitation.

## links:
snow depth:
http://www.nohrsc.noaa.gov/nsa/reports.html?region=Northwest&var=snowdepth&dy=2014&dm=12&dd=24&units=e&sort=value&filter=0

24h snowfall
http://www.nohrsc.noaa.gov/nsa/reports.html?region=Northwest&var=snowfall&dy=2014&dm=12&dd=24&units=e&sort=value&filter=0

mcdc data tools
http://www.ncdc.noaa.gov/cdo-web/datatools

ncdc map page
https://gis.ncdc.noaa.gov/map/viewer/#app=cdo

aviation forecast for wa airports:
http://www.usairnet.com/cgi-bin/launch/code.cgi?Submit=Go&sta=KBVS&state=WA

forecast for skagit regional airport
http://www.usairnet.com/cgi-bin/launch/code.cgi?Submit=Go&sta=KBVS&state=WA

gfs cloudbase
http://www.weatheronline.co.uk/cgi-bin/expertcharts?MODELL=gfs&MODELLTYP=1&VAR=lclb&INFO=1

nwac snow climatology
http://data.nwac.us/CLISNO/CLISNO.TXT
