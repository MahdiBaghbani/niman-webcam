import time
import logging
import requests


class StorageApi:
    def __init__(
        self,
        endpoint: str,
        access_token: str,
        request_timeout: int,
        retry_max_attempts: int,
        retry_delay_seconds: int,
    ):
        self.endpoint: str = endpoint
        self.request_timeout: int = request_timeout
        self.retry_max_attempts: int = retry_max_attempts
        self.retry_delay_seconds: int = retry_delay_seconds

        self.headers = dict(access_token=access_token)

        self.log_module = "STORAGE:API"

    def upload(self, name: str, serialized_image: str) -> bool:
        print("upload")
        is_successful: bool = False

        # upload image with retry mechanism.
        for attempt in range(1, self.retry_max_attempts):
            logging.debug(f"{self.log_module}:{name}: trying attempt: {attempt}")

            try:
                response: requests.Response = requests.post(
                    f"{self.endpoint}/upload",
                    headers=self.headers,
                    json={"name": name, "data": serialized_image},
                    timeout=self.request_timeout,
                )
                response.raise_for_status()

            except requests.exceptions.HTTPError as err:
                logging.warning(
                    f"{self.log_module}:{name}: uploading camera image {err}"
                )
                time.sleep(self.retry_delay_seconds)

            except requests.exceptions.ConnectionError as err:
                logging.warning(
                    f"{self.log_module}:{name}: uploading camera image {err}"
                )
                time.sleep(self.retry_delay_seconds)

            except requests.exceptions.Timeout as err:
                logging.warning(
                    f"{self.log_module}:{name}: uploading camera image {err}"
                )
                time.sleep(self.retry_delay_seconds)

            except requests.exceptions.RequestException as err:
                logging.warning(
                    f"{self.log_module}:{name}: uploading camera image {err}"
                )
                time.sleep(self.retry_delay_seconds)

            else:
                logging.info(f"{self.log_module}:{name}: upload successful")
                is_successful = True
                break

        if not is_successful:
            logging.error(f"{self.log_module}:{name}: upload failed")

        return is_successful
