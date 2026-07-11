import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { groupEncoderProfilesByFamily, getProbeSourceLabel } from '@/services/format/labels'

export function useHomeDashboard() {
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()

  const issue = computed(() => envStore.env.issue)
  const isChecking = computed(() => envStore.env.isChecking)
  const isBootstrapping = computed(() => envStore.env.isBootstrapping)
  const checkResult = computed(() => envStore.env.checkResult)
  const lastProbeAt = computed(() => envStore.env.lastProbeAt)

  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(checkResult.value))
  const probeSourceLabel = computed(() => getProbeSourceLabel(envStore.env.checkSource))
  const familyCards = computed(() => groupEncoderProfilesByFamily(visibleEncoderProfiles.value))
  const overviewStats = computed(() => [
    { label: '运行时', value: checkResult.value?.runtime?.mode ?? '--' },
    { label: 'FFmpeg', value: checkResult.value?.ffmpeg?.available ? 'Ready' : 'Missing' },
    { label: '已探测编码器', value: `${visibleEncoderProfiles.value.length}` },
    { label: '已导入素材', value: `${mediaStore.mediaItems.length}` },
  ])

  return {
    issue,
    isChecking,
    isBootstrapping,
    checkResult,
    lastProbeAt,
    probeSourceLabel,
    familyCards,
    overviewStats,
  }
}
