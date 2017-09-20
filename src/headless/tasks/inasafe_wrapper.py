# coding=utf-8
import datetime
import logging
import os
import tempfile
import urlparse

from inasafe_cli.inasafe import (
    CommandLineArguments,
    run_impact_function,
    build_report,
    get_layer)
from headless.celery_app import app
from headless.celeryconfig import DEPLOY_OUTPUT_DIR, DEPLOY_OUTPUT_URL
from headless.tasks.utilities import download_layer, archive_layer, \
    generate_styles, download_file
from safe.utilities.keyword_io import KeywordIO

__author__ = 'Rizky Maulana Nugraha <lana.pcfre@gmail.com>'
__date__ = '1/19/16'

LOGGER = logging.getLogger('InaSAFE')


@app.task(queue='inasafe-headless-analysis')
def run_analysis(hazard, exposure, aggregation=None,
                 generate_report=False,
                 requested_extent=None):

    """Run analysis with a given combination

    Proxy tasks for celery broker. It is not actually implemented here.
    It is implemented in InaSAFE headless.tasks package

    :param hazard: hazard layer url
    :type hazard: str

    :param exposure: exposure layer url
    :type exposure: str

    :param aggregation: aggregation layer url
    :type aggregation: str

    :param generate_report: set True to generate pdf report
    :type generate_report: bool

    :param requested_extent: An extent of BBOX format list to denote the area
        of analysis. In CRS EPSG:4326
    :type requested_extent: list(float)

    :return: Impact layer url
    :rtype: str
    """
    hazard_file = download_layer(hazard)
    exposure_file = download_layer(exposure)
    aggregation_file = None
    if aggregation:
        aggregation_file = download_layer(aggregation)
    arguments = CommandLineArguments()
    arguments.hazard_path = hazard_file
    arguments.exposure_path = exposure_file
    arguments.aggregation_path = aggregation_file
    if requested_extent:
        arguments.extent = requested_extent

    # generate names for impact results
    # create date timestamp
    date_folder = datetime.datetime.now().strftime('%Y%m%d')
    deploy_dir = os.path.join(DEPLOY_OUTPUT_DIR, date_folder)
    try:
        os.mkdir(deploy_dir)
    except:
        pass

    # create temporary directory name
    tmp = tempfile.mkdtemp(dir=deploy_dir)
    arguments.output_dir = tmp
    status, msg, impact_function = run_impact_function(arguments)

    # if asked to generate report
    if generate_report:
        build_report(arguments, impact_function)

    # archiving the layer
    new_name = archive_layer(impact_function.impact.source())
    # new_name is a file path to archived layer
    # we need to return the url
    new_basename = os.path.basename(new_name)
    output_url = urlparse.urljoin(
        DEPLOY_OUTPUT_URL,
        '%s/%s/%s' % (date_folder, tmp, new_basename)
    )
    return output_url


@app.task(queue='inasafe-headless')
def read_keywords_iso_metadata(metadata_url, keyword=None):
    """Read xml metadata of a layer

    :param keyword: Can be string or tuple containing keywords to search for
    :type keyword: str, (str, )

    :return: the keywords, or a dictionary with key-value pair
    """
    filename = download_file(metadata_url, direct_access=True)
    keyword_io = KeywordIO()
    keywords = keyword_io.read_keywords_file(filename)
    if keyword:
        if isinstance(keyword, tuple) or isinstance(keyword, list):
            ret_val = {}
            for key in keyword:
                ret_val[key] = keywords.get(key, None)
            return ret_val
        else:
            return keywords.get(keyword, None)
    return keywords