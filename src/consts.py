from enum import StrEnum


SHORT_NAME = 'cobang'
BRAND_NAME = 'CoBang'
APP_ID = 'vn.hoabinh.quan.CoBang'


class JobName(StrEnum):
    SCANNER = 'scanner'
    GENERATOR = 'generator'


class ScanSourceName(StrEnum):
    WEBCAM = 'webcam'
    IMAGE = 'image'


class WebcamPageLayoutName(StrEnum):
    REQUESTING = 'webcam-requesting'
    AVAILABLE = 'webcam-available'
    UNAVAILABLE = 'webcam-unavailable'


GST_SOURCE_NAME = 'webcam_source'
GST_FLIP_FILTER_NAME = 'videoflip'
GST_SINK_NAME = 'widget_sink'
GST_APP_SINK_NAME = 'app_sink'
