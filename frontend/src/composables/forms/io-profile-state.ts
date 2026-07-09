import { computed } from 'vue'

import { buildProfileOptions } from '@/services/preset/io-options'
import type { CodecProfileSpec } from '@/types/domain/capability'

interface IoProfileStateParams<Profile extends CodecProfileSpec> {
  resolveVisibleProfiles: () => readonly Profile[]
  selectedProfileName: () => string
}

export function createIoProfileState<Profile extends CodecProfileSpec>({
  resolveVisibleProfiles,
  selectedProfileName,
}: IoProfileStateParams<Profile>) {
  const visibleProfiles = computed(() => resolveVisibleProfiles())
  const profileOptions = computed(() => buildProfileOptions(visibleProfiles.value))
  const currentProfile = computed(
    () => visibleProfiles.value.find((profile) => profile.name === selectedProfileName()) ?? null,
  )
  const capabilityOptions = computed(() => currentProfile.value?.options ?? [])

  return {
    visibleProfiles,
    profileOptions,
    currentProfile,
    capabilityOptions,
  }
}
