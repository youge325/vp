classDiagram
direction TB
class node12 {
    invoke
}
class node26 {
    UnlistenFn
    listen
}
class node37 {
    AddCircleOutline
    BookOutline
    ColorFillOutline
    ColorWandOutline
    ConstructOutline
    HardwareChipOutline
    OptionsOutline
    SendOutline
}
class node53 {
    afterEach
    beforeEach
    describe
    it
}
class node82 {
    mount
}
class node60 {
    reactive
}
class node44 {
    Component
    computed
    onBeforeUnmount
    onMounted
}
class node49 {
    createApp
}
class node28 {
    FilterStep
    FilterStepKind
    computed
}
class node30 {
    ResumeConflictAction
    ResumeConflictDescriptor
    computed
}
class node6 {
    ModuleKey
    RouterLink
    WORKBENCH_MODULES
    WorkbenchModuleDefinition
    computed
    getTaskStatusLabel
    getVisibleEncoderProfiles
    useEnvStore
    useMediaStore
    useRoute
    useTaskStore
    useWorkbenchEditor
}
class node3 {
    TaskConsole
    beforeEach
    describe
    expect
    it
    mount
    vi
}
class node77 {
    computed
    nextTick
    ref
    useTaskStore
    watch
}
class node8 {
    computed
    getEditingScopeLabel
    useMediaStore
    usePresetStore
    useWorkbenchEditor
}
class node81 {
    EnvironmentCheckResult
    TensorBackend
    computed
    getAvailableEngines
    getVisibleBackends
    shouldShowEngineSelector
}
class node25 {
    AnimeConfig
}
class node13 {
    BackendDeviceSupport
}
class node72 {
    DecodeConfig
}
class node0 {
    EncodeConfig
    RateControlConfig
}
class node29 {
    EnvironmentCheckResult
}
class node1 {
    BackendDeviceSupport
    EnvironmentCheckResult
    FfmpegInfo
    GpuInfo
    JsonValue
    OnnxModels
    OnnxRuntimeInfo
    RifeModel
    RuntimeInfo
    TensorBackends
    TensorEngines
}
class node2 {
    FfmpegInfo
}
class node55 {
    FilterStep
}
class node15 {
    GpuInfo
}
class node14 {
    InterpolationConfig
}
class node22 {
    OnnxModels
}
class node61 {
    OnnxRuntimeInfo
}
class node47 {
    OutputConfig
}
class node45 {
    FilterStep
    PostprocessConfig
}
class node39 {
    FilterStep
    PreprocessConfig
}
class node50 {
    RateControlConfig
}
class node31 {
    RifeModel
}
class node79 {
    RuntimeInfo
}
class node52 {
    SuperResolutionConfig
}
class node62 {
    TaskCompletedPayload
}
class node59 {
    TaskErrorCode
}
class node40 {
    TaskErrorCode
}
class node78 {
    TaskEventName
}
class node43 {
    TaskLogPayload
}
class node67 {
    TaskProgressPayload
}
class node10 {
    DecodeConfig
    EncodeConfig
    OutputConfig
    TaskRequest
    WorkflowConfig
}
class node69 {
    TensorBackends
}
class node66 {
    TensorEngines
}
class node21 {
    DecodeConfig
    EncodeConfig
    OutputConfig
    WorkbenchPreset
    WorkflowConfig
}
class node70 {
    AnimeConfig
    InterpolationConfig
    PostprocessConfig
    PreprocessConfig
    SuperResolutionConfig
    WorkflowConfig
}
class node32 {
    TERMINAL_PROGRESS_PREFIX
    appendTaskLog
    applyTaskCancelled
    applyTaskCancelling
    applyTaskCompleted
    applyTaskError
    applyTaskPaused
    applyTaskProgress
    applyTaskResumed
    createIdleTaskState
    describe
    expect
    it
}
class node48 {
    MediaTaskState
    ResumeStatus
    TASK_ERROR_CODES
    TERMINAL_PROGRESS_PREFIX
    TaskCompletedPayload
    TaskError
    TaskLogPayload
    TaskProgressPayload
    appendTaskLog
    applyTaskCancelled
    applyTaskCancelling
    applyTaskCompleted
    applyTaskError
    applyTaskPaused
    applyTaskProgress
    applyTaskResumeStatus
    applyTaskResumed
    createIdleTaskState
}
class node27 {
    EnvironmentCheckResult
    MediaItem
    buildTaskRequest
    createDefaultDecodeConfig
    createDefaultEncodeConfig
    createDefaultWorkbenchPreset
    createIdleTaskState
    describe
    expect
    it
    resolvePrimaryMode
}
class node41 {
    DecodeConfig
    DecoderProfileSpec
    EncodeConfig
    EncoderProfileSpec
    EnvironmentCheckResult
    InferenceEngine
    MediaItem
    OutputConfig
    ResumeMode
    TaskError
    TaskRequest
    WorkbenchPreset
    WorkflowConfig
    WorkflowMode
    buildTaskRequest
    cloneDecodeConfig
    cloneEncodeConfig
    cloneOutputConfig
    cloneWorkbenchPreset
    cloneWorkflowConfig
    createDefaultDecodeConfig
    createDefaultEncodeConfig
    createDefaultWorkbenchPreset
    formatNumber
    getVisibleDecoderProfiles
    getVisibleEncoderProfiles
    normalizeTaskError
    resolvePrimaryMode
}
class node76 {
    EnvironmentCheckPayload
    ResumeInspectionResult
    ResumeStatus
    TASK_EVENT_NAMES
    TaskCompletedPayload
    TaskError
    TaskLogPayload
    TaskProgressPayload
    TaskRequest
    UnlistenFn
    VideoInfoResult
    WorkbenchPreset
    cancelTask
    checkEnvironment
    checkResumeState
    inspectVideo
    invoke
    listen
    listenTaskEvents
    loadWorkbenchPreset
    openOutputLocation
    pauseTask
    pickInputs
    pickOutputDirectory
    resumeTask
    saveWorkbenchPreset
    startTask
}
class node80 {
    AddCircleOutline
    BookOutline
    CONTAINER_OPTIONS
    ColorFillOutline
    ColorWandOutline
    ConstructOutline
    HardwareChipOutline
    OptionsOutline
    ProcessOrder
    RIFE_MODELS
    RateControlMode
    SendOutline
    WORKBENCH_MODULES
    WORKFLOW_LABELS
    WorkbenchModuleDefinition
    WorkflowMode
}
class node58 {
    createPinia
    defineStore
    setActivePinia
}
class node11 {
    WORKBENCH_MODULES
    beforeEach
    describe
    expect
    it
    router
}
class node9 {
    DecodeModuleView
    EncodeModuleView
    EnhanceModuleView
    HomeModuleView
    InputModuleView
    PostprocessModuleView
    PreprocessModuleView
    RenderModuleView
    WORKBENCH_MODULES
    createRouter
    createWebHashHistory
    router
}
class node68 {
    JsonValue
}
class node34 {
    CapabilityValue
    DecodeConfig
    EncodeConfig
    EnvironmentCheckResult
    createDefaultDecodeConfig
    createDefaultEncodeConfig
    defaultRateControlValue
    getVisibleDecoderProfiles
    getVisibleEncoderProfiles
    inferHwaccelForProfile
    normalizeDecodeConfig
    normalizeEncodeConfig
    seedProfileOptions
}
class node17 {
    BACKEND_LABELS
    BatchState
    ENGINE_LABELS
    EncoderProfileSpec
    MediaItem
    WORKFLOW_LABELS
    getEditingScopeLabel
    getProbeSourceLabel
    getTaskStatusLabel
    getWorkflowSummaryLabel
    groupEncoderProfilesByFamily
    resolvePrimaryMode
}
class node65 {
    EnvironmentCheckResult
    InferenceEngine
    TensorBackend
    getAvailableEngines
    getVisibleBackends
    shouldShowEngineSelector
}
class node18 {
    RouterView
    StepRail
    WORKBENCH_MODULES
    WorkbenchModuleDefinition
    computed
    createDefaultWorkbenchPreset
    getTaskStatusLabel
    onBeforeUnmount
    onMounted
    useEnvStore
    usePresetStore
    useRoute
    useTaskStore
}
class node75 {
    App
    createApp
    createPinia
    router
    style.css
}
class node64
class node7 {
    AppEnv
    BatchState
    CapabilityOptionSpec
    CapabilityValue
    Component
    DecodeConfig
    DecoderProfileSpec
    EncodeConfig
    EncoderProfileSpec
    EnvironmentCheckPayload
    EnvironmentCheckResult
    FilterStepKind
    FpsMode
    GpuAdapter
    InferenceEngine
    MediaItem
    MediaTaskState
    ModuleKey
    OperationIssue
    OperationIssueScope
    OutputConfig
    ProcessOrder
    RateControlMode
    ResumeConflictAction
    ResumeConflictDescriptor
    ResumeConflictKind
    ResumeInspectionResult
    ResumeMode
    ResumeStatus
    TASK_ERROR_CODES
    TASK_EVENT_NAMES
    TERMINAL_PROGRESS_PREFIX
    TaskError
    TaskErrorCode
    TaskEventName
    TensorBackend
    VideoInfoResult
    WorkbenchModuleDefinition
    WorkflowConfig
    WorkflowMode
}
class node35 {
    AppEnv
    EnvironmentCheckPayload
    EnvironmentCheckResult
    GpuAdapter
    OperationIssue
    OperationIssueScope
    TaskError
    computed
    defineStore
    getVisibleEncoderProfiles
    invokeCheckEnvironment
    normalizeTaskError
    reactive
    ref
    useEnvStore
}
class node23 {
    MediaItem
    VideoInfoResult
    cloneDecodeConfig
    cloneEncodeConfig
    cloneOutputConfig
    cloneWorkflowConfig
    computed
    defineStore
    invokeInspectVideo
    invokePickInputs
    normalizeTaskError
    ref
    useMediaStore
}
class node63 {
    CapabilityValue
    DecodeConfig
    EncodeConfig
    EnvironmentCheckResult
    WorkbenchPreset
    cloneDecodeConfig
    cloneEncodeConfig
    cloneOutputConfig
    cloneWorkbenchPreset
    cloneWorkflowConfig
    computed
    createDefaultWorkbenchPreset
    defaultRateControlValue
    defineStore
    getVisibleDecoderProfiles
    getVisibleEncoderProfiles
    inferHwaccelForProfile
    invokeLoadWorkbenchPreset
    invokePickOutputDirectory
    invokeSaveWorkbenchPreset
    normalizeDecode
    normalizeEncode
    normalizeTaskError
    reactive
    ref
    seedProfileOptions
    useEnvStore
    usePresetStore
}
class node73 {
    BatchState
    ResumeConflictAction
    ResumeConflictDescriptor
    ResumeConflictKind
    ResumeInspectionResult
    ResumeMode
    ResumeStatus
    TASK_ERROR_CODES
    TaskCompletedPayload
    TaskError
    TaskLogPayload
    TaskProgressPayload
    UnlistenFn
    appendTaskLog
    applyTaskCancelled
    applyTaskCancelling
    applyTaskCompleted
    applyTaskError
    applyTaskPaused
    applyTaskProgress
    applyTaskResumeStatus
    applyTaskResumed
    buildTaskRequest
    cancelTask
    checkResumeState
    computed
    createIdleTaskState
    defineStore
    listenTaskEvents
    normalizeTaskError
    openOutputLocation
    pauseTask
    reactive
    ref
    resumeTask
    startTask
    useMediaStore
    useTaskStore
}
class node24 {
    EnvironmentCheckPayload
    EnvironmentCheckResult
    ResumeInspectionResult
    VideoInfoResult
    WorkbenchPreset
    afterEach
    beforeEach
    cloneWorkflowConfig
    createDefaultWorkbenchPreset
    createPinia
    describe
    expect
    getVisibleDecoderProfiles
    it
    setActivePinia
    useEnvStore
    useMediaStore
    usePresetStore
    useTaskStore
    vi
}
class node42 {
    CapabilityOptionSpec
    DecodeConfig
    DecodeModuleView
    EncodeConfig
    MediaItem
    OutputConfig
    WorkbenchPreset
    WorkflowConfig
    beforeEach
    createPinia
    describe
    expect
    it
    mount
    setActivePinia
    vi
}
class node4 {
    CapabilityOptionSpec
    CapabilityValue
    computed
    getVisibleDecoderProfiles
    useEnvStore
    usePresetStore
    useWorkbenchEditor
}
class node74 {
    EncodeConfig
    EncodeModuleView
    MediaItem
    OutputConfig
    WorkbenchPreset
    WorkflowConfig
    beforeEach
    createPinia
    describe
    expect
    it
    mount
    setActivePinia
    vi
}
class node38 {
    CONTAINER_OPTIONS
    CapabilityOptionSpec
    CapabilityValue
    RateControlMode
    computed
    getVisibleEncoderProfiles
    useEnvStore
    usePresetStore
    useWorkbenchEditor
}
class node54 {
    EnhanceModuleView
    WorkbenchPreset
    WorkflowConfig
    beforeEach
    createPinia
    describe
    expect
    it
    mount
    setActivePinia
    vi
}
class node36 {
    BACKEND_LABELS
    ENGINE_LABELS
    FpsMode
    InferenceEngine
    ProcessOrder
    RIFE_MODELS
    TensorBackend
    computed
    getAvailableEngines
    getVisibleBackends
    shouldShowEngineSelector
    useEnvStore
    usePresetStore
    useWorkbenchEditor
}
class node71 {
    computed
    getProbeSourceLabel
    groupEncoderProfilesByFamily
    useEnvStore
    useMediaStore
}
class node56 {
    InputModuleView
    MediaItem
    beforeEach
    createPinia
    describe
    expect
    it
    mount
    setActivePinia
    vi
}
class node46 {
    computed
    formatNumber
    getWorkflowSummaryLabel
    ref
    useEnvStore
    useMediaStore
    usePresetStore
}
class node19 {
    FilterChainEditor
    computed
    usePresetStore
    useWorkbenchEditor
}
class node20 {
    FilterChainEditor
    computed
    usePresetStore
    useWorkbenchEditor
}
class node5 {
    RenderModuleView
    beforeEach
    createPinia
    describe
    expect
    it
    mount
    reactive
    setActivePinia
    vi
}
class node33 {
    ResumeConflictAction
    ResumeConflictDialog
    TaskConsole
    computed
    useEnvStore
    useTaskStore
}
class node57 {
    expect
    vi
}
class vue {
    nextTick
    ref
    watch
}
class node16 {
    RouterLink
    RouterView
    createRouter
    createWebHashHistory
    useRoute
}

node44  -->  node28
node55  -->  node28
node7  -->  node28
node44  -->  node30
node7  -->  node30
node7  -->  node30
node44  -->  node6
node8  -->  node6
node41  -->  node6
node80  -->  node6
node17  -->  node6
node7  -->  node6
node7  -->  node6
node35  -->  node6
node23  -->  node6
node73  -->  node6
node16  -->  node6
node16  -->  node6
node53  -->  node3
node53  -->  node3
node53  -->  node3
node82  -->  node3
node77  -->  node3
node57  -->  node3
node57  -->  node3
node44  -->  node77
node73  -->  node77
vue  -->  node77
vue  -->  node77
vue  -->  node77
node44  -->  node8
node17  -->  node8
node23  -->  node8
node63  -->  node8
node44  -->  node81
node65  -->  node81
node65  -->  node81
node65  -->  node81
node7  -->  node81
node7  -->  node81
node50  -->  node0
node1  -->  node29
node13  -->  node1
node2  -->  node1
node15  -->  node1
node22  -->  node1
node61  -->  node1
node31  -->  node1
node79  -->  node1
node69  -->  node1
node66  -->  node1
node68  -->  node1
node55  -->  node45
node55  -->  node39
node59  -->  node40
node72  -->  node10
node0  -->  node10
node47  -->  node10
node70  -->  node10
node72  -->  node21
node0  -->  node21
node47  -->  node21
node70  -->  node21
node25  -->  node70
node14  -->  node70
node45  -->  node70
node39  -->  node70
node52  -->  node70
node53  -->  node32
node53  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node48  -->  node32
node7  -->  node32
node57  -->  node32
node62  -->  node48
node43  -->  node48
node67  -->  node48
node7  -->  node48
node7  -->  node48
node7  -->  node48
node7  -->  node48
node7  -->  node48
node53  -->  node27
node53  -->  node27
node48  -->  node27
node41  -->  node27
node41  -->  node27
node41  -->  node27
node41  -->  node27
node41  -->  node27
node7  -->  node27
node7  -->  node27
node57  -->  node27
node72  -->  node41
node0  -->  node41
node47  -->  node41
node10  -->  node41
node21  -->  node41
node70  -->  node41
node7  -->  node41
node7  -->  node41
node7  -->  node41
node7  -->  node41
node7  -->  node41
node7  -->  node41
node7  -->  node41
node7  -->  node41
node12  -->  node76
node26  -->  node76
node26  -->  node76
node62  -->  node76
node43  -->  node76
node67  -->  node76
node10  -->  node76
node21  -->  node76
node7  -->  node76
node7  -->  node76
node7  -->  node76
node7  -->  node76
node7  -->  node76
node7  -->  node76
node37  -->  node80
node37  -->  node80
node37  -->  node80
node37  -->  node80
node37  -->  node80
node37  -->  node80
node37  -->  node80
node37  -->  node80
node7  -->  node80
node7  -->  node80
node7  -->  node80
node7  -->  node80
node53  -->  node11
node53  -->  node11
node53  -->  node11
node80  -->  node11
node9  -->  node11
node57  -->  node11
node80  -->  node9
node4  -->  node9
node38  -->  node9
node36  -->  node9
node71  -->  node9
node46  -->  node9
node19  -->  node9
node20  -->  node9
node33  -->  node9
node16  -->  node9
node16  -->  node9
node72  -->  node34
node0  -->  node34
node41  -->  node34
node41  -->  node34
node41  -->  node34
node41  -->  node34
node7  -->  node34
node7  -->  node34
node41  -->  node17
node80  -->  node17
node7  -->  node17
node7  -->  node17
node7  -->  node17
node7  -->  node65
node7  -->  node65
node7  -->  node65
node44  -->  node18
node44  -->  node18
node44  -->  node18
node6  -->  node18
node41  -->  node18
node80  -->  node18
node17  -->  node18
node7  -->  node18
node35  -->  node18
node63  -->  node18
node73  -->  node18
node16  -->  node18
node16  -->  node18
node49  -->  node75
node58  -->  node75
node9  -->  node75
node18  -->  node75
node64  -->  node75
node44  -->  node7
node72  -->  node7
node0  -->  node7
node47  -->  node7
node59  -->  node7
node78  -->  node7
node70  -->  node7
node60  -->  node35
node44  -->  node35
node41  -->  node35
node41  -->  node35
node76  -->  node35
node58  -->  node35
node7  -->  node35
node7  -->  node35
node7  -->  node35
node7  -->  node35
node7  -->  node35
node7  -->  node35
node7  -->  node35
vue  -->  node35
node44  -->  node23
node41  -->  node23
node41  -->  node23
node41  -->  node23
node41  -->  node23
node41  -->  node23
node76  -->  node23
node76  -->  node23
node58  -->  node23
node7  -->  node23
node7  -->  node23
vue  -->  node23
node60  -->  node63
node44  -->  node63
node72  -->  node63
node0  -->  node63
node21  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node41  -->  node63
node76  -->  node63
node76  -->  node63
node76  -->  node63
node58  -->  node63
node34  -->  node63
node34  -->  node63
node34  -->  node63
node34  -->  node63
node34  -->  node63
node7  -->  node63
node7  -->  node63
node35  -->  node63
vue  -->  node63
node26  -->  node73
node60  -->  node73
node44  -->  node73
node62  -->  node73
node43  -->  node73
node67  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node48  -->  node73
node41  -->  node73
node41  -->  node73
node76  -->  node73
node76  -->  node73
node76  -->  node73
node76  -->  node73
node76  -->  node73
node76  -->  node73
node76  -->  node73
node58  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node7  -->  node73
node23  -->  node73
vue  -->  node73
node53  -->  node24
node53  -->  node24
node53  -->  node24
node53  -->  node24
node21  -->  node24
node41  -->  node24
node41  -->  node24
node41  -->  node24
node58  -->  node24
node58  -->  node24
node7  -->  node24
node7  -->  node24
node7  -->  node24
node7  -->  node24
node35  -->  node24
node23  -->  node24
node63  -->  node24
node73  -->  node24
node57  -->  node24
node57  -->  node24
node53  -->  node42
node53  -->  node42
node53  -->  node42
node82  -->  node42
node72  -->  node42
node0  -->  node42
node47  -->  node42
node21  -->  node42
node70  -->  node42
node58  -->  node42
node58  -->  node42
node7  -->  node42
node7  -->  node42
node4  -->  node42
node57  -->  node42
node57  -->  node42
node44  -->  node4
node8  -->  node4
node41  -->  node4
node7  -->  node4
node7  -->  node4
node35  -->  node4
node63  -->  node4
node53  -->  node74
node53  -->  node74
node53  -->  node74
node82  -->  node74
node0  -->  node74
node47  -->  node74
node21  -->  node74
node70  -->  node74
node58  -->  node74
node58  -->  node74
node7  -->  node74
node38  -->  node74
node57  -->  node74
node57  -->  node74
node44  -->  node38
node8  -->  node38
node41  -->  node38
node80  -->  node38
node7  -->  node38
node7  -->  node38
node7  -->  node38
node35  -->  node38
node63  -->  node38
node53  -->  node54
node53  -->  node54
node53  -->  node54
node82  -->  node54
node21  -->  node54
node70  -->  node54
node58  -->  node54
node58  -->  node54
node36  -->  node54
node57  -->  node54
node57  -->  node54
node44  -->  node36
node8  -->  node36
node80  -->  node36
node17  -->  node36
node17  -->  node36
node65  -->  node36
node65  -->  node36
node65  -->  node36
node7  -->  node36
node7  -->  node36
node7  -->  node36
node7  -->  node36
node35  -->  node36
node63  -->  node36
node44  -->  node71
node17  -->  node71
node17  -->  node71
node35  -->  node71
node23  -->  node71
node53  -->  node56
node53  -->  node56
node53  -->  node56
node82  -->  node56
node58  -->  node56
node58  -->  node56
node7  -->  node56
node46  -->  node56
node57  -->  node56
node57  -->  node56
node44  -->  node46
node41  -->  node46
node17  -->  node46
node35  -->  node46
node23  -->  node46
node63  -->  node46
vue  -->  node46
node44  -->  node19
node28  -->  node19
node8  -->  node19
node63  -->  node19
node44  -->  node20
node28  -->  node20
node8  -->  node20
node63  -->  node20
node53  -->  node5
node53  -->  node5
node53  -->  node5
node82  -->  node5
node60  -->  node5
node58  -->  node5
node58  -->  node5
node33  -->  node5
node57  -->  node5
node57  -->  node5
node44  -->  node33
node30  -->  node33
node77  -->  node33
node7  -->  node33
node35  -->  node33
node73  -->  node33
