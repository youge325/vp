// Generated from contracts/model-assets.json. Do not edit.
#[derive(Clone, Copy)]
pub(crate) struct ModelAssetVariant {
    pub(crate) scale_factor: u32,
    pub(crate) inference_bytes: u64,
    pub(crate) inference_sha256: &'static str,
    pub(crate) relative_path: &'static str,
}

pub(crate) struct ModelAssetFamily {
    pub(crate) algorithm_id: &'static str,
    pub(crate) display_name: &'static str,
    pub(crate) variants: &'static [ModelAssetVariant],
}

pub(crate) const REAL_RAWVSR_LICENSE_PATH: &str = "licenses/real-rawvsr/CC-BY-NC-SA-4.0.txt";
pub(crate) const REAL_RAWVSR_NOTICE_PATH: &str = "licenses/real-rawvsr/NOTICE.md";
pub(crate) const REAL_RAWVSR_THIRD_PARTY_NOTICE_PATH: &str =
    "licenses/real-rawvsr/THIRD-PARTY-NOTICES.md";

const REAL_RAWVSR_FAMILY_0_VARIANTS: &[ModelAssetVariant] = &[
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

const REAL_RAWVSR_FAMILY_1_VARIANTS: &[ModelAssetVariant] = &[
    ModelAssetVariant {
        scale_factor: 2,
        inference_bytes: 12623308,
        inference_sha256: "f237abefeff26bef1077fcab1ee096b7056858ac16c05cd8a1bf0f7a8a73c02e",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-edvr/x2/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 3,
        inference_bytes: 13361868,
        inference_sha256: "2138f338398f236b91b56385318ef24e316eab1df7e415c6841c50680400dc15",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-edvr/x3/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 4,
        inference_bytes: 13214324,
        inference_sha256: "cf947c5a93d8616fe879272eab456d740a1666a4c6310a7af9aa152e30676c34",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-edvr/x4/model.safetensors",
    },
];

const REAL_RAWVSR_FAMILY_2_VARIANTS: &[ModelAssetVariant] = &[
    ModelAssetVariant {
        scale_factor: 2,
        inference_bytes: 8557668,
        inference_sha256: "8d729c685899a88d02c60b37c38eab5af0c6b2b119602a72a3bade36d9ae8c51",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-tdan/x2/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 3,
        inference_bytes: 9296228,
        inference_sha256: "e5167c65adb60c45e491d090af8c4340f700ca653728aa6abe87deaa2772df29",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-tdan/x3/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 4,
        inference_bytes: 9148676,
        inference_sha256: "5098c026063c09de5ed064409f2a9741b058fa0e4b7a62aa929d4796ae6b67da",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-tdan/x4/model.safetensors",
    },
];

const REAL_RAWVSR_FAMILY_3_VARIANTS: &[ModelAssetVariant] = &[
    ModelAssetVariant {
        scale_factor: 2,
        inference_bytes: 5516628,
        inference_sha256: "38ddb333e3c0befae3ab7bf3821bfc856fc81ec9dd980f66afc621b9ce5c783f",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-toflow/x2/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 3,
        inference_bytes: 5516628,
        inference_sha256: "c1357bc9c16416eda2f7ded3eb8ef6c13068a219dab5a922b428e6593c1fd701",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-toflow/x3/model.safetensors",
    },
    ModelAssetVariant {
        scale_factor: 4,
        inference_bytes: 5516628,
        inference_sha256: "15efc76c7821d55c6d8882b4d4fbe4695d4dbff9f56b45730cec671de0907b77",
        relative_path: "models/super_resolution/pytorch/real-rawvsr-toflow/x4/model.safetensors",
    },
];

pub(crate) const REAL_RAWVSR_MODEL_FAMILIES: &[ModelAssetFamily] = &[
    ModelAssetFamily {
        algorithm_id: "real-rawvsr-basicvsr",
        display_name: "Real-RawVSR BasicVSR",
        variants: REAL_RAWVSR_FAMILY_0_VARIANTS,
    },
    ModelAssetFamily {
        algorithm_id: "real-rawvsr-edvr",
        display_name: "Real-RawVSR EDVR",
        variants: REAL_RAWVSR_FAMILY_1_VARIANTS,
    },
    ModelAssetFamily {
        algorithm_id: "real-rawvsr-tdan",
        display_name: "Real-RawVSR TDAN",
        variants: REAL_RAWVSR_FAMILY_2_VARIANTS,
    },
    ModelAssetFamily {
        algorithm_id: "real-rawvsr-toflow",
        display_name: "Real-RawVSR TOFlow",
        variants: REAL_RAWVSR_FAMILY_3_VARIANTS,
    },
];
