// APK OTA updater for Android — owner app
// Checks control-plane manifest for owner_android artifact and triggers in-app install

const MANIFEST_ARTIFACT = 'owner_android'

export interface ApkUpdateInfo {
  available: boolean
  version: string | null
  downloadUrl: string | null
  currentVersion: string
}

/**
 * Checks the control-plane manifest for a newer owner APK.
 * Returns update info; available=false if manifest unreachable or up to date.
 */
export async function checkApkUpdate(
  controlPlaneUrl: string,
  installToken: string,
  currentVersion: string
): Promise<ApkUpdateInfo> {
  const noUpdate: ApkUpdateInfo = {
    available: false,
    version: null,
    downloadUrl: null,
    currentVersion,
  }

  try {
    const url = `${controlPlaneUrl}/api/v1/releases/manifest?install_token=${encodeURIComponent(installToken)}`
    const res = await fetch(url)
    if (!res.ok) return noUpdate

    const data = await res.json()
    const artifact = data?.data?.artifacts?.[MANIFEST_ARTIFACT]
    if (!artifact?.version || !artifact?.target_ref) return noUpdate

    const isNewer = compareVersions(artifact.version, currentVersion) > 0
    return {
      available: isNewer,
      version: artifact.version,
      downloadUrl: artifact.target_ref,
      currentVersion,
    }
  } catch {
    return noUpdate
  }
}

/**
 * Downloads the APK from downloadUrl and triggers the system package installer.
 * Uses the native ApkInstaller Capacitor plugin.
 */
export async function downloadAndInstallApk(
  downloadUrl: string,
  fileName: string = 'posvendelo-owner-update.apk'
): Promise<void> {
  const { ApkInstaller } = await import('../plugins/apkInstaller')
  await ApkInstaller.downloadAndInstall({ url: downloadUrl, fileName })
}

/**
 * Compares two semver-like version strings.
 * Returns >0 if a > b, <0 if a < b, 0 if equal.
 */
export function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] ?? 0
    const nb = pb[i] ?? 0
    if (na > nb) return 1
    if (na < nb) return -1
  }
  return 0
}
