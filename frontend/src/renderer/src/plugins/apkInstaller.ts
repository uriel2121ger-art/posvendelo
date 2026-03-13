import { registerPlugin } from '@capacitor/core'

export interface ApkInstallerPlugin {
  downloadAndInstall(options: { url: string; fileName: string }): Promise<void>
}

export const ApkInstaller = registerPlugin<ApkInstallerPlugin>('ApkInstaller')
