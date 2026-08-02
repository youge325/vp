// Generated from contracts/model-assets.json. Do not edit.
pub(crate) struct ModelAssetVariant {
    pub(crate) scale_factor: u32,
    pub(crate) inference_bytes: u64,
    pub(crate) inference_sha256: &'static str,
    pub(crate) relative_path: &'static str,
}

pub(crate) const REAL_RAWVSR_BASICVSR_LICENSE_PATH: &str =
    "licenses/real-rawvsr-basicvsr/CC-BY-NC-SA-4.0.txt";
pub(crate) const REAL_RAWVSR_BASICVSR_NOTICE_PATH: &str = "licenses/real-rawvsr-basicvsr/NOTICE.md";
pub(crate) const REAL_RAWVSR_BASICVSR_VARIANTS: &[ModelAssetVariant] = &[
    ModelAssetVariant {
        scale_factor: 2,
        inference_bytes: 24608772,
        inference_sha256: "19e06889ff7e96f3904c24562667949bb7e452ab02234508db51759741c91efb",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-basicvsr/x2/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 3,
        inference_bytes: 25347332,
        inference_sha256: "01dbec2b5827f868d89a12abe9aadb9952f6bc05b28c233f10884cfc18a59914",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-basicvsr/x3/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 4,
        inference_bytes: 25199820,
        inference_sha256: "bc8e5f0d545d049a8268d9a980062aa83ee86ce0c998e104a245d5190dab2295",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-basicvsr/x4/model.safetensors",
    },
];
