import uuid
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime

import httpx
from . import utility

ENDPOINT = "mapp-2019.taipower.com.tw"
BASIC_AUTH = "dHBlYy13U1pvLTVDNjZTZG84ZzM6X1UyVlpZd05kWi1hTW9ILV9fZlctZ3ROR0lwVmgydy4="
APP_VERSION = "3.0.6"

_LOGGER = logging.getLogger(__name__)

@dataclass
class TaipowerTokens:
    access_token: str
    refresh_token: str
    expiration: float


class TaipowerConnection:
    """Connecting to Taipower API.

    Parameters
    ----------
    account : str
        User phone number.
    password : str
        User password.
    taipower_tokens : TaipowerTokens, optional
        If taipower_tokens is given, it is used by request;
        otherwise, a login procedure is performed to obtain new taipower_tokens,
        by default None.
    proxy : str, optional
        Proxy setting. Format:"IP:port", by default None. 
    print_response : bool, optional
        If set, all responses of httpx will be printed, by default False.
    """

    def __init__(self, account, password, taipower_tokens=None, proxy=None, print_response=False):
        self._login_response = None
        self._account = account
        self._password = password
        self._print_response = print_response
        self._proxies = {'http': proxy, 'https': proxy} if proxy else None

        if taipower_tokens:
            self._taipower_tokens = taipower_tokens
        else:
            conn_status, self._taipower_tokens = self.login()
            if conn_status != "OK":
                raise RuntimeError(f"An error occurred when signing into Taipower API: {conn_status}")

    def _generate_headers(self, token_type="bearer"):
        auth = f"Bearer {self._taipower_tokens.access_token}" if token_type == "bearer" else f"Basic {BASIC_AUTH}"
        headers = {
            "Accept": "*",
            "Authorization": auth,
            "User-Agent": "Mozilla/5.0 ( compatible )"
        }
        return headers
    
    def _handle_response(self, response):
        response_json = response.json()
        
        if response.status_code == httpx.codes.ok:    
            return "OK", response_json
        else:
            return f"{response_json['error']}", response_json
    
    def _send(self, api_name, json=None):
        req = httpx.post(
            f"https://{ENDPOINT}/{api_name}",
            headers=self._generate_headers(),
            json=json,
            proxies=self._proxies,
        )
        if self._print_response:
            self.print_response(req)

        message, response_json = self._handle_response(req)

        return message, response_json

    def login(self, use_refresh_token=False):
        """Login API.

        Parameters
        ----------
        use_refresh_token : bool, optional
            Whether or not to use TaipowerTokens.refresh_token to login. 
            If TaipowerTokens is not provided, fallback to email and password, by default False

        Returns
        -------
        (str, TaipowerTokens)
            (status, Taipower tokens).
        """

        if use_refresh_token and self._aws_tokens != None:
            login_json_data = {
                "refresh_token": self._taipower_tokens.refresh_token,
                "grant_type": "refresh_token",
            }
        else:
            login_json_data = {
                "username": self._account,
                "password": utility.des_encrypt(self._password),
                "grant_type": "password",
                "scope": "tpec",
                "device_id": str(uuid.uuid4()),
                "appVersion": APP_VERSION,
            }
        
        login_headers = self._generate_headers(token_type="basic")

        login_req = httpx.post(
            f"https://{ENDPOINT}/oauth/token",
            data=login_json_data,
            headers=login_headers,
            proxies=self._proxies,
        )

        if self._print_response:
            self.print_response(login_req)
        
        status, response = self._handle_response(login_req)

        taipower_tokens = None
        if status == "OK" and response["token_type"] == "bearer":
            taipower_tokens = TaipowerTokens(
                access_token = response['access_token'],
                refresh_token = self._taipower_tokens.refresh_token if use_refresh_token else response['refresh_token'],
                expiration = time.time() + response['expires_in'],
            )
        return status, taipower_tokens
    
    def get_data(self):
        raise NotImplementedError
    
    def print_response(self, response):
        print('===================================================')
        print(self.__class__.__name__, 'Response:')
        print('headers:', response.headers)
        print('status_code:', response.status_code)
        print('text:', json.dumps(response.json(), indent=True))
        print('===================================================')


class GetMember(TaipowerConnection):
    """API internal endpoint.
    
    Parameters
    ----------
    account : str
        User phone number.
    password : str
        User password.
    """

    def __init__(self, account, password, **kwargs):
        super().__init__(account, password, **kwargs)

    def get_data(self):
        return self._send("member/getData")


class GetAMIBill(TaipowerConnection):
    """API internal endpoint.
    
    Parameters
    ----------
    account : str
        User phone number.
    password : str
        User password.
    """

    def __init__(self, account, password, **kwargs):
        super().__init__(account, password, **kwargs)
    
    def get_data(self, electric_number: str):
        json_data = {
            "phoneNo": self._account,
            "deviceId": "",
            "customNo": electric_number,
        }
        return self._send(f"api/home/bills", json_data)


class GetAMI(TaipowerConnection):
    """API internal endpoint.
    
    Parameters
    ----------
    account : str
        User phone number.
    password : str
        User password.
    """

    def __init__(self, account, password, **kwargs):
        super().__init__(account, password, **kwargs)
    
    def get_data(self, time_period: str, datetime: datetime, electric_number: str):
        if time_period == "hour":
            time_text = "date"
            time_rep = datetime.strftime("%Y%m%d") # YYYYMMDD
        elif time_period == "daily":
            time_text = "yearMonth"
            time_rep = datetime.strftime("%Y%m") # YYYYMM
        elif time_period == "monthly":
            time_text = "year"
            time_rep = datetime.strftime("%Y") # YYYY
        elif time_period == "quater":
            time_text = "date"
            time_rep = datetime.strftime("%Y%m%d") # YYYYMMDD
        else:
            raise ValueError("time_period accepts either `hour`, `daily`, `monthly`, or `quater`.")

        json_data = {
            "custNo": electric_number,
            time_text: time_rep
        }
        return self._send(f"api/ami/{time_period}", json_data)


class GetBillRecords(TaipowerConnection):
    """API internal endpoint.
    
    Parameters
    ----------
    account : str
        User phone number.
    password : str
        User password.
    """

    def __init__(self, account, password, **kwargs):
        super().__init__(account, password, **kwargs)
    
    def get_data(self, electric_number : str):
        json_data = {
            "customNo": electric_number,
        }
        return self._send("api/mybill/records", json_data)