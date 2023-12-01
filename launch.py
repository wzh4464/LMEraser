#!/usr/bin/env python3
"""
launch helper functions
"""

import os
import sys
import PIL
import contextlib
from collections import defaultdict
from tabulate import tabulate
from typing import Tuple

import torch
from utils.file_io import PathManager
from utils import logging
from utils.distributed import get_world_size


def collect_torch_env() -> str:
    try:
        import torch.__config__

        return torch.__config__.show()
    except ImportError:
        # compatible with older versions of pytorch
        from torch.utils.collect_env import get_pretty_env_info

        return get_pretty_env_info()


def get_env_module() -> Tuple[str]:
    var_name = "ENV_MODULE"
    return var_name, os.environ.get(var_name, "<not set>")


def collect_env_info() -> str:
    data = [("Python", sys.version.replace("\n", ""))]
    data.extend(
        (
            get_env_module(),
            ("PyTorch", torch.__version__),
            ("PyTorch Debug Build", torch.version.debug),
        )
    )
    has_cuda = torch.cuda.is_available()
    data.append(("CUDA available", has_cuda))
    if has_cuda:
        data.append(("CUDA ID", os.environ["CUDA_VISIBLE_DEVICES"]))
        devices = defaultdict(list)
        for k in range(torch.cuda.device_count()):
            devices[torch.cuda.get_device_name(k)].append(str(k))
        data.extend(
            ("GPU " + ",".join(devids), name)
            for name, devids in devices.items()
        )
    data.append(("Pillow", PIL.__version__))

    with contextlib.suppress(ImportError):
        import cv2

        data.append(("cv2", cv2.__version__))
    env_str = tabulate(data) + "\n"
    env_str += collect_torch_env()
    return env_str


def logging_train_setup(args) -> None:
    output_dir = args.output_dir
    if output_dir:
        PathManager.mkdirs(output_dir)

    logger = logging.setup_logging(
        args.num_gpus, get_world_size(), output_dir, name="dam-vp")

    # Log basic information about environment, cmdline arguments, and config
    rank = args.local_rank
    logger.info(
        f"Rank of current process: {rank}. World size: {args.num_gpus}.")
    logger.info("Environment info:\n" + collect_env_info())

    logger.info(f"Command line arguments: {str(args)}")
    # cudnn benchmark has large overhead.
    # It shouldn't be used considering the small size of typical val set.
    if not (hasattr(args, "eval_only") and args.eval_only):
        torch.backends.cudnn.benchmark = False