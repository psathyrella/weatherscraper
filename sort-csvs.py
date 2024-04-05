#!/usr/bin/env python
import csv
import sys
import glob
import datetime

dirname = '/home/dralph/Dropbox/tmp/weatherscraper/history/noaa'

for fname in glob.glob(dirname + '/*.csv'):
    print fname
    dates = []
    ininfo = {}
    with open(fname) as infile:
        reader = csv.DictReader(infile)
        for line in reader:
            date = datetime.date(int(line['year']), int(line['month']), int(line['day']))
            ininfo[date] = line
            dates.append(date)
            # if len(dates) > 10:
            #     break
    dates.sort()
    with open(fname, 'w') as outfile:
        writer = csv.DictWriter(outfile, reader.fieldnames)
        writer.writeheader()
        for date in dates:
            writer.writerow(ininfo[date])
    # sys.exit()
