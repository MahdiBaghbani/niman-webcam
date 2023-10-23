import os
import cv2
import time
import base64
import logging
import threading
import requests
import screeninfo
import tkinter as tk

# this is used to register avif format do not remove!
import pillow_avif

# trace segmentation fault errors.
import faulthandler

from os import path
from io import BytesIO
from pathlib import Path
from PIL import ImageTk, Image
from datetime import datetime, timezone, timedelta
from imutils.video import VideoStream, WebcamVideoStream

# type annotations.
from typing import Optional


def camera_resize(cv2_image, width, height):
    return Image.fromarray(
        cv2.resize(cv2_image, (width, height), interpolation=cv2.INTER_NEAREST)
    )


class NimanWebcam:
    class Program:
        """Program metadata"""

        name = "Niman Webcam"
        version = "0.1.0"
        author = "Mahdi Baghbani"
        name_version = name + " " + version

    class Default:
        """Program constants"""

        # default values.
        camera_delay: int = 2
        camera_delay_range: range = range(100)
        image_quality: int = 65
        image_quality_range: range = range(35, 100)

    def __init__(
        self,
        tk_app: Optional[tk.Tk] = None,
        title: str = "application",
        use_relative_path: bool = True,
        api_enabled: bool = False,
        api_endpoint: str = "https://niman.api",
        api_request_timeout: int = 5,
        api_retry_max_attempts: int = 10,
        api_retry_delay_seconds: int = 2,
        images_dir: str = "images",
        image_quality: int = 65,
        image_optimize: bool = True,
        camera_delay_seconds: int = 1,
        log_file: str = "niman_camera.log",
        log_level: str = "info",
        log_enable_fault_handler: bool = False,
    ):
        self.parent_dir = path.abspath(path.dirname(__file__))
        if use_relative_path:
            # construct absolute paths paths.
            log_file = path.join(self.parent_dir, log_file)

        # set log level.
        if log_level == "critical":
            self.log_level = logging.CRITICAL
        elif log_level == "error":
            self.log_level = logging.ERROR
        elif log_level == "warning":
            self.log_level = logging.WARNING
        elif log_level == "debug":
            self.log_level = logging.DEBUG
        else:
            self.log_level = logging.INFO

        # logging settings.
        logging.basicConfig(
            filename=log_file,
            filemode="a+",
            format="%(asctime)s : %(name)s - %(levelname)s - %(message)s",
            datefmt="%d-%b-%y %H:%M:%S",
            level=self.log_level,
        )

        logging.info(f"INIT:PROGRAM: init Niman Camera App with name {title}")
        # trace program calls.
        if log_enable_fault_handler:
            logging.debug("INIT:PACKAGES:FAULT_HANDLER: enabling ...")
            faulthandler.enable()
            logging.debug("INIT:PACKAGES:FAULT_HANDLER: enabled")

        logging.debug(
            f"INIT:PACKAGES:AVIF: AVIF plugin version is {pillow_avif.__version__}"
        )

        # set API endpoint.
        self.api_enabled: bool = api_enabled
        self.api_endpoint: str = api_endpoint
        self.api_request_timeout: int = api_request_timeout
        self.api_retry_max_attempts: int = api_retry_max_attempts + 1
        self.api_retry_delay_seconds: int = api_retry_delay_seconds

        # get all monitors.
        self.monitors = screeninfo.get_monitors()

        # monitor width and height.
        self.window_primary_width: int = 400
        self.window_primary_height: int = 300

        # select primary monitor.
        for monitor in self.monitors:
            if monitor.is_primary:
                self.window_primary_width = monitor.width
                self.window_primary_height = monitor.height

        # creating camera recorder.
        self.camera_stream: WebcamVideoStream = VideoStream(src=0).start()

        # warm up camera before starting the program.
        time.sleep(2.0)

        self.camera_image_quality: int = image_quality
        self.camera_image_optimize: bool = image_optimize

        # internal variable.
        self._camera_image_quality: int = NimanWebcam.Default.image_quality

        # camera capture settings.
        self.camera_capture_flag: bool = False
        self.camera_capture_timestamp: datetime = datetime.now(
            timezone.utc
        ) - timedelta(seconds=camera_delay_seconds)
        self.camera_capture_minimum_delay_in_seconds: int = camera_delay_seconds

        # internal variable.
        self._camera_capture_minimum_delay_in_seconds: int = (
            NimanWebcam.Default.camera_delay
        )

        # get camera dimensions.
        camera_height, camera_width, _ = self.camera_stream.read().shape

        # set window width, height based on image shape to avoid distorted picture.
        # TODO: check against the actual size of monitor and also calculate the aspect ratio of
        # picture to adjust window size based on monitor size.
        self.window_primary_width = camera_width
        self.window_primary_height = camera_height

        # construct absolute paths paths.
        self.images_dir: str = (
            path.join(self.parent_dir, images_dir)
            if use_relative_path
            else images_dir
        )
        # create directories, if not exists.
        Path(self.images_dir).mkdir(parents=True, exist_ok=True)

        self.tk_app: tk.Tk

        # app.
        if tk_app:
            self.tk_app = tk_app
        else:
            self.tk_app = tk.Tk()

        self.window_primary = self.tk_app

        # set window properties.
        self.window_primary.title(title)
        self.window_primary.geometry(
            f"{self.window_primary_width}x{self.window_primary_height}"
        )
        self.window_primary.minsize(
            self.window_primary_width, self.window_primary_height
        )
        self.window_primary.maxsize(
            self.window_primary_width, self.window_primary_height
        )

        # constructing frames.
        self.frame_pack = tk.LabelFrame(
            self.window_primary,
            bg="white",
            width=float(self.window_primary_width),
            height=float(self.window_primary_height),
        )
        self.frame_camera = tk.Frame(
            self.frame_pack,
            bg="white",
            width=float(self.window_primary_width),
            height=float(self.window_primary_height),
        )

        # displaying grid.
        self.frame_pack.grid(row=0, sticky="nsew")
        self.frame_camera.grid(row=0, sticky="nsew")

        # place label into label frame.
        self.label_camera = tk.Label(self.frame_camera)
        self.label_camera.place(x=0, y=0)

        # Bind the Enter Key to Call an event
        self.window_primary.bind("<Return>", self._camera_capture)

    @property
    def camera_capture_minimum_delay_in_seconds(self):
        return self._camera_capture_minimum_delay_in_seconds

    @camera_capture_minimum_delay_in_seconds.setter
    def camera_capture_minimum_delay_in_seconds(self, seconds):
        self._camera_capture_minimum_delay_in_seconds = (
            seconds
            if seconds in NimanWebcam.Default.camera_delay_range
            else NimanWebcam.Default.camera_delay
        )

    @property
    def camera_image_quality(self):
        return self._camera_image_quality

    @camera_image_quality.setter
    def camera_image_quality(self, quality):
        self._camera_image_quality = (
            quality
            if quality in NimanWebcam.Default.image_quality_range
            else NimanWebcam.Default.image_quality
        )

    def _camera_capture(self, _) -> None:
        self.camera_capture_flag = True

    def camera_play(self) -> None:
        frame = cv2.cvtColor(self.camera_stream.read(), cv2.COLOR_BGR2RGB)

        # flip frame horizontally.
        frame = cv2.flip(frame, 1)

        if self.camera_capture_flag:
            timestamp: datetime = datetime.now(timezone.utc)

            # rate limiting the camera capture based of minimum delay between
            # two consecutive captures to avoid bursts of images for the same person.
            if (
                self.camera_capture_minimum_delay_in_seconds
                < (timestamp - self.camera_capture_timestamp).seconds
            ):
                self.camera_capture_timestamp = timestamp
                filename: str = (
                    f"{timestamp.strftime('%d-%m-%YT%H-%M-%S')}.avif"
                )

                image = Image.fromarray(frame)

                with open(
                    os.path.join(self.images_dir, filename), "wb+"
                ) as output:
                    image.save(
                        output,
                        format="avif",
                        optimize=self.camera_image_optimize,
                        quality=self.camera_image_quality,
                    )

                if self.api_enabled:
                    # upload photo to api from another thread
                    # to prevent stalling current program.
                    threading.Thread(
                        target=self._camera_process_and_upload,
                        args=(
                            filename,
                            image,
                        ),
                        daemon=True,
                    ).start()

            self.camera_capture_flag = False

        # show image on tkinter frame.
        img_tk = ImageTk.PhotoImage(
            image=camera_resize(
                frame,
                self.window_primary_width - 5,
                self.window_primary_height - 5,
            )
        )

        self.label_camera.imgtk = img_tk
        self.label_camera.configure(image=img_tk)
        self.label_camera.after(1, self.camera_play)

    def _camera_process_and_upload(self, name, image) -> None:
        logging.info(f"API:UPLOAD:{name}: uploading camera image:")

        # process image binary and serialize it as base 85 string.
        with BytesIO() as base85_file:
            image.save(
                base85_file,
                format="avif",
                optimize=self.camera_image_optimize,
                quality=self.camera_image_quality,
            )
            image_base85: str = base64.b85encode(base85_file.getvalue()).decode(
                "utf-8"
            )

        headers = {"access_token": "ACCESS_TOKEN"}

        flag_successful_upload: bool = False

        # upload image with retry mechanism.
        for attempt in range(1, self.api_retry_max_attempts):
            logging.debug(f"API:UPLOAD:{name}: trying attempt: {attempt}")
            try:
                response: requests.Response = requests.post(
                    f"{self.api_endpoint}/upload",
                    headers=headers,
                    json={"name": name, "data": image_base85},
                    timeout=self.api_request_timeout,
                )
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                logging.warning(
                    f"API:UPLOAD:{name}: uploading camera image http error"
                )
                time.sleep(self.api_retry_delay_seconds)
            except requests.exceptions.ConnectionError:
                logging.warning(
                    f"API:UPLOAD:{name}: uploading camera image connection error"
                )
                time.sleep(self.api_retry_delay_seconds)
            except requests.exceptions.Timeout:
                logging.warning(
                    f"API:UPLOAD:{name}: uploading camera image timout error"
                )
                time.sleep(self.api_retry_delay_seconds)
            except requests.exceptions.RequestException:
                logging.warning(
                    f"API:UPLOAD:{name}: uploading camera image error"
                )
                time.sleep(self.api_retry_delay_seconds)
            else:
                logging.info(f"API:UPLOAD:{name}: upload successful")
                flag_successful_upload = True
                break

        if not flag_successful_upload:
            logging.error(f"API:UPLOAD:{name}: upload failed")

    def start(self):
        self.camera_play()
        self.tk_app.mainloop()


app = NimanWebcam(
    title="Niman Webcam",
    use_relative_path=True,
    log_level="debug",
    log_enable_fault_handler=False,
    camera_delay_seconds=1,
)

app.start()
