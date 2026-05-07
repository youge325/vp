"""RIFE 全版本权重加载验证测试。

测试内容：
1. 结构验证：逐个创建 36 个版本的 IFNet + Head，验证 state_dict 键匹配
2. 前向传播验证：验证各版本的推理路径能正常执行
3. 权重加载验证：加载全部 36 个版本的真实权重并验证

测试策略：
- 权重文件预置于 backend/models/ 目录下
- 使用 torch.device("meta") 创建模型骨架，再 load_state_dict 加载真实权重
- 验证 state_dict 键完全匹配（strict=False 但检查缺失/多余键）
"""

import os
import sys

import pytest

pytestmark = pytest.mark.pytorch

# 确保 backend 目录在 sys.path 上
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import torch
from app.algorithms.rife.model_loader import (
    SUPPORTED_MODELS,
    MODEL_CONFIGS,
    _version_to_module_name,
    _build_sequential_head,
    HEAD_NONE,
    HEAD_SEQUENTIAL,
    HEAD_CUSTOM,
    get_model_dir,
)


def _make_backwarp_grid(height: int, width: int) -> torch.Tensor:
    """创建后向变形采样网格。"""
    tenHorizontal = torch.linspace(-1.0, 1.0, width)
    tenHorizontal = tenHorizontal.view(1, 1, 1, width).expand(-1, -1, height, -1)
    tenVertical = torch.linspace(-1.0, 1.0, height)
    tenVertical = tenVertical.view(1, 1, height, 1).expand(-1, -1, -1, width)
    return torch.cat([tenHorizontal, tenVertical], 1)


def test_structure():
    """测试全部 36 个版本的模型结构。"""
    failed = _test_structure_impl()
    assert len(failed) == 0, f"结构验证失败: {[(v, e) for v, e in failed]}"


def _test_structure_impl():
    print("=" * 60)
    print("1. Structure validation (IFNet + Head state_dict keys)")
    print("=" * 60)

    results = {}
    failed = []

    for version in SUPPORTED_MODELS:
        config = MODEL_CONFIGS[version]
        head_type = config["head_type"]
        encode_channel = config["encode_channel"]
        ensemble = config["ensemble"]

        try:
            # 动态导入 IFNet 模块
            module_name = _version_to_module_name(version)
            ifnet_module = __import__(f"app.algorithms.rife.{module_name}", fromlist=["IFNet"])
            IFNet = ifnet_module.IFNet

            # 创建 IFNet（meta 设备，不分配内存）
            with torch.device("meta"):
                flownet = IFNet(scale=1.0, ensemble=ensemble)

            # 获取 IFNet 的 state_dict 键
            ifnet_keys = set(flownet.state_dict().keys())

            # 分离 encode 键和 IFNet 专属键
            encode_keys_in_ifnet = {k for k in ifnet_keys if k.startswith("encode.")}
            ifnet_only_keys = ifnet_keys - encode_keys_in_ifnet

            # 验证 Head 类型与 encode 键的一致性
            if head_type == HEAD_NONE:
                if encode_keys_in_ifnet:
                    print(f"  X {version}: no-head but has encode keys: {encode_keys_in_ifnet}")
                    failed.append((version, "no-head has encode keys"))
                    results[version] = "FAIL"
                    continue
            else:
                if not encode_keys_in_ifnet:
                    print(f"  X {version}: has-head but no encode keys")
                    failed.append((version, "has-head no encode keys"))
                    results[version] = "FAIL"
                    continue

                # 创建 Head 并验证键匹配
                if head_type == HEAD_SEQUENTIAL:
                    head_config = config.get("head_config", {})
                    with torch.device("meta"):
                        encode = _build_sequential_head(
                            in_channels=head_config.get("in_channels", 3),
                            mid_channels=head_config.get("mid_channels", 16),
                            out_channels=head_config.get("out_channels", 4),
                        )
                    head_keys = set(encode.state_dict().keys())
                    expected_head_keys = {k.replace("encode.", "") for k in encode_keys_in_ifnet}
                    if expected_head_keys != head_keys:
                        print(
                            f"  X {version}: Sequential Head key mismatch, "
                            f"expected: {sorted(expected_head_keys)}, "
                            f"got: {sorted(head_keys)}"
                        )
                        failed.append((version, "Head key mismatch"))
                        results[version] = "FAIL"
                        continue

                elif head_type == HEAD_CUSTOM:
                    Head = ifnet_module.Head
                    with torch.device("meta"):
                        encode = Head()
                    head_keys = set(encode.state_dict().keys())
                    expected_head_keys = {k.replace("encode.", "") for k in encode_keys_in_ifnet}
                    if expected_head_keys != head_keys:
                        print(
                            f"  X {version}: Custom Head key mismatch, "
                            f"expected: {sorted(expected_head_keys)}, "
                            f"got: {sorted(head_keys)}"
                        )
                        failed.append((version, "Head key mismatch"))
                        results[version] = "FAIL"
                        continue

            print(
                f"  OK {version}: structure OK (head={head_type}, enc_ch={encode_channel}, "
                f"ifnet_keys={len(ifnet_only_keys)}, enc_keys={len(encode_keys_in_ifnet)})"
            )
            results[version] = "PASS"

        except Exception as e:
            print(f"  X {version}: exception - {e}")
            failed.append((version, str(e)))
            results[version] = "FAIL"

    # 汇总
    print()
    pass_count = sum(1 for v in results.values() if v == "PASS")
    fail_count = sum(1 for v in results.values() if v == "FAIL")
    total = len(results)
    print(f"Structure: {pass_count}/{total} passed, {fail_count} failed")

    if failed:
        print("\nFailed versions:")
        for version, error in failed:
            print(f"  {version}: {error}")

    return failed


def test_forward_pass():
    """测试全部 36 个版本的前向传播。"""
    failed = _test_forward_pass_impl()
    assert len(failed) == 0, f"前向传播失败: {[(v, e) for v, e in failed]}"


def _test_forward_pass_impl():
    print()
    print("=" * 60)
    print("2. Forward pass validation (random weights)")
    print("=" * 60)

    results = {}
    failed = []

    for version in SUPPORTED_MODELS:
        config = MODEL_CONFIGS[version]
        head_type = config["head_type"]
        ensemble = config["ensemble"]
        modulo = config["modulo"]

        try:
            # 动态导入 IFNet 模块
            module_name = _version_to_module_name(version)
            ifnet_module = __import__(f"app.algorithms.rife.{module_name}", fromlist=["IFNet"])
            IFNet = ifnet_module.IFNet

            # 创建 IFNet（正常设备，随机初始化权重）
            flownet = IFNet(scale=1.0, ensemble=ensemble)
            flownet.eval()

            # 创建 Head
            encode = None
            if head_type == HEAD_SEQUENTIAL:
                head_config = config.get("head_config", {})
                encode = _build_sequential_head(
                    in_channels=head_config.get("in_channels", 3),
                    mid_channels=head_config.get("mid_channels", 16),
                    out_channels=head_config.get("out_channels", 4),
                )
                encode.eval()
            elif head_type == HEAD_CUSTOM:
                Head = ifnet_module.Head
                encode = Head()
                encode.eval()

            # 前向传播测试
            h, w = modulo, modulo
            img0 = torch.randn(1, 3, h, w)
            img1 = torch.randn(1, 3, h, w)
            timestep = torch.full([1, 1, h, w], 0.5)
            flow_div = torch.tensor([(w - 1.0) / 2.0, (h - 1.0) / 2.0])
            backwarp_grid = _make_backwarp_grid(h, w)

            with torch.no_grad():
                if head_type != HEAD_NONE and encode is not None:
                    f0 = encode(img0)
                    f1 = encode(img1)
                    output = flownet(img0, img1, timestep, flow_div, backwarp_grid, f0, f1)
                else:
                    output = flownet(img0, img1, timestep, flow_div, backwarp_grid)

                # 验证输出形状
                if output.shape[2:] != (h, w) or output.shape[0] != 1 or output.shape[1] != 3:
                    print(f"  X {version}: output shape mismatch, expected (1,3,{h},{w}), got {tuple(output.shape)}")
                    failed.append((version, f"output shape: {tuple(output.shape)}"))
                    results[version] = "FAIL"
                    continue

            print(f"  OK {version}: forward OK, output {tuple(output.shape)}")
            results[version] = "PASS"

        except Exception as e:
            short_error = str(e)[:100]
            print(f"  X {version}: forward failed - {short_error}")
            failed.append((version, short_error))
            results[version] = "FAIL"

    # 汇总
    print()
    pass_count = sum(1 for v in results.values() if v == "PASS")
    fail_count = sum(1 for v in results.values() if v == "FAIL")
    total = len(results)
    print(f"Forward pass: {pass_count}/{total} passed, {fail_count} failed")

    if failed:
        print("\nFailed versions:")
        for version, error in failed:
            print(f"  {version}: {error}")

    return failed


def test_weight_loading():
    """测试全部 36 个版本的真实权重加载。"""
    failed = _test_weight_loading_impl()
    assert len(failed) == 0, f"权重加载失败: {[(v, e) for v, e in failed]}"


def _test_weight_loading_impl():
    """加载全部 36 个版本的真实权重并验证。"""
    print()
    print("=" * 60)
    print("3. Real weight loading validation (all 36 versions)")
    print("=" * 60)

    model_dir = get_model_dir()
    results = {}
    failed = []

    for version in SUPPORTED_MODELS:
        config = MODEL_CONFIGS[version]
        head_type = config["head_type"]
        ensemble = config["ensemble"]
        encode_channel = config["encode_channel"]

        weight_path = os.path.join(model_dir, f"flownet_v{version}.pkl")

        try:
            # 检查权重文件存在
            if not os.path.isfile(weight_path):
                print(f"  X {version}: 权重文件不存在 - {weight_path}")
                failed.append((version, "权重文件不存在"))
                results[version] = "FAIL"
                continue

            file_size = os.path.getsize(weight_path)
            if file_size == 0:
                print(f"  X {version}: 权重文件为空 (0 bytes)")
                failed.append((version, "权重文件为空"))
                results[version] = "FAIL"
                continue

            # 加载权重
            state_dict = torch.load(weight_path, map_location="cpu", weights_only=False)
            # 移除 DistributedDataParallel 的 "module." 前缀
            state_dict = {k.replace("module.", ""): v for k, v in state_dict.items() if "module." in k}

            # 动态导入 IFNet
            module_name = _version_to_module_name(version)
            ifnet_module = __import__(f"app.algorithms.rife.{module_name}", fromlist=["IFNet"])
            IFNet = ifnet_module.IFNet

            # 创建 IFNet（meta 设备）
            with torch.device("meta"):
                flownet = IFNet(scale=1.0, ensemble=ensemble)

            # 加载 state_dict
            load_result = flownet.load_state_dict(state_dict, strict=False, assign=True)

            # 检查缺失和多余键
            missing = load_result.missing_keys
            unexpected = load_result.unexpected_keys

            # 加载 Head
            encode_missing = []
            encode_unexpected = []
            if head_type == HEAD_CUSTOM:
                Head = ifnet_module.Head
                encode_state_dict = {k.replace("encode.", ""): v for k, v in state_dict.items() if "encode." in k}
                with torch.device("meta"):
                    encode = Head()
                enc_result = encode.load_state_dict(encode_state_dict, assign=True)
                encode_missing = enc_result.missing_keys
                encode_unexpected = enc_result.unexpected_keys

            elif head_type == HEAD_SEQUENTIAL:
                head_config = config.get("head_config", {})
                encode_state_dict = {k.replace("encode.", ""): v for k, v in state_dict.items() if "encode." in k}
                with torch.device("meta"):
                    encode = _build_sequential_head(
                        in_channels=head_config.get("in_channels", 3),
                        mid_channels=head_config.get("mid_channels", 16),
                        out_channels=head_config.get("out_channels", 4),
                    )
                enc_result = encode.load_state_dict(encode_state_dict, assign=True)
                encode_missing = enc_result.missing_keys
                encode_unexpected = enc_result.unexpected_keys

            # 汇总
            all_missing = missing + encode_missing
            # 排除训练残余权重（teacher/block_tea/contextnet/unet/caltime），
            # vs-rife 也用 strict=False 加载并忽略这些
            training_prefixes = (
                "teacher.",
                "block_tea.",
                "contextnet.",
                "unet.",
                "caltime.",
            )
            all_unexpected = [k for k in (unexpected + encode_unexpected) if not k.startswith(training_prefixes)]

            if all_missing or all_unexpected:
                msg_parts = []
                if all_missing:
                    msg_parts.append(f"缺失键: {all_missing[:5]}{'...' if len(all_missing) > 5 else ''}")
                if all_unexpected:
                    msg_parts.append(f"多余键: {all_unexpected[:5]}{'...' if len(all_unexpected) > 5 else ''}")
                print(f"  X {version}: {', '.join(msg_parts)} ({file_size / 1024 / 1024:.1f}MB)")
                failed.append((version, ", ".join(msg_parts)))
                results[version] = "FAIL"
            else:
                print(
                    f"  OK {version}: 权重加载成功 ({file_size / 1024 / 1024:.1f}MB, "
                    f"head={head_type}, enc_ch={encode_channel})"
                )
                results[version] = "PASS"

        except Exception as e:
            short_error = str(e)[:120]
            print(f"  X {version}: 加载失败 - {short_error}")
            failed.append((version, short_error))
            results[version] = "FAIL"

    # 汇总
    print()
    pass_count = sum(1 for v in results.values() if v == "PASS")
    fail_count = sum(1 for v in results.values() if v == "FAIL")
    total = len(results)
    print(f"Weight loading: {pass_count}/{total} passed, {fail_count} failed")

    if failed:
        print("\nFailed versions:")
        for version, error in failed:
            print(f"  {version}: {error}")

    return failed


if __name__ == "__main__":
    print("RIFE Full Version Model Validation")
    print("=" * 60)

    # 1. 结构验证（不需要权重文件）
    struct_failed = _test_structure_impl()

    # 2. 前向传播验证（使用随机权重）
    forward_failed = _test_forward_pass_impl()

    # 3. 全部 36 版本真实权重加载（权重文件预置于 backend/models/）
    weight_failed = _test_weight_loading_impl()

    # 总汇总
    print()
    print("=" * 60)
    total_failed = len(struct_failed) + len(forward_failed) + len(weight_failed)
    if total_failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"TOTAL FAILURES: {total_failed}")

    sys.exit(1 if total_failed > 0 else 0)
