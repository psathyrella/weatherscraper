#!/usr/bin/env python
# helps a bit: convert tmp.png -morphology erode:1 square:1 m.png

import Image
import os
import csv
import sys
import glob
from subprocess import check_call, CalledProcessError
import datetime
import calendar
import pytesseract
import argparse

titles = {
    '3-hour-precip' : 'precip in previous 3 hours',
    '24-hour-precip' : 'precip in previous 24 hours',
    'surface-temp' : 'surface temperature',
    '10m-wind-speed' : '10m wind speed'
}

expected_date_format = ('hours', 'tz', 'weekday', 'monthday', 'month', 'year')
def convert_dateinfo(dateinfo):
    dateinfo['hours'] = int(dateinfo['hours'].replace('O', '0').replace('l', '1'))
    dateinfo['monthday'] = int(dateinfo['monthday'])
    dateinfo['year'] = 2000 + int(dateinfo['year'])

side_indices = {'left' : 0, 'right' : 1, 'top' : 2, 'bottom' : 3}
base_margins = {  # (left, right, top, bottom)
    'full' : (0, 0, 0, 0),
    'entire-date-line' : (0, 0, 21, 855),
    'right-legend' : (850, 3, 100, 70)
}
specific_margins = {
    'washington' : {
        'date' : (653, 123, 21, 855),
        'full-date' : (643, 5, 21, 855),
        'howe-to-chehalis' : (175, 550, 175, 650),
        'cascades' : (310, 415, 250, 300)
    },
    'western-washington' : {
        'date' : (630, 123, 21, 855),
        'full-date' : (630, 5, 21, 855),
        'cascades' : (550, 70, 120, 200)
    }
}
# ----------------------------------------------------------------------------------------
def get_margins(maptype):
    margins = base_margins.copy()
    margins.update(specific_margins[maptype])
    return margins
    
paste_sizes = {
    'washington' : (175, 460),
    'western-washington' : (280, 604)
}
# rescale_pixels = {
#     'full-date' : (150, 20)
# }

paste_positions = {
    'washington' : {
        'date' : (0, 0),
        'howe-to-chehalis' : (0, 28),
        'cascades' : (0, 107)
    },
    'western-washington' : {
        'full-date' : (0, 0),
        'cascades' : (0, 30)
    }
}

base_url = 'http://www.atmos.washington.edu/wrfrt/data/timeindep'
base_outdir = 'images'
domain_codes = {
    '1.33km' : 'd4',
    '4km' : 'd3',
    '12km' : 'd2',
    '36km' : 'd1'
}
maptype_codes = {
    'washington' : 'wa',
    'western-washington' : 'ww'
}
variable_codes = {
    '3-hour-precip' : 'pcp3',
    '24-hour-precip' : 'pcp24',
    'surface-temp' : 'tsfc',
    '10m-wind-speed' : 'wssfc2'
}
expected_hours = {
    '12km' : {
        '24-hour-precip' : [h for h in range(24, 180, 12)],
        'surface-temp' : [h for h in range(24, 180, 12)],
        '10m-wind-speed' : [h for h in range(24, 180, 12)]
    },
    '4km' : {
        '3-hour-precip' : [h for h in range(6, 84, 3) if h != 3],
        'surface-temp' : [h for h in range(6, 84, 3) if h != 3],
        '10m-wind-speed' : [h for h in range(6, 84, 3) if h != 3]
    },
    '1.33km' : {
        '3-hour-precip' : [h for h in range(6, 72, 3) if h != 3],
        'surface-temp' : [h for h in range(6, 72, 3) if h != 3],
        '10m-wind-speed' : [h for h in range(6, 72, 3) if h != 3]
    }
}

final_image_params = {
    'margin' : 10,
    'columns' : 10
}

htmlheader = """<!DOCTYPE html>
<html>
<body style="background-color:black;">
"""
htmlfooter = """</body>
</html>
"""

# ----------------------------------------------------------------------------------------
def get_subimage(img, rname, margins):
    tmpco = {side : margins[rname][iside] for side, iside in side_indices.items()}
    width, height = img.size
    bbox = (tmpco['left'], tmpco['top'], width - tmpco['right'], height - tmpco['bottom'])
    subimg = img.crop(bbox)
    # if rname in rescale_pixels:
    #     subimg = subimg.resize(rescale_pixels[rname])
    return subimg

# ----------------------------------------------------------------------------------------
def get_url(domain, maptype, variable, hour):
    return base_url + '/images_' + domain_codes[domain] + '/' + maptype_codes[maptype] + '_' + variable_codes[variable] + '.' + ('%02d' % hour) + '.0000.gif'

# ----------------------------------------------------------------------------------------
def get_legend_fname(maptype, variable):
    if 'precip' in variable:
        variable_category = 'precip'
    elif 'temp' in variable:
        variable_category = 'temp'
    elif 'wind' in variable:
        variable_category = 'wind'
    else:
        assert False

    legend_dir = 'legends/' + maptype  # *relative* path
    legendfname = variable_category + '.svg'
    if not os.path.exists(args.outdir + '/' + legend_dir):
        os.makedirs(args.outdir + '/' + legend_dir)
    check_call(['cp', '-v', wrfdir + '/' + legend_dir + '/' + legendfname, args.outdir + '/' + legend_dir + '/' + legendfname])

    return legend_dir + '/' + legendfname

# ----------------------------------------------------------------------------------------
def get_fname(domain, maptype, variable, hour, processed=False):
    # NOTE this is the *relative* path, used for links
    outpath = base_outdir
    suffix = 'gif'
    if processed:
        outpath += '/processed'
        suffix = 'png'
    outpath += '/' + domain + '/' + maptype + '/' + variable + '/' + str(hour) + '.' + suffix
    return outpath

# ----------------------------------------------------------------------------------------
def download_image(domain, maptype, variable, hour):
    outfname = args.outdir + '/' + get_fname(domain, maptype, variable, hour)
    if not os.path.exists(os.path.dirname(outfname)):
        os.makedirs(os.path.dirname(outfname))
    url = get_url(domain, maptype, variable, hour)
    try:
        check_call(['wget', '-O', outfname, url])
    except CalledProcessError:
        os.remove(outfname)

# ----------------------------------------------------------------------------------------
def download_all_images(domain, maptype, variable):
    for hour in expected_hours[domain][variable]:
        download_image(domain, maptype, variable, hour)

# ----------------------------------------------------------------------------------------
def join_image_pieces(subimages, maptype):
    # joined_image = Image.new("RGB", (subimages['cascades'].size[0], subimages['cascades'].size[1] + subimages['date'].size[1]))
    joined_image = Image.new("RGB", paste_sizes[maptype])
    for name, ppos in paste_positions[maptype].items():
        joined_image.paste(subimages[name], ppos)
    return joined_image

# ----------------------------------------------------------------------------------------
def run_tesseract(img):
    return_str = pytesseract.image_to_string(img)
    # tmptiff = '/tmp/tmp-date-image.tiff'
    # tmptxt = '/tmp/tmp-date-image'
    # img.save(tmptiff)
    # check_call(['tesseract', tmptiff, tmptxt])
    # with open(tmptxt + '.txt') as txtfile:
    #     return_str = txtfile.read()
    # os.remove(tmptiff)
    # os.remove(tmptxt + '.txt')
    print return_str
    return return_str

# ----------------------------------------------------------------------------------------
def get_single_date(img):
    datestr = run_tesseract(img)
    pdtlist = datestr[datestr.find('(') + 1 : datestr.find(')')].replace('\'', '').split()
    dateinfo = {}
    for ifmt in range(len(expected_date_format)):
        dateinfo[expected_date_format[ifmt]] = pdtlist[ifmt]
    convert_dateinfo(dateinfo)
    imonth = list(calendar.month_abbr).index(dateinfo['month'])
    return datetime.datetime(dateinfo['year'], imonth, dateinfo['monthday'], dateinfo['hours'])

# ----------------------------------------------------------------------------------------
def set_dates(imgfo):
    first_fcast_hour, first_datetime = None, None  # first fcast hour and its corresponding date
    for iimg in range(len(imgfo)):
        if first_datetime is None:
            first_datetime = get_single_date(imgfo[iimg]['subimages']['entire-date-line'])
            first_fcast_hour = imgfo[iimg]['fcast-hour']
        imgfo[iimg]['datetime'] = first_datetime + datetime.timedelta(hours=(imgfo[iimg]['fcast-hour'] - first_fcast_hour))
        # print imgfo[iimg]['fcast-hour'], imgfo[iimg]['datetime'].weekday()

# ----------------------------------------------------------------------------------------
def dummy_image():
    return Image.new("RGB", (10, 10))

# ----------------------------------------------------------------------------------------
def get_fcast_image_info(domain, maptype, variable, hour):
    fname = args.outdir + '/' + get_fname(domain, maptype, variable, hour)
    if os.path.exists(fname):
        pass
        # print '  already exists: %s' % fname
    else:
        print '  downloading %s' % fname
        download_image(domain, maptype, variable, hour)
    margins = get_margins(maptype)
    if os.path.exists(fname):
        img = Image.open(fname)
        subimages = {sname : get_subimage(img, sname, margins) for sname in margins}
        final_image = join_image_pieces(subimages, maptype)
    else:
        final_image = dummy_image()
        subimages = {sname : dummy_image() for sname in margins}

    # # print subimage sizes
    # for si in subimages:
    #     print '%40s %3d %3d' % (si, subimages[si].size[0], subimages[si].size[1])
    # sys.exit()

    # # write individual subimage
    # subimages['right-legend'].save('tmp.png')
    # sys.exit()

    processed_fname = args.outdir + '/' + get_fname(domain, maptype, variable, hour, processed=True)
    if not os.path.exists(os.path.dirname(processed_fname)):
        os.makedirs(os.path.dirname(processed_fname))
    final_image.save(processed_fname)

    return {'fcast-hour' : hour, 'fname' : processed_fname, 'subimages' : subimages}

# ----------------------------------------------------------------------------------------
def join_fcasts(domain, maptype, variable):
    imgfo = []
    for hour in expected_hours[domain][variable]:
        imgfo.append(get_fcast_image_info(domain, maptype, variable, hour))  # if it fails, for whatever reason, it'll put in a dummy image
    set_dates(imgfo)

    return imgfo

# ----------------------------------------------------------------------------------------
def get_htmlfname(domain, variable):
    return args.outdir + '/' + domain + '_' + variable + '.html'

# ----------------------------------------------------------------------------------------
def reverse_htmlfname(fname):
    return os.path.basename(fname).replace('.html', '').split('_')

# ----------------------------------------------------------------------------------------
def get_links():
    fnames = sorted(glob.glob('*.html'))
    links = []
    last_domain = None
    for fname in fnames:
        domain, variable = reverse_htmlfname(fname)
        linkstr = '<a href="' + fname + '"><font size=3>' + variable.replace('-', ' ') + '</font></a>'
        if last_domain is None or domain != last_domain:
            linkstr = '<font color=white>' + domain + ': </font>' + linkstr
        if last_domain is not None and domain != last_domain:
            linkstr = '<br>\n' + linkstr
        links.append(linkstr)
        last_domain = domain
    return links

# ----------------------------------------------------------------------------------------
def write_index_html(fname):
    with open(fname, 'w') as htmlfile:
        htmlfile.write(htmlheader)
        for link in get_links():
            htmlfile.write(link + '\n')
        htmlfile.write(htmlfooter)

# ----------------------------------------------------------------------------------------
def add_linkstrs(fname):
    with open(fname) as htmlfile:
        lines = htmlfile.readlines()
    with open(fname, 'w') as htmlfile:
        for line in lines:
            if '<body' in line:
                # htmlfile.write('<center>\n')
                for link in get_links():
                    htmlfile.write(link + '\n')
                # htmlfile.write('</center>\n')
                htmlfile.write('<br>\n<br>\n')
            htmlfile.write(line)

# ----------------------------------------------------------------------------------------
def write_html(domain, maptype, variable):
    imgfo = join_fcasts(domain, maptype, variable)
    htmlfname = get_htmlfname(domain, variable)
    # if not os.path.exists(os.path.dirname(htmlfname)):
    #     os.makedirs(os.path.dirname(htmlfname))
    with open(htmlfname, 'w') as htmlfile:
        htmlfile.write(htmlheader)
        htmlfile.write('<center><font color=red size=4>%s</font></center><br><br>\n' % titles[variable])
        last_weekday = None
        for ifn in range(len(imgfo)):
            if variable == '24-hour-precip' and imgfo[ifn]['datetime'].hour == 5:
                continue
            if domain != '12km' and last_weekday is not None and imgfo[ifn]['datetime'].weekday() != last_weekday:
                htmlfile.write('<br>\n')
            last_weekday = imgfo[ifn]['datetime'].weekday()
            htmlfile.write('<img href="' + imgfo[ifn]['fname'] + '" src="' + imgfo[ifn]['fname'] + '", width="150">\n')
        htmlfile.write('<br>\n')
        htmlfile.write('<center><img src="' + get_legend_fname(maptype, variable) + '", width="' + ('500' if 'wind' in variable else '350') + '"></center>\n')
        htmlfile.write(htmlfooter)

# ----------------------------------------------------------------------------------------
wrfdir = os.path.dirname(os.path.realpath(__file__))
parser = argparse.ArgumentParser()
parser.add_argument('--outdir', required=True)
parser.add_argument('--config-fname', default=wrfdir + '/config.csv')
args = parser.parse_args()

stuff_to_run = []
with open(args.config_fname) as cfgfile:
    reader = csv.DictReader(row for row in cfgfile if not row.startswith('#'))
    for line in reader:
        stuff_to_run.append(line)

for line in stuff_to_run:
    print line['domain'], line['variable']
    # download_all_images(line['domain'], line['maptype'], line['variable'])
    write_html(line['domain'], line['maptype'], line['variable'])

for line in stuff_to_run:
    add_linkstrs(get_htmlfname(line['domain'], line['variable']))

write_index_html(args.outdir + '/index.html')
