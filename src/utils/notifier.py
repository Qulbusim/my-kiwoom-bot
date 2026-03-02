from datetime import datetime

import requests


class Discord:
    def __init__(self, url):
        self.url = url
        self.is_valid_url = True
        self.check_url()

    def check_url(self):
        if not(isinstance(self.url, str) and self.url.startswith(("http://", "https://")) and "." in self.url):
            self.is_valid_url = False

    def send_msg(self, message: str):
        if self.is_valid_url:
            message = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}"
            requests.post(self.url, json = {"content" : message})