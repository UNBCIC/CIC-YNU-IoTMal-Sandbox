import logging
import os
import re
import shutil
import socket
import time

import requests

from config.settings import app_settings
from service.analysis import dynamic_analysis, clear_stop, AnalysisCancelled

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Starting worker poller")

    worker = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    worker["worker_ip"] = s.getsockname()[0]
    s.close()

    time.sleep(5)

    worker_uri = f"http://{worker['worker_ip']}:{app_settings.port}{app_settings.app_base_url}"

    while True:
        get_file_url = app_settings.sandbox_manager_uri + "/get-file/" + app_settings.app_name
        logger.debug(f"GET {get_file_url}")
        resp = requests.get(get_file_url, params={"worker_uri": worker_uri})

        if resp.status_code == 200:
            fname = re.findall("filename=\"(.+)\"", resp.headers['content-disposition'])[0]
            logger.info(f"Received task: {fname}")

            task_dir = app_settings.data_dir + fname
            os.makedirs(task_dir)
            with open(task_dir + "/" + fname, 'wb') as f:
                f.write(resp.content)

            clear_stop()
            try:
                dynamic_analysis(fname, task_dir=task_dir, worker=worker)
            except AnalysisCancelled:
                logger.warning(f"Task {fname} was cancelled")
                shutil.rmtree(task_dir, ignore_errors=True)
                continue
            except Exception as e:
                logger.exception(f"Analysis failed for task {fname}")
                qemu_log = task_dir + app_settings.qemu_log_path
                try:
                    with open(qemu_log, 'r', encoding='utf-8', errors='replace') as _lf:
                        logger.error(f"QEMU log for task {fname}:\n{_lf.read()}")
                except FileNotFoundError:
                    logger.warning(f"No QEMU log found for task {fname}")
                shutil.rmtree(task_dir, ignore_errors=True)
                failure_url = app_settings.sandbox_manager_uri + "/submit-failure/" + fname
                requests.post(failure_url, params={"reason": str(e)})
                continue

            time.sleep(0.5)

            shutil.rmtree(task_dir + "/image")
            shutil.make_archive(task_dir, 'zip', task_dir)

            upload_url = app_settings.sandbox_manager_uri + "/submit-result/" + fname
            with open(task_dir + ".zip", 'rb') as f:
                resp2 = requests.post(upload_url, files={"file": f})
            logger.info(f"Upload response: {resp2.status_code}")

            if resp2.status_code == 200:
                shutil.rmtree(task_dir)
                os.remove(task_dir + ".zip")
            else:
                logger.warning(f"Result upload failed ({resp2.status_code}) for task {fname}, cleaning up")
                shutil.rmtree(task_dir, ignore_errors=True)
                try:
                    os.remove(task_dir + ".zip")
                except FileNotFoundError:
                    pass
                try:
                    failure_url = app_settings.sandbox_manager_uri + "/submit-failure/" + fname
                    requests.post(failure_url, params={"reason": f"result upload failed with status {resp2.status_code}"})
                except Exception:
                    logger.exception(f"Failed to report upload failure to manager for task {fname}")
        else:
            logger.debug("No tasks available, retrying in 5s")
            time.sleep(5)
