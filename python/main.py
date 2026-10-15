from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

from recorder import Recorder


ui = WebUI()
recorder = Recorder()


def api_record():
    return recorder.start_record()


def api_stop_record():
    return recorder.stop_record()


def api_status():
    return recorder.status()


ui.expose_api("GET", "/api/record", api_record)
ui.expose_api("GET", "/api/stop_record", api_stop_record)
ui.expose_api("GET", "/api/status", api_status)


App.run()