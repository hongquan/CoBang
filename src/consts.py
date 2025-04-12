from enum import StrEnum, IntEnum


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


class ScannerState(IntEnum):
    IDLE = 0
    SCANNING = 1
    NO_RESULT = 2
    WIFI_FOUND = 3
    URL_FOUND = 4
    TEXT_FOUND = 5


GST_SOURCE_NAME = 'webcam_source'
GST_FLIP_FILTER_NAME = 'videoflip'
GST_SINK_NAME = 'widget_sink'
GST_APP_SINK_NAME = 'app_sink'

SUPPORTED_DEVICE_SOURCES = ('v4l2src',)
