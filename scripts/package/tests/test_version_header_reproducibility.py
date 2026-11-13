# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""SOURCE_DATE_EPOCH produces the same header in every build timezone."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("epoch", [0, 1609459200])
@pytest.mark.parametrize("timestamp", [False, True])
def test_source_date_epoch_is_timezone_independent(epoch, timestamp):
    generator = Path(__file__).resolve().parents[1] / "generate_version_header.sh"
    command = ["bash", str(generator), "sample", "9.0.0"]
    if timestamp:
        command.append("--timestamp")
    outputs = []
    for zone in ("UTC0", "HST10", "JST-9"):
        result = subprocess.run(
            command,
            env={**os.environ, "SOURCE_DATE_EPOCH": str(epoch), "TZ": zone},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout)

    expected = datetime.fromtimestamp(epoch, tz=timezone.utc)
    assert all(output == outputs[0] for output in outputs)
    assert f"Copyright (c) {expected.year}" in outputs[0]
    if timestamp:
        assert f"#define SAMPLE_TIMESTAMP {expected:%Y%m}" in outputs[0]
    else:
        assert "SAMPLE_TIMESTAMP" not in outputs[0]
