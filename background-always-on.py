#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one target, found {count}")
    p.write_text(text.replace(old, new, 1))

# Force connected sessions to hold both locks continuously, regardless of stale
# settings saved by an older build.
vm = "app/src/main/java/com/mgafk/app/ui/MainViewModel.kt"
replace_once(
    vm,
    '''        val intent = Intent(app, AfkService::class.java)\n            .putExtra(AfkService.EXTRA_WIFI_LOCK, _state.value.settings.wifiLockEnabled)\n            .putExtra(AfkService.EXTRA_WAKE_LOCK_MODE, _state.value.settings.wakeLockMode.toServiceMode())\n            .putExtra(AfkService.EXTRA_WAKE_LOCK_DELAY_MIN, _state.value.settings.wakeLockAutoDelayMin)''',
    '''        // Always-on mode: a connected account must keep CPU + Wi-Fi awake even\n        // when the phone is locked. Do not let stale user settings disable this.\n        val intent = Intent(app, AfkService::class.java)\n            .putExtra(AfkService.EXTRA_WIFI_LOCK, true)\n            .putExtra(AfkService.EXTRA_WAKE_LOCK_MODE, AfkService.MODE_ALWAYS)\n            .putExtra(AfkService.EXTRA_WAKE_LOCK_DELAY_MIN, 0)''',
)

# Ask Android to exempt this sideloaded AFK companion from Doze/battery
# optimization. Android still shows the system confirmation UI; if already
# exempt, nothing is shown.
activity = "app/src/main/java/com/mgafk/app/MainActivity.kt"
replace_once(
    activity,
    '''import android.content.pm.PackageManager\nimport android.os.Build\nimport android.os.Bundle''',
    '''import android.content.pm.PackageManager\nimport android.net.Uri\nimport android.os.Build\nimport android.os.Bundle\nimport android.os.PowerManager\nimport android.provider.Settings''',
)
replace_once(
    activity,
    '''        requestNotificationPermission()\n        setContent {''',
    '''        requestNotificationPermission()\n        requestBatteryOptimizationExemption()\n        setContent {''',
)
replace_once(
    activity,
    '''    private fun requestNotificationPermission() {''',
    '''    private fun requestBatteryOptimizationExemption() {\n        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return\n        val powerManager = getSystemService(PowerManager::class.java)\n        if (powerManager.isIgnoringBatteryOptimizations(packageName)) return\n\n        try {\n            startActivity(\n                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {\n                    data = Uri.parse("package:$packageName")\n                }\n            )\n        } catch (_: Exception) {\n            try {\n                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))\n            } catch (_: Exception) {\n                // Some OEMs hide both screens; the foreground service + locks still run.\n            }\n        }\n    }\n\n    private fun requestNotificationPermission() {''',
)

print("Applied always-on background connection changes")
