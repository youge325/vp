"""批量导出所有 RIFE 模型为 ONNX 格式。"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.algorithms.rife.model_loader import SUPPORTED_MODELS, get_model_dir
from app.algorithms.rife.onnx_export import export_rife_to_onnx


def main():
    model_dir = get_model_dir()
    success = []
    failed = []

    for version in SUPPORTED_MODELS:
        onnx_path = os.path.join(model_dir, f"rife_v{version}.onnx")
        if os.path.isfile(onnx_path) and os.path.getsize(onnx_path) > 0:
            print(f"[SKIP] v{version}: ONNX 已存在 ({onnx_path})")
            success.append(version)
            continue

        try:
            print(f"[EXPORT] v{version} ...", flush=True)
            export_rife_to_onnx(
                model_version=version,
                output_path=onnx_path,
                dummy_size=(256, 256),
                dynamo=False,
            )
            print(f"[OK] v{version}: {onnx_path}")
            success.append(version)
        except Exception as e:
            print(f"[FAIL] v{version}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed.append((version, str(e)))

    print("\n" + "=" * 60)
    print(f"总计: {len(SUPPORTED_MODELS)}, 成功: {len(success)}, 失败: {len(failed)}")
    if failed:
        print("\n失败列表:")
        for v, err in failed:
            print(f"  v{v}: {err}")
    print("=" * 60)


if __name__ == "__main__":
    main()
