import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { homedir, platform } from 'node:os'
import { resolve } from 'node:path'

/**
 * @param {NodeJS.ProcessEnv} [environment]
 * @param {NodeJS.Platform} [platformName]
 * @param {string} [homeDirectory]
 */
export function resolveE2ECacheDir(
  environment = process.env,
  platformName = platform(),
  homeDirectory = homedir(),
) {
  if (environment.VP_E2E_CACHE_DIR) {
    return resolve(environment.VP_E2E_CACHE_DIR)
  }

  const systemCacheRoot = platformName === 'win32'
    ? environment.LOCALAPPDATA ?? resolve(homeDirectory, 'AppData', 'Local')
    : environment.XDG_CACHE_HOME ?? resolve(homeDirectory, '.cache')
  return resolve(systemCacheRoot, 'vp-workbench', 'e2e')
}

/**
 * @param {string} cacheDir
 * @param {string} sourcePath
 * @param {string} launcherName
 * @param {NodeJS.Platform} [platformName]
 */
export function rustLauncherCachePath(cacheDir, sourcePath, launcherName, platformName = platform()) {
  const sourceHash = createHash('sha256').update(readFileSync(sourcePath)).digest('hex').slice(0, 16)
  const extension = platformName === 'win32' ? '.exe' : ''
  return resolve(cacheDir, 'launchers', `${launcherName}-${sourceHash}${extension}`)
}
