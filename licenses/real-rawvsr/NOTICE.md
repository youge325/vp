# Real-RawVSR RGB model notice

The packaged `real-rawvsr-basicvsr`, `real-rawvsr-edvr`,
`real-rawvsr-tdan`, and `real-rawvsr-toflow` weights and their inference-only
network ports are third-party assets. They are separate from VP Workbench's
MIT-licensed application code and are distributed only for non-commercial
research and personal use under CC BY-NC-SA 4.0.

- Upstream project: <https://github.com/zmzhang1998/Real-RawVSR>
- Official checkpoints: <https://drive.google.com/drive/folders/1zBMWiRq352HvurnVDxG0t-_OPVXAwtcQ?usp=sharing>
- Real-RawVSR copyright: Intelligent Imaging and Reconstruction Laboratory,
  Tianjin University.
- BasicVSR and TOFlow portions retain the OpenMMLab copyright notice and
  Apache-2.0 terms: <https://github.com/open-mmlab/mmagic/blob/main/LICENSE>.
- TDAN portions retain the original MIT terms:
  <https://github.com/YapengTian/TDAN-VSR-CVPR-2020/blob/master/LICENSE>.
- EDVR architecture provenance: <https://github.com/xinntao/EDVR>.

VP Workbench removes training, MMCV, registry, logger, and custom extension
infrastructure; preserves checkpoint-compatible inference layers; replaces
legacy deformable convolution bindings with torchvision's maintained CUDA
operator; converts official pickle checkpoints to inference-only SafeTensors;
and adapts RGB video I/O, bounded temporal slicing, padding, progress, and
error handling. No ground-truth color correction is performed.

Please cite:

> Huanjing Yue, Zhiming Zhang, and Jingyu Yang. “Real-RawVSR: Real-World Raw
> Video Super-Resolution with a Benchmark Dataset.” ECCV 2022, pp. 608–624.

Use of these assets is governed by
[CC BY-NC-SA 4.0](./CC-BY-NC-SA-4.0.txt). Commercial use requires separate
authorization from the rights holders.
