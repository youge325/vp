classDiagram
direction BT
class BaseException {
    args
    __cause__
    __context__
    __suppress_context__
    __traceback__
    __notes__
   __init__(self, *args: object)
   __setstate__(self, __state: dict[str, Any] | None)
   with_traceback(self, __tb: TracebackType | None)
   add_note(self, __note: str)
}
class Exception
class node87 {
    __slots__
}
class node57 {
    cls
   __new__(mcls, name, bases, namespace, /, **kwargs)
   register(cls, subclass)
   __instancecheck__(cls, instance)
   __subclasscheck__(cls, subclass)
   _dump_registry(cls, file=None)
   _abc_registry_clear(cls)
   _abc_caches_clear(cls)
}
class node60 {
   process_frame(self, frame: Any, **kwargs)
   process_frame_batch(self, frames: list[Any], **kwargs)
   get_name(self)
   validate(self)
   get_description(self)
   needs_frame_pairs(self)
   process_frame_pair(self, frame0: Any, frame1: Any, timestep: float = 0.5, **kwargs)
   get_interpolation_multi(self)
}
class node113 {
    _registry
   register(cls, algorithm_type: str, algorithm_class: type[IAlgorithm])
   create(
        cls,
        algorithm_type: str,
        tensor_backend: Optional[ITensorBackend] = None,
        tensor_backend_name: str = "pytorch",
        **kwargs,
    )
   get_available_types(cls)
   get_available_algorithms(cls)
}
class node82 {
    _has_head
    _fp16
    _orig_w
    _dtype
    _backwarp_grid
    _padding
    _encode_cache
    _config
    _device
    _modulo
    _model_version
    _cached_size
    _encode
    _scale
    _encode_channel
    _orig_h
    _flownet
    _flow_div
   __init__(
        self,
        model_version: str = "4.25",
        scale: float = 1.0,
        device: Optional[str] = None,
        fp16: bool = False,
        model_dir: Optional[str] = None,
        engine: str = "cuda",
    )
   device(self)
   dtype(self)
   modulo(self)
   has_head(self)
   _ensure_grid_cache(self, height: int, width: int)
   _encode_frame(self, img: torch.Tensor)
   interpolate(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: float = 0.5,
    )
   interpolate_multi(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        multi: int = 2,
    )
   clear_cache(self)
}
class node23 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node75 {
    block0
    block1
    block2
    block3
    scale
    ensemble
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node100 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node39 {
    block0
    block1
    block2
    block3
    scale
    ensemble
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node143 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node163 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node135 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node147 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node69 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node104 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node17 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node127 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node8 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node24 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node6 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node29 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node156 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node9 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node7 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node171 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node102 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node72 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node43 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node5 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node64 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node14 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node44 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node168 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node38 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node78 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node170 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node130 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node94 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node25 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node1 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node13 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node128 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node157 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node116 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node101 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node158 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node74 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node10 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node133 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node109 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node117 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node46 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node20 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node4 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node63 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node140 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node185 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node166 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node51 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node103 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node180 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node150 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node52 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node136 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node70 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node55 {
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node149 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node71 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node76 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node173 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node15 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node123 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node28 {
    encode
    block0
    block1
    block2
    block3
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node148 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node139 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node61 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node179 {
    encode
    block0
    block1
    block2
    block3
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node181 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node40 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node86 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node16 {
    encode
    block0
    block1
    block2
    block3
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node169 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node33 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node106 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node21 {
    encode
    block0
    block1
    block2
    block3
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node175 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node115 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node77 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node132 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node120 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node138 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node84 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node34 {
    encode
    block0
    block1
    block2
    block3
    block4
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node141 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node182 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node26 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node65 {
    encode
    block0
    block1
    block2
    block3
    block4
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node137 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node112 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node91 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node89 {
    encode
    block0
    block1
    block2
    block3
    block4
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node11 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node105 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node67 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node30 {
    encode
    block0
    block1
    block2
    block3
    block4
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node19 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node59 {
    cnn1
    cnn2
    cnn0
    relu
    cnn3
   __init__(self)
   forward(self, x: torch.Tensor, feat: bool = False)
}
class node159 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes, c=64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node45 {
    encode
    block0
    block1
    block2
    block3
    block4
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1)
}
class node96 {
    relu
    conv
    beta
   __init__(self, c, dilation=1)
   forward(self, x: torch.Tensor)
}
class node119 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node97 {
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node114 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node80 {
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node177 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node47 {
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node176 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node85 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node50 {
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node58 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node81 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node68 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node162 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node183 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node73 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node129 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node66 {
    lastconv
    convblock
    conv0
   __init__(self, in_planes: int, c: int = 64)
   forward(self, x: torch.Tensor, flow: torch.Tensor = None, scale: float = 1)
}
class node108 {
    encode
    block0
    block1
    block2
    block3
    ensemble
    scale_list
   __init__(self, scale: float = 1, ensemble: bool = False)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
        f0: torch.Tensor,
        f1: torch.Tensor,
    )
}
class node42 {
    relu
    conv
    beta
   __init__(self, c: int, dilation: int = 1)
   forward(self, x: torch.Tensor)
}
class node98 {
    flownet
    has_head
   __init__(self, flownet: nn.Module, has_head: bool)
   forward(
        self,
        img0: torch.Tensor,
        img1: torch.Tensor,
        timestep: torch.Tensor,
        tenFlow_div: torch.Tensor,
        backwarp_tenGrid: torch.Tensor,
    )
}
class node121 {
    _output_names
    _model_version
    _cached_size
    _session
    _input_names
    _backwarp_grid
    _config
    _modulo
    _flow_div
   __init__(
        self,
        model_version: str = "4.25",
        model_dir: Optional[str] = None,
        onnx_model: Optional[str] = None,
        engine: str = "cuda",
    )
   _ensure_grid_cache(self, height: int, width: int)
   interpolate(
        self,
        img0: np.ndarray,
        img1: np.ndarray,
        timestep: float = 0.5,
    )
   interpolate_multi(
        self,
        img0: np.ndarray,
        img1: np.ndarray,
        multi: int = 2,
    )
   clear_cache(self)
}
class node134 {
   numpy_to_tensor(self, frame: np.ndarray)
   tensor_to_numpy(self, tensor: Any)
   get_name(self)
   is_available(self)
   get_supported_devices(self)
   get_supported_engines(self)
}
class node48 {
    _ort
   __init__(self)
   numpy_to_tensor(self, frame: np.ndarray)
   tensor_to_numpy(self, tensor: Any)
   get_name(self)
   is_available(self)
   get_supported_devices(self)
   get_supported_engines(self)
}
class node153 {
    _paddle
   __init__(self)
   numpy_to_tensor(self, frame: np.ndarray)
   tensor_to_numpy(self, tensor: Any)
   get_name(self)
   is_available(self)
   get_supported_devices(self)
   get_supported_engines(self)
}
class node155 {
    _torch
   __init__(self)
   numpy_to_tensor(self, frame: np.ndarray)
   tensor_to_numpy(self, tensor: Any)
   get_name(self)
   is_available(self)
   get_supported_devices(self)
   get_supported_engines(self)
}
class node118 {
    started_at
    current_frame
    _last_reported_percent
    total_frames
   __init__(self, total_frames: int)
   update(
        self,
        current_frame: int,
        fps: float | None = None,
        speed: float | None = None,
        _out_time_seconds: float | None = None,
        progress_state: str = "continue",
    )
   finish(self, processed_frames: int)
   _estimate_eta(self, current_frame: int, fps: float | None)
}
class node131 {
    MISSING_FFMPEG
    MISSING_MODEL
    MISSING_TENSOR_BACKEND
    CANCELLED
    PROCESS_FAILED
    INVALID_INPUT
    INVALID_CONFIG
    RESUME_CONFLICT
}
class node167 {
    APP_NAME
    APP_VERSION
    DEBUG
    APP_ROOT
    RUNTIME_ROOT
    PYTHON_EXECUTABLE
    FFMPEG_PATH
    FFPROBE_PATH
    OUTPUT_DIR
    MAX_CONCURRENT_TASKS
    DEFAULT_TENSOR_BACKEND
    LOG_DIR
    LOG_FILE_MAX_BYTES
    LOG_FILE_BACKUP_COUNT
    LOG_STARTUP_FILE_KEEP_COUNT
    RIFE_MODEL_DIR
    RIFE_MODEL_VERSION
    RIFE_SCALE
    RIFE_FP16
    RIFE_DEFAULT_MULTI
    TENSORRT_DIR
    model_config
   model_post_init(self, __context: object)
   backend_root(self)
   repo_root(self)
   runtime_root_path(self)
   runtime_mode(self)
   bundled_runtime_available(self)
   resource_summary(self)
}
class node142 {
    code
    details
    message
   __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    )
}
class node151 {
    enabled
    profile
    denoise
    edge_boost
}
class node165 {
    mode
    hwaccel
    hwaccel_device
    decoder
    options
}
class node178 {
    codec
    family
    container
    keep_audio
    rate_control
    options
}
class node122 {
    kind
    enabled
    params
}
class node12 {
    enabled
    target_fps
    multi
    model
    onnx_model
    scale
    fp16
    tensor_backend
    engine
}
class node54 {
    output_dir
    open_on_complete
    segment_frames
}
class node161 {
    enabled
    filters
}
class node62 {
    enabled
    filters
}
class node27 {
    mode
    value
}
class node41 {
    enabled
    scale_factor
    algorithm
    onnx_model
}
class node37 {
    fps_mode
    process_order
    interpolation
    super_resolution
    anime
    preprocess
    postprocess
}
class node174 {
    model_config
}
class node0 {
    completed_output_frames
    sidecar_signature_match
    output_path
    completed_chunks
   __init__(
        self,
        *,
        output_path: str,
        completed_chunks: int,
        completed_output_frames: int,
        sidecar_signature_match: bool,
    )
   to_details(self)
}
class node35 {
    kind
    state
    sidecar_signature_match
}
class node107 {
    start_source_frame
    completed_output_frames
    completed_segments
}
class node83 {
    manifest_path
    sidecar_dir
    output_path
    MANIFEST_VERSION
    CHUNK_PATTERN
    TMP_PATTERN
    TMP_PREFIX
    AUDIO_FILE_NAME
    CONCAT_BASENAME
   __init__(self, output_path: str)
   prepare(
        self,
        signature: str,
        config_snapshot: dict[str, Any] | None = None,
        *,
        mode: ResumeMode = "auto",
    )
   inspect(
        self,
        signature: str,
        *,
        total_output_frames: int = 0,
    )
   chunk_tmp_path(self, extension: str, *, index: int | None = None)
   chunk_final_path(
        self,
        *,
        index: int,
        start_output_frame: int,
        end_output_frame: int,
        next_source_frame: int,
        extension: str,
    )
   finalize_chunk(
        self,
        tmp_path: str,
        *,
        index: int,
        start_output_frame: int,
        end_output_frame: int,
        next_source_frame: int,
    )
   concat_temp_path(self, extension: str)
   scan_completed_chunks(self)
   cleanup_partial(self)
   cleanup_stale_chunks(self, keep: list[SegmentRecord])
   cleanup(self)
   read_completed_segments(self)
   _scan_resume_state(self)
   _empty_state()
   _reset_sidecar(self)
   _delete_final_output(self)
   _write_manifest(self, signature: str, config_snapshot: dict[str, Any])
   _load_manifest_safe(self)
}
class node93 {
    index
    path
    start_output_frame
    end_output_frame
    frame_count
    next_source_frame
}
class node184 {
    pre_steps
    interpolation_step
    post_steps
    total_output_frames
    total_encoded_frames
    total_pairs
}
class node125 {
    _tensor_backend
    _duplicate_threshold
   __init__(self, tensor_backend: ITensorBackend = None, **kwargs)
   process_frame(self, frame: Any, **kwargs)
   process_frame_batch(self, frames: list[Any], **kwargs)
   get_name(self)
   validate(self)
   get_description(self)
}
class node99 {
    _tensor_backend
    _filters
   __init__(self, tensor_backend: ITensorBackend | None = None, **kwargs: Any)
   _validate_filters(self)
   process_frame(self, frame: Any, **kwargs: Any)
   process_frame_batch(self, frames: list[Any], **kwargs: Any)
   get_name(self)
   validate(self)
   get_description(self)
   _apply_filters(self, frame: np.ndarray)
   _apply_scale(self, frame: np.ndarray, params: dict[str, Any])
   _apply_crop(self, frame: np.ndarray, params: dict[str, Any])
   _parse_hex_color(color_str: str)
   _apply_pad(self, frame: np.ndarray, params: dict[str, Any])
   _apply_sharpen(self, frame: np.ndarray, params: dict[str, Any])
   _apply_denoise(self, frame: np.ndarray, params: dict[str, Any])
   _apply_color(self, frame: np.ndarray, params: dict[str, Any])
}
class node164 {
    _tensor_backend
    _model_version
    _scale
    _fp16
    _model_dir
    _engine
    _multi
    _onnx_model
    _device
    _solver
   __init__(
        self,
        tensor_backend: Optional[ITensorBackend] = None,
        **kwargs,
    )
   _ensure_solver(self)
   process_frame(self, frame: Any, **kwargs)
   process_frame_batch(self, frames: list[Any], **kwargs)
   get_name(self)
   validate(self)
   get_description(self)
   needs_frame_pairs(self)
   process_frame_pair(self, frame0: Any, frame1: Any, timestep: float = 0.5, **kwargs)
   get_interpolation_multi(self)
}
class node92 {
    source_index
    frame
}
class node144 {
    output_index
    frame
}
class node146 {
    next_source_frame
}
class node95 {
    next_source_frame
}
class node124 {
    _tensor_backend
    _model_dir
    _engine
    _session
    _scale_factor
    _onnx_model
    _input_name
    _algorithm_name
    _output_name
   __init__(self, tensor_backend: ITensorBackend = None, **kwargs)
   process_frame(self, frame: Any, **kwargs)
   _ensure_onnx_session(self)
   _validate_output_shape(self, input_tensor: np.ndarray, output_tensor: np.ndarray)
   _backend_name(self)
   process_frame_batch(self, frames: list[Any], **kwargs)
   get_name(self)
   validate(self)
   get_description(self)
}
class node18 {
    _ffmpeg_path_explicit
    _frame_count_cache
    _video_info_cache
    ffprobe_path
    _ffprobe_path_explicit
    ffmpeg_path
   __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None)
   _probe_cache_key(self, input_path: str)
   get_video_info(self, input_path: str)
   get_fps(self, input_path: str)
   get_frame_count(self, input_path: str)
   _frame_count_from_metadata(self, input_path: str)
   get_duration(self, input_path: str)
   has_audio(self, input_path: str)
   get_primary_video_codec(self, input_path: str)
   build_rawvideo_decode_command(
        self,
        input_path: str,
        *,
        width: int,
        height: int,
        decode_config: dict[str, Any] | None = None,
        start_frame: int = 0,
    )
   build_rawvideo_encode_command(
        self,
        output_path: str,
        *,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        encode_config: dict[str, Any] | None = None,
    )
   open_rawvideo_decoder(
        self,
        *,
        input_path: str,
        width: int,
        height: int,
        decode_config: dict[str, Any] | None = None,
        start_frame: int = 0,
    )
   open_rawvideo_encoder(
        self,
        *,
        output_path: str,
        width: int,
        height: int,
        fps: float,
        output_fps: float | None = None,
        encode_config: dict[str, Any] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    )
   extract_audio(self, input_path: str, output_path: str)
   merge_audio(self, video_path: str, audio_path: str, output_path: str)
   concat_videos(self, segment_paths: list[str], output_path: str)
   transcode_video(
        self,
        *,
        input_path: str,
        output_path: str,
        decode_config: dict[str, Any] | None = None,
        encode_config: dict[str, Any] | None = None,
        output_fps: float | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    )
   convert_format(
        self,
        input_path: str,
        output_path: str,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
        audio_codec: str = "aac",
    )
   list_codec_names(self, mode: str)
   list_hwaccels(self)
   describe_codec(self, mode: str, name: str)
   parse_codec_profile(
        self,
        mode: str,
        metadata: dict[str, Any],
        help_text: str,
    )
   parse_avoptions(self, help_text: str)
   discover_capabilities(self, gpu_adapters: list[dict[str, Any]] | None = None)
   build_decode_input_args(self, input_path: str, decode_config: dict[str, Any] | None = None)
   build_encode_video_args(self, encode_config: dict[str, Any] | None = None)
   build_encode_output_args(self, output_path: str, encode_config: dict[str, Any] | None = None)
   is_available(self)
   get_version(self)
   _parse_supported_values(self, text: str, prefix: str)
   _build_option_args(self, options: dict[str, Any])
   _default_pix_fmt(self, codec: str)
   _run_command(self, cmd: list[str], *, timeout: int = 3600)
   _auto_detect_paths(self)
}
class node3 {
    _frame_bytes
    _width
    _height
   __init__(self, *, process: subprocess.Popen[bytes], width: int, height: int)
   read_frame(self)
   close(self)
}
class node111 {
    _width
    _height
   __init__(
        self,
        *,
        process: subprocess.Popen[bytes],
        width: int,
        height: int,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    )
   write_frame(self, frame: np.ndarray)
   close(self)
   output_frame_count(self)
}
class node49 {
    _stderr_thread
    _stderr_lines
    _latest_progress
    _progress_callback
    _process
   __init__(
        self,
        process: subprocess.Popen[bytes],
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    )
   _collect_stderr(self)
   _update_progress(self, snapshot: dict[str, str])
   _wait_for_process(self)
}
class node53 {
    result
    __context__
    exc
    ve_exc
   __signature__(cls)
   __new__(cls, value)
   __init__(self, *args, **kwds)
   _generate_next_value_(name, start, count, last_values)
   _missing_(cls, value)
   __repr__(self)
   __str__(self)
   __dir__(self)
   __format__(self, format_spec)
   __hash__(self)
   __reduce_ex__(self, proto)
   __deepcopy__(self,memo)
   __copy__(self)
   name(self)
   value(self)
}
class node56 {
    _member_names_
    _member_map_
    _value2member_map_
   __new__(
            metacls: type[_typeshed.Self],
            cls: str,
            bases: tuple[type, ...],
            classdict: _EnumDict,
            *,
            boundary: FlagBoundary | None = None,
            _simple: bool = False,
            **kwds: Any,
        )
   __prepare__(metacls, cls: str, bases: tuple[type, ...], **kwds: Any)
   __iter__(self: type[_EnumMemberT])
   __reversed__(self: type[_EnumMemberT])
   __contains__(self: type[Any], value: object)
   __getitem__(self: type[_EnumMemberT], name: str)
   __members__(self: type[_EnumMemberT])
   __len__(self)
   __bool__(self)
   __dir__(self)
   __call__(cls: type[_EnumMemberT], value: Any, names: None = None)
   __call__(
            cls,
            value: str,
            names: _EnumNames,
            *,
            module: str | None = None,
            qualname: str | None = None,
            type: type | None = None,
            start: int = 1,
            boundary: FlagBoundary | None = None,
        )
   __call__(cls: type[_EnumMemberT], value: Any, *values: Any)
}
class object {
    __doc__
    __dict__
    __module__
    __annotations__
   __class__(self)
   __class__(self, __type: type[object])
   __init__(self)
   __new__(cls)
   __setattr__(self, __name: str, __value: Any)
   __delattr__(self, __name: str)
   __eq__(self, __value: object)
   __ne__(self, __value: object)
   __str__(self)
   __repr__(self)
   __hash__(self)
   __format__(self, __format_spec: str)
   __getattribute__(self, __name: str)
   __sizeof__(self)
   __reduce__(self)
   __reduce_ex__(self, __protocol: SupportsIndex)
   __getstate__(self)
   __dir__(self)
   __init_subclass__(cls)
   __subclasshook__(cls, __subclass: type)
}
class node2 {
    parameters_str
    combined_parameters
    parent_namespace
    __pydantic_generic_metadata__
    config_wrapper
    original_model_post_init
    parent_parameters
    BaseModel
    types_namespace
    class_vars
    error_message
    __pydantic_decorators__
    model_computed_fields
    base_private_attributes
    private_attributes
    base_field_names
    cls
    mro
    generic_type_label
    __pydantic_complete__
    __pydantic_post_init__
    missing_parameters
    bases_str
    __pydantic_custom_init__
    parameters
    __pydantic_parent_namespace__
   __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        __pydantic_generic_metadata__: PydanticGenericMetadata | None = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: str | None = None,
        **kwargs: Any,
    )
   __getattr__(self, item: str)
   __prepare__(cls, *args: Any, **kwargs: Any)
   __instancecheck__(self, instance: Any)
   _collect_bases_data(bases: tuple[type[Any], ...])
   __fields__(self)
   __dir__(self)
}
class node31 {
    __pydantic_parent_namespace__
    model_config
    model_fields
    model_computed_fields
    __class_vars__
    __private_attributes__
    __signature__
    __pydantic_complete__
    __pydantic_core_schema__
    __pydantic_custom_init__
    __pydantic_decorators__
    __pydantic_generic_metadata__
    __pydantic_parent_namespace__
    __pydantic_post_init__
    __pydantic_root_model__
    __pydantic_serializer__
    __pydantic_validator__
    __pydantic_extra__
    __pydantic_fields_set__
    __pydantic_private__
    __pydantic_core_schema__
    __pydantic_validator__
    __pydantic_serializer__
    __slots__
    __pydantic_base_init__
    __repr_name__
    __repr_str__
    __pretty__
    __rich_repr__
   __init__(self, /, **data: Any)
   model_extra(self)
   model_fields_set(self)
   model_construct(cls, _fields_set: set[str] | None = None, **values: Any)
   model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False)
   model_dump(
        self,
        *,
        mode: Literal['json', 'python'] | str = 'python',
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal['none', 'warn', 'error'] = True,
        serialize_as_any: bool = False,
    )
   model_dump_json(
        self,
        *,
        indent: int | None = None,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal['none', 'warn', 'error'] = True,
        serialize_as_any: bool = False,
    )
   model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = 'validation',
    )
   model_parametrized_name(cls, params: tuple[type[Any], ...])
   model_post_init(self, __context: Any)
   model_rebuild(
        cls,
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: dict[str, Any] | None = None,
    )
   model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
    )
   model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: Any | None = None,
    )
   model_validate_strings(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        context: Any | None = None,
    )
   __get_pydantic_core_schema__(cls, source: type[BaseModel], handler: GetCoreSchemaHandler, /)
   __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
        /,
    )
   __pydantic_init_subclass__(cls, **kwargs: Any)
   __class_getitem__(
        cls, typevar_values: type[Any] | tuple[type[Any], ...]
    )
   __copy__(self)
   __deepcopy__(self, memo: dict[int, Any] | None = None)
   __getattr__(self, item: str)
   __setattr__(self, name: str, value: Any)
   __delattr__(self, item: str)
   _check_frozen(self, name: str, value: Any)
   __getstate__(self)
   __setstate__(self, state: dict[Any, Any])
   __eq__(self, other: Any)
   __init_subclass__(cls, **kwargs: Unpack[ConfigDict])
   __iter__(self)
   __repr__(self)
   __repr_args__(self)
   __str__(self)
   __fields__(self)
   __fields_set__(self)
   dict(  # noqa: D102
        self,
        *,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    )
   json(  # noqa: D102
        self,
        *,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        encoder: Callable[[Any], Any] | None = PydanticUndefined,  # type: ignore[assignment]
        models_as_dict: bool = PydanticUndefined,  # type: ignore[assignment]
        **dumps_kwargs: Any,
    )
   parse_obj(cls, obj: Any)
   parse_raw(  # noqa: D102
        cls,
        b: str | bytes,
        *,
        content_type: str | None = None,
        encoding: str = 'utf8',
        proto: DeprecatedParseProtocol | None = None,
        allow_pickle: bool = False,
    )
   parse_file(  # noqa: D102
        cls,
        path: str | Path,
        *,
        content_type: str | None = None,
        encoding: str = 'utf8',
        proto: DeprecatedParseProtocol | None = None,
        allow_pickle: bool = False,
    )
   from_orm(cls, obj: Any)
   construct(cls, _fields_set: set[str] | None = None, **values: Any)
   copy(
        self,
        *,
        include: AbstractSetIntStr | MappingIntStrAny | None = None,
        exclude: AbstractSetIntStr | MappingIntStrAny | None = None,
        update: Dict[str, Any] | None = None,  # noqa UP006
        deep: bool = False,
    )
   schema(  # noqa: D102
        cls, by_alias: bool = True, ref_template: str = DEFAULT_REF_TEMPLATE
    )
   schema_json(  # noqa: D102
        cls, *, by_alias: bool = True, ref_template: str = DEFAULT_REF_TEMPLATE, **dumps_kwargs: Any
    )
   validate(cls, value: Any)
   update_forward_refs(cls, **localns: Any)
   _iter(self, *args: Any, **kwargs: Any)
   _copy_and_set_values(self, *args: Any, **kwargs: Any)
   _get_value(cls, *args: Any, **kwargs: Any)
   _calculate_keys(self, *args: Any, **kwargs: Any)
}
class node22 {
    model_config
   __init__(
        __pydantic_self__,
        _case_sensitive: bool | None = None,
        _nested_model_default_partial_update: bool | None = None,
        _env_prefix: str | None = None,
        _env_file: DotenvType | None = ENV_FILE_SENTINEL,
        _env_file_encoding: str | None = None,
        _env_ignore_empty: bool | None = None,
        _env_nested_delimiter: str | None = None,
        _env_nested_max_split: int | None = None,
        _env_parse_none_str: str | None = None,
        _env_parse_enums: bool | None = None,
        _cli_prog_name: str | None = None,
        _cli_parse_args: bool | list[str] | tuple[str, ...] | None = None,
        _cli_settings_source: CliSettingsSource[Any] | None = None,
        _cli_parse_none_str: str | None = None,
        _cli_hide_none_type: bool | None = None,
        _cli_avoid_json: bool | None = None,
        _cli_enforce_required: bool | None = None,
        _cli_use_class_docs_for_groups: bool | None = None,
        _cli_exit_on_error: bool | None = None,
        _cli_prefix: str | None = None,
        _cli_flag_prefix_char: str | None = None,
        _cli_implicit_flags: bool | None = None,
        _cli_ignore_unknown_args: bool | None = None,
        _cli_kebab_case: bool | None = None,
        _cli_shortcuts: Mapping[str, str | list[str]] | None = None,
        _secrets_dir: PathType | None = None,
        **values: Any,
    )
   settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    )
   _settings_build_values(
        self,
        init_kwargs: dict[str, Any],
        _case_sensitive: bool | None = None,
        _nested_model_default_partial_update: bool | None = None,
        _env_prefix: str | None = None,
        _env_file: DotenvType | None = None,
        _env_file_encoding: str | None = None,
        _env_ignore_empty: bool | None = None,
        _env_nested_delimiter: str | None = None,
        _env_nested_max_split: int | None = None,
        _env_parse_none_str: str | None = None,
        _env_parse_enums: bool | None = None,
        _cli_prog_name: str | None = None,
        _cli_parse_args: bool | list[str] | tuple[str, ...] | None = None,
        _cli_settings_source: CliSettingsSource[Any] | None = None,
        _cli_parse_none_str: str | None = None,
        _cli_hide_none_type: bool | None = None,
        _cli_avoid_json: bool | None = None,
        _cli_enforce_required: bool | None = None,
        _cli_use_class_docs_for_groups: bool | None = None,
        _cli_exit_on_error: bool | None = None,
        _cli_prefix: str | None = None,
        _cli_flag_prefix_char: str | None = None,
        _cli_implicit_flags: bool | None = None,
        _cli_ignore_unknown_args: bool | None = None,
        _cli_kebab_case: bool | None = None,
        _cli_shortcuts: Mapping[str, str | list[str]] | None = None,
        _secrets_dir: PathType | None = None,
    )
}
class str {
   __new__(cls, object: object = ...)
   __new__(cls, object: ReadableBuffer, encoding: str = ..., errors: str = ...)
   capitalize(self: LiteralString)
   capitalize(self)
   casefold(self: LiteralString)
   casefold(self)
   center(self: LiteralString, __width: SupportsIndex, __fillchar: LiteralString = " ")
   center(self, __width: SupportsIndex, __fillchar: str = " ")
   count(self, x: str, __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...)
   encode(self, encoding: str = "utf-8", errors: str = "strict")
   endswith(
        self, __suffix: str | tuple[str, ...], __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...
    )
   expandtabs(self: LiteralString, tabsize: SupportsIndex = 8)
   expandtabs(self, tabsize: SupportsIndex = 8)
   find(self, __sub: str, __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...)
   format(self: LiteralString, *args: LiteralString, **kwargs: LiteralString)
   format(self, *args: object, **kwargs: object)
   format_map(self, map: _FormatMapMapping)
   index(self, __sub: str, __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...)
   isalnum(self)
   isalpha(self)
   isascii(self)
   isdecimal(self)
   isdigit(self)
   isidentifier(self)
   islower(self)
   isnumeric(self)
   isprintable(self)
   isspace(self)
   istitle(self)
   isupper(self)
   join(self: LiteralString, __iterable: Iterable[LiteralString])
   join(self, __iterable: Iterable[str])
   ljust(self: LiteralString, __width: SupportsIndex, __fillchar: LiteralString = " ")
   ljust(self, __width: SupportsIndex, __fillchar: str = " ")
   lower(self: LiteralString)
   lower(self)
   lstrip(self: LiteralString, __chars: LiteralString | None = None)
   lstrip(self, __chars: str | None = None)
   partition(self: LiteralString, __sep: LiteralString)
   partition(self, __sep: str)
   replace(
        self: LiteralString, __old: LiteralString, __new: LiteralString, __count: SupportsIndex = -1
    )
   replace(self, __old: str, __new: str, __count: SupportsIndex = -1)
   removeprefix(self: LiteralString, __prefix: LiteralString)
   removeprefix(self, __prefix: str)
   removesuffix(self: LiteralString, __suffix: LiteralString)
   removesuffix(self, __suffix: str)
   rfind(self, __sub: str, __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...)
   rindex(self, __sub: str, __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...)
   rjust(self: LiteralString, __width: SupportsIndex, __fillchar: LiteralString = " ")
   rjust(self, __width: SupportsIndex, __fillchar: str = " ")
   rpartition(self: LiteralString, __sep: LiteralString)
   rpartition(self, __sep: str)
   rsplit(self: LiteralString, sep: LiteralString | None = None, maxsplit: SupportsIndex = -1)
   rsplit(self, sep: str | None = None, maxsplit: SupportsIndex = -1)
   rstrip(self: LiteralString, __chars: LiteralString | None = None)
   rstrip(self, __chars: str | None = None)
   split(self: LiteralString, sep: LiteralString | None = None, maxsplit: SupportsIndex = -1)
   split(self, sep: str | None = None, maxsplit: SupportsIndex = -1)
   splitlines(self: LiteralString, keepends: bool = False)
   splitlines(self, keepends: bool = False)
   startswith(
        self, __prefix: str | tuple[str, ...], __start: SupportsIndex | None = ..., __end: SupportsIndex | None = ...
    )
   strip(self: LiteralString, __chars: LiteralString | None = None)
   strip(self, __chars: str | None = None)
   swapcase(self: LiteralString)
   swapcase(self)
   title(self: LiteralString)
   title(self)
   translate(self, __table: _TranslateTable)
   upper(self: LiteralString)
   upper(self)
   zfill(self: LiteralString, __width: SupportsIndex)
   zfill(self, __width: SupportsIndex)
   maketrans(__x: dict[int, _T] | dict[str, _T] | dict[str | int, _T])
   maketrans(__x: str, __y: str)
   maketrans(__x: str, __y: str, __z: str)
   __add__(self: LiteralString, __value: LiteralString)
   __add__(self, __value: str)
   __contains__(self, __key: str)
   __eq__(self, __value: object)
   __ge__(self, __value: str)
   __getitem__(self, __key: SupportsIndex | slice)
   __gt__(self, __value: str)
   __hash__(self)
   __iter__(self: LiteralString)
   __iter__(self)
   __le__(self, __value: str)
   __len__(self)
   __lt__(self, __value: str)
   __mod__(self: LiteralString, __value: LiteralString | tuple[LiteralString, ...])
   __mod__(self, __value: Any)
   __mul__(self: LiteralString, __value: SupportsIndex)
   __mul__(self, __value: SupportsIndex)
   __ne__(self, __value: object)
   __rmul__(self: LiteralString, __value: SupportsIndex)
   __rmul__(self, __value: SupportsIndex)
   __getnewargs__(self)
}
class node145 {
    _compiled_call_impl
    _backward_pre_hooks
    training
    _is_full_backward_hook
    _forward_hooks_with_kwargs
    _forward_hooks_always_called
    _non_persistent_buffers_set
    _forward_pre_hooks_with_kwargs
    _state_dict_pre_hooks
    _forward_pre_hooks
    _state_dict_hooks
    _load_state_dict_pre_hooks
    _load_state_dict_post_hooks
    dump_patches
    _version
    training
    _parameters
    _buffers
    _non_persistent_buffers_set
    _backward_pre_hooks
    _backward_hooks
    _is_full_backward_hook
    _forward_hooks
    _forward_hooks_with_kwargs
    _forward_hooks_always_called
    _forward_pre_hooks
    _forward_pre_hooks_with_kwargs
    _state_dict_hooks
    _load_state_dict_pre_hooks
    _state_dict_pre_hooks
    _load_state_dict_post_hooks
    _modules
    call_super_init
    _compiled_call_impl
    forward
    __call__
    T_destination
   __init__(self, *args: Any, **kwargs: Any)
   register_buffer(
        self, name: str, tensor: Tensor | None, persistent: bool = True
    )
   register_parameter(self, name: str, param: Parameter | None)
   add_module(self, name: str, module: Optional["Module"])
   register_module(self, name: str, module: Optional["Module"])
   get_submodule(self, target: str)
   set_submodule(
        self, target: str, module: "Module", strict: bool = False
    )
   get_parameter(self, target: str)
   get_buffer(self, target: str)
   get_extra_state(self)
   set_extra_state(self, state: Any)
   _apply(self, fn, recurse=True)
   apply(self, fn: Callable[["Module"], None])
   cuda(self, device: int | device | None = None)
   ipu(self, device: int | device | None = None)
   xpu(self, device: int | device | None = None)
   mtia(self, device: int | device | None = None)
   cpu(self)
   type(self, dst_type: dtype | str)
   float(self)
   double(self)
   half(self)
   bfloat16(self)
   to_empty(self, *, device: DeviceLikeType | None, recurse: bool = True)
   to(
        self,
        device: DeviceLikeType | None = ...,
        dtype: dtype | None = ...,
        non_blocking: bool = ...,
    )
   to(self, dtype: dtype, non_blocking: bool = ...)
   to(self, tensor: Tensor, non_blocking: bool = ...)
   to(self, *args, **kwargs)
   register_full_backward_pre_hook(
        self,
        hook: Callable[["Module", _grad_t], _grad_t | None],
        prepend: bool = False,
    )
   register_backward_hook(
        self, hook: Callable[["Module", _grad_t, _grad_t], _grad_t | None]
    )
   register_full_backward_hook(
        self,
        hook: Callable[["Module", _grad_t, _grad_t], _grad_t | None],
        prepend: bool = False,
    )
   _get_backward_hooks(self)
   _get_backward_pre_hooks(self)
   _maybe_warn_non_full_backward_hook(self, inputs, result, grad_fn)
   register_forward_pre_hook(
        self,
        hook: Callable[[T, tuple[Any, ...]], Any | None]
        | Callable[
            [T, tuple[Any, ...], dict[str, Any]], tuple[Any, dict[str, Any]] | None
        ],
        *,
        prepend: bool = False,
        with_kwargs: bool = False,
    )
   register_forward_hook(
        self,
        hook: Callable[[T, tuple[Any, ...], Any], Any | None]
        | Callable[[T, tuple[Any, ...], dict[str, Any], Any], Any | None],
        *,
        prepend: bool = False,
        with_kwargs: bool = False,
        always_call: bool = False,
    )
   _slow_forward(self, *input, **kwargs)
   _wrapped_call_impl(self, *args, **kwargs)
   _call_impl(self, *args, **kwargs)
   __getstate__(self)
   __setstate__(self, state)
   __getattr__(self, name: str)
   __setattr__(self, name: str, value: Union[Tensor, "Module"])
   __delattr__(self, name)
   _register_state_dict_hook(self, hook)
   register_state_dict_post_hook(self, hook)
   register_state_dict_pre_hook(self, hook)
   _save_to_state_dict(self, destination, prefix, keep_vars)
   state_dict(
        self,
        *,
        destination: T_destination,
        prefix: str = ...,
        keep_vars: bool = ...,
    )
   state_dict(
        self,
        *,
        prefix: str = ...,
        keep_vars: bool = ...,
    )
   state_dict(self, *args, destination=None, prefix="", keep_vars=False)
   _register_load_state_dict_pre_hook(self, hook, with_module=False)
   register_load_state_dict_pre_hook(self, hook)
   register_load_state_dict_post_hook(self, hook)
   _load_from_state_dict(
        self,
        state_dict,
        prefix,
        local_metadata,
        strict,
        missing_keys,
        unexpected_keys,
        error_msgs,
    )
   load_state_dict(
        self, state_dict: Mapping[str, Any], strict: bool = True, assign: bool = False
    )
   _named_members(
        self, get_members_fn, prefix="", recurse=True, remove_duplicate: bool = True
    )
   parameters(self, recurse: bool = True)
   named_parameters(
        self, prefix: str = "", recurse: bool = True, remove_duplicate: bool = True
    )
   buffers(self, recurse: bool = True)
   named_buffers(
        self, prefix: str = "", recurse: bool = True, remove_duplicate: bool = True
    )
   children(self)
   named_children(self)
   modules(self, remove_duplicate: bool = True)
   named_modules(
        self,
        memo: set["Module"] | None = None,
        prefix: str = "",
        remove_duplicate: bool = True,
    )
   train(self, mode: bool = True)
   eval(self)
   requires_grad_(self, requires_grad: bool = True)
   zero_grad(self, set_to_none: bool = True)
   share_memory(self)
   _get_name(self)
   extra_repr(self)
   __repr__(self)
   __dir__(self)
   _replicate_for_data_parallel(self)
   compile(self, *args, **kwargs)
}
class node172 {
   __len__(self)
}
class node152 {
   __contains__(self, x: object, /)
}
class node160 {
   __hash__(self)
}
class node154 {
   __iter__(self)
}
class node79 {
   __next__(self)
   __iter__(self)
}
class node90 {
   __reversed__(self)
}
class node32 {
   __getitem__(self, index: int)
   __getitem__(self, index: slice)
   index(self, value: Any, start: int = 0, stop: int = ...)
   count(self, value: Any)
   __contains__(self, value: object)
   __iter__(self)
   __reversed__(self)
}

object  -->  BaseException
BaseException  -->  Exception
object  -->  node87
node87  -->  node60
object  -->  node113
object  -->  node82
node145  -->  node23
node145  -->  node75
node145  -->  node100
node145  -->  node39
node145  -->  node143
node145  -->  node163
node145  -->  node135
node145  -->  node147
node145  -->  node69
node145  -->  node104
node145  -->  node17
node145  -->  node127
node145  -->  node8
node145  -->  node24
node145  -->  node6
node145  -->  node29
node145  -->  node156
node145  -->  node9
node145  -->  node7
node145  -->  node171
node145  -->  node102
node145  -->  node72
node145  -->  node43
node145  -->  node5
node145  -->  node64
node145  -->  node14
node145  -->  node44
node145  -->  node168
node145  -->  node38
node145  -->  node78
node145  -->  node170
node145  -->  node130
node145  -->  node94
node145  -->  node25
node145  -->  node1
node145  -->  node13
node145  -->  node128
node145  -->  node157
node145  -->  node116
node145  -->  node101
node145  -->  node158
node145  -->  node74
node145  -->  node10
node145  -->  node133
node145  -->  node109
node145  -->  node117
node145  -->  node46
node145  -->  node20
node145  -->  node4
node145  -->  node63
node145  -->  node140
node145  -->  node185
node145  -->  node166
node145  -->  node51
node145  -->  node103
node145  -->  node180
node145  -->  node150
node145  -->  node52
node145  -->  node136
node145  -->  node70
node145  -->  node55
node145  -->  node149
node145  -->  node71
node145  -->  node76
node145  -->  node173
node145  -->  node15
node145  -->  node123
node145  -->  node28
node145  -->  node148
node145  -->  node139
node145  -->  node61
node145  -->  node179
node145  -->  node181
node145  -->  node40
node145  -->  node86
node145  -->  node16
node145  -->  node169
node145  -->  node33
node145  -->  node106
node145  -->  node21
node145  -->  node175
node145  -->  node115
node145  -->  node77
node145  -->  node132
node145  -->  node120
node145  -->  node138
node145  -->  node84
node145  -->  node34
node145  -->  node141
node145  -->  node182
node145  -->  node26
node145  -->  node65
node145  -->  node137
node145  -->  node112
node145  -->  node91
node145  -->  node89
node145  -->  node11
node145  -->  node105
node145  -->  node67
node145  -->  node30
node145  -->  node19
node145  -->  node59
node145  -->  node159
node145  -->  node45
node145  -->  node96
node145  -->  node119
node145  -->  node97
node145  -->  node114
node145  -->  node80
node145  -->  node177
node145  -->  node47
node145  -->  node176
node145  -->  node85
node145  -->  node50
node145  -->  node58
node145  -->  node81
node145  -->  node68
node145  -->  node162
node145  -->  node183
node145  -->  node73
node145  -->  node129
node145  -->  node66
node145  -->  node108
node145  -->  node42
node145  -->  node98
object  -->  node121
node87  -->  node134
node134  -->  node48
node134  -->  node153
node134  -->  node155
object  -->  node118
node53  -->  node131
str  -->  node131
node22  -->  node167
Exception  -->  node142
node174  -->  node151
node174  -->  node165
node174  -->  node178
node174  -->  node122
node174  -->  node12
node174  -->  node54
node174  -->  node161
node174  -->  node62
node174  -->  node27
node174  -->  node41
node174  -->  node37
node31  -->  node174
Exception  -->  node0
object  -->  node35
object  -->  node107
object  -->  node83
object  -->  node93
object  -->  node184
node60  -->  node125
node60  -->  node99
node60  -->  node164
object  -->  node92
object  -->  node144
object  -->  node146
object  -->  node95
node60  -->  node124
object  -->  node18
node49  -->  node3
node49  -->  node111
object  -->  node49
node56 "isinstanceof" ..>  node53
object  -->  node53
node160  ..>  node53
node154  ..>  node56
node79  ..>  node56
node32  ..>  node56
node160  ..>  object
node57  -->  node2
object  -->  node31
node2 "isinstanceof" ..>  node31
node154  ..>  node31
node31  -->  node22
node160  ..>  str
node79  ..>  str
node32  -->  str
object  -->  node145
node152  -->  node172
node154  -->  node172
node154  -->  node90
