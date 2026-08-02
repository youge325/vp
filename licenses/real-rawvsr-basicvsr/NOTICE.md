# Real-RawVSR BasicVSR model notice

The packaged `real-rawvsr-basicvsr` weights and the inference-only BasicVSR
port are third-party assets. They are separate from VP Workbench's MIT-licensed
application code and are distributed only for non-commercial research and
personal use under CC BY-NC-SA 4.0.

- Upstream project: <https://github.com/zmzhang1998/Real-RawVSR>
- Official checkpoints: <https://drive.google.com/drive/folders/1zBMWiRq352HvurnVDxG0t-_OPVXAwtcQ?usp=sharing>
- Copyright: Intelligent Imaging and Reconstruction Laboratory, Tianjin University.
- BasicVSR portions retain the upstream OpenMMLab copyright notice.

VP Workbench modifications are limited to removing training/MMCV/registry
infrastructure, preserving checkpoint-compatible inference layers, converting
the official pickle checkpoints to inference-only SafeTensors, and adapting RGB
video frame I/O, bounded temporal slicing, padding, progress, and error handling.
No ground-truth color correction is performed.

Please cite:

> Huanjing Yue, Zhiming Zhang, and Jingyu Yang. “Real-RawVSR: Real-World Raw
> Video Super-Resolution with a Benchmark Dataset.” ECCV 2022, pp. 608–624.

Use of these assets is governed by
[CC BY-NC-SA 4.0](./CC-BY-NC-SA-4.0.txt). Commercial use requires separate
authorization from the rights holders.
