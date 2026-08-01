#   Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserve.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os.path as osp

from app.algorithms.paddle.paddlegan_vsr.weights import _fixed_weight_root
from app.errors.codes import TaskErrorCode
from app.errors.process import raise_error

# VP vendor integration: keep auxiliary PaddleGAN weights beside the VP
# repository-local PaddleGAN VSR weight cache instead of using ~/.cache/ppgan.
PPGAN_HOME = str(_fixed_weight_root() / "_auxiliary")


def is_url(path):
    """
    Whether path is URL.
    Args:
        path (string): URL string or not.
    """
    return path.startswith("http://") or path.startswith("https://")


def _map_path(url, root_dir):
    # parse path after download under root_dir
    fname = osp.split(url)[-1]
    fpath = fname
    return osp.join(root_dir, fpath)


def get_path_from_url(url, md5sum=None, check_exist=True):
    """Map a PaddleGAN auxiliary weight URL to a pre-provisioned local file.

    VP Workbench does not download PaddleGAN weights at runtime. The PaddleGAN
    generator code still calls this vendored helper with upstream URLs, so the
    URL is used only for its filename and the file must already exist under
    ``backend/models/super_resolution/paddlegan/_auxiliary``.
    """
    assert is_url(url), "downloading from {} not a url".format(url)
    fullpath = _map_path(url, PPGAN_HOME)

    if osp.isfile(fullpath) and osp.getsize(fullpath) > 0:
        return fullpath

    raise_error(
        TaskErrorCode.MISSING_MODEL,
        "PaddleGAN auxiliary weight is missing: {}".format(fullpath),
        details={"path": fullpath},
    )
